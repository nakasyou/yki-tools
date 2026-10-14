"""Word-based JSON ABI shared with the JavaScript bindings."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from threading import RLock
from typing import Any, Callable

import wasmtime

Json = Any
Host = Callable[[Json], Json]
WasmSource = bytes | bytearray | str | Path


class YkiError(RuntimeError):
    """An operation failed in WASM or its host callback."""


class Runtime:
    def __init__(self, name: str, wasm: WasmSource | None, host: Host | None = None):
        self._engine = wasmtime.Engine()
        if wasm is None:
            resource = files("yki_sdk").joinpath("wasm", name)
            try:
                data = resource.read_bytes()
            except FileNotFoundError as error:
                raise YkiError(
                    "WASM asset missing; run scripts/build.mjs before packaging"
                ) from error
        else:
            data = (
                Path(wasm).read_bytes()
                if isinstance(wasm, (str, Path))
                else bytes(wasm)
            )
        self._store = wasmtime.Store(self._engine)
        module = wasmtime.Module(self._engine, data)
        linker = wasmtime.Linker(self._engine)
        self._host = host
        self._lock = RLock()
        self._active = False
        self._closed = False
        linker.define_func(
            "yki_host",
            "rpc",
            wasmtime.FuncType([], [wasmtime.ValType.i32()]),
            self._rpc,
        )
        instance = linker.instantiate(self._store, module)
        self._exports = instance.exports(self._store)

    def _call(self, name: str, *args: int) -> int | None:
        return self._exports[name](self._store, *args)

    def _send(self, value: Json, begin: str, write: str) -> None:
        data = json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        if self._call(begin, len(data)) != 0:
            raise YkiError("WASM request exceeds 256 MB")
        for offset in range(0, len(data), 4):
            word = int.from_bytes(
                data[offset : offset + 4].ljust(4, b"\0"), "little", signed=True
            )
            self._call(write, offset, word)

    def _receive(self, length: str, read: str) -> Json:
        size = self._call(length)
        data = bytearray()
        for offset in range(0, size, 4):
            word = self._call(read, offset) & 0xFFFFFFFF
            data.extend(word.to_bytes(4, "little"))
        return json.loads(data[:size].decode("utf-8"))

    def _rpc(self) -> int:
        try:
            request = self._receive("host_request_length", "host_request_read")
            if self._host is None:
                raise YkiError(f"Host capability required: {request['op']}")
            reply = self._host(request)
            # Failures to serialize a host reply must also reach the core as errors.
            self._send(reply, "host_response_begin", "host_response_write")
        except Exception as error:
            self._send(
                {"error": str(error)}, "host_response_begin", "host_response_write"
            )
        return 0

    def request(self, value: Json) -> Json:
        with self._lock:
            if self._closed:
                raise YkiError("YKI SDK is closed")
            if self._active:
                raise YkiError("Recursive calls on one WASM instance are unsupported")
            self._active = True
            try:
                self._send(value, "input_begin", "input_write")
                self._call("invoke")
                result = self._receive("output_length", "output_read")
                if isinstance(result, dict) and "error" in result:
                    raise YkiError(result["error"])
                return result
            finally:
                self._active = False

    def close(self) -> None:
        with self._lock:
            if self._active:
                raise YkiError("Cannot close an active WASM request")
            if not self._closed:
                self._closed = True
                self._store.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
