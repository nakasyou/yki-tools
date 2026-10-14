"""Thin bindings: parsing, editing, and codecs run entirely in MoonBit WASM."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._runtime import Host, Runtime, WasmSource, YkiError


@dataclass(frozen=True)
class BuildResult:
    data: bytes
    manifest: dict[str, Any]


class Core(Runtime):
    def __init__(self, wasm: WasmSource | None = None, *, host: Host | None = None):
        super().__init__("yki-core.wasm", wasm, host)

    def schema(self) -> dict:
        return self.request({"op": "schema"})

    def validate_config(self, config: dict) -> dict:
        return self.request({"op": "validate_config", "config": config})

    def inspect(self, data: bytes) -> dict:
        return self.request({"op": "inspect", "hex": data.hex()})

    def describe(self, data: bytes) -> dict:
        return self.request({"op": "describe", "hex": data.hex()})

    def extract(self, data: bytes, resource: int) -> bytes:
        return bytes.fromhex(
            self.request({"op": "extract", "hex": data.hex(), "resource": resource})[
                "hex"
            ]
        )

    def roundtrip(self, data: bytes) -> bytes:
        return bytes.fromhex(
            self.request({"op": "roundtrip", "hex": data.hex()})["hex"]
        )

    def resolve(self, data: bytes, medal_id: Any, *, strict: bool = False) -> dict:
        return self.request(
            {"op": "resolve", "hex": data.hex(), "id": medal_id, "strict": strict}
        )

    def validate(self, config: dict, *, strict: bool = False) -> dict:
        return self.request({"op": "validate", "config": config, "strict": strict})

    def build(self, config: dict, *, strict: bool = False) -> BuildResult:
        result = self.request({"op": "build", "config": config, "strict": strict})
        return BuildResult(bytes.fromhex(result["hex"]), result["manifest"])

    def decode(self, blob: bytes) -> bytes:
        return bytes.fromhex(self.request({"op": "decode", "hex": blob.hex()})["hex"])

    def encode_g7221(self, pcm: bytes) -> bytes:
        return bytes.fromhex(
            self.request({"op": "g7221_encode", "hex": pcm.hex()})["hex"]
        )

    def decode_g7221(self, payload: bytes) -> bytes:
        return bytes.fromhex(
            self.request({"op": "g7221_decode", "hex": payload.hex()})["hex"]
        )


class ThreeD(Runtime):
    def __init__(self, wasm: WasmSource | None = None):
        super().__init__("yki-3d.wasm", wasm)

    def generate_medal(
        self,
        bits: str,
        *,
        mode: str = "normal",
        orientation: str = "canonical",
        mirror: bool = False,
    ) -> dict:
        return self.request(
            {
                "op": "generate_medal",
                "bits": bits,
                "mode": mode,
                "orientation": orientation,
                "mirror": mirror,
            }
        )


class YkiSDK(Core):
    """Combined YKI and 3D bindings. Supplied hosts remain caller-owned."""

    def __init__(
        self,
        wasm: WasmSource | None = None,
        *,
        wasm3d: WasmSource | None = None,
        host: Host | None = None,
    ):
        super().__init__(wasm, host=host)
        try:
            self._three_d = ThreeD(wasm3d)
        except Exception:
            super().close()
            raise

    def request(self, value: Any) -> Any:
        # Serialize both modules against close; the core guard rejects recursion.
        with self._lock:
            if isinstance(value, dict) and value.get("op") == "generate_medal":
                if self._closed:
                    raise YkiError("YKI SDK is closed")
                return self._three_d.request(value)
            return super().request(value)

    def generate_medal(
        self,
        bits: str,
        *,
        mode: str = "normal",
        orientation: str = "canonical",
        mirror: bool = False,
    ) -> dict:
        return self.request(
            {
                "op": "generate_medal",
                "bits": bits,
                "mode": mode,
                "orientation": orientation,
                "mirror": mirror,
            }
        )

    def close(self) -> None:
        with self._lock:
            if self._active:
                raise YkiError("Cannot close an active WASM request")
            self._three_d.close()
            super().close()
