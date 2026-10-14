"""Optional native file/FFmpeg host. Audio codecs remain inside WASM."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import RLock

from ._runtime import YkiError


class FileHost:
    def __init__(
        self,
        base_dir: str | Path = ".",
        *,
        stock_dir: str | Path | None = None,
        ffmpeg: str = "ffmpeg",
    ):
        self.base_dir = Path(base_dir).resolve()
        self.stock_dir = Path(stock_dir).resolve() if stock_dir is not None else None
        self.ffmpeg = ffmpeg
        self._temporary = TemporaryDirectory(prefix="yki-sdk-")
        self._root = Path(self._temporary.name)
        self._closed = False
        self._lock = RLock()

    def resolve_path(self, path: str) -> Path:
        if path.startswith("@stock/"):
            if self.stock_dir is None:
                raise YkiError("Numeric extends requires stock_dir")
            return self.stock_dir / path[7:]
        return self.base_dir / path

    def _command(self, args: list[str]) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                [self.ffmpeg, "-hide_banner", "-nostats", *args],
                capture_output=True,
                check=True,
            )
        except FileNotFoundError as error:
            raise YkiError(f"Required executable not found: {self.ffmpeg}") from error
        except subprocess.CalledProcessError as error:
            raise YkiError(
                f"FFmpeg failed: {error.stderr.decode(errors='replace')[-2000:]}"
            ) from error

    def __call__(self, request: dict) -> dict:
        with self._lock:
            if self._closed:
                raise YkiError("File host is closed")
            op = request["op"]
            if op == "read":
                return {"hex": self.resolve_path(request["path"]).read_bytes().hex()}
            if op == "transcode":
                path = self.resolve_path(request["path"])
                source = path.read_bytes()
                output = self._root / "transcode.pcm"
                self._command(
                    [
                        "-loglevel",
                        "error",
                        "-y",
                        "-i",
                        str(path),
                        "-map",
                        "0:a:0",
                        "-ar",
                        "16000",
                        "-ac",
                        "1",
                        "-c:a",
                        "pcm_s16le",
                        "-f",
                        "s16le",
                        str(output),
                    ]
                )
                return {
                    "hex": output.read_bytes().hex(),
                    "sha256": hashlib.sha256(source).hexdigest(),
                }
            if op not in ("gain", "measure"):
                raise YkiError(f"Unknown host operation: {op}")
            source = self._root / "input.pcm"
            source.write_bytes(bytes.fromhex(request["hex"]))
            args = ["-f", "s16le", "-ar", "16000", "-ac", "1", "-i", str(source)]
            if op == "gain":
                output = self._root / "gain.pcm"
                self._command(
                    [
                        *args,
                        "-loglevel",
                        "error",
                        "-y",
                        "-af",
                        f"volume={request['gain']:.9f}",
                        "-c:a",
                        "pcm_s16le",
                        "-f",
                        "s16le",
                        str(output),
                    ]
                )
                return {"hex": output.read_bytes().hex()}
            result = self._command(
                [*args, "-af", "loudnorm=print_format=json", "-f", "null", "-"]
            )
            stderr = result.stderr.decode()
            values = json.loads(stderr[stderr.rfind("{") : stderr.rfind("}") + 1])

            def finite(value):
                number = float(value)
                return number if math.isfinite(number) else None

            return {
                "lufs": finite(values["input_i"]),
                "true_peak_dbtp": finite(values["input_tp"]),
                "lra": finite(values["input_lra"]),
            }

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._temporary.cleanup()
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
