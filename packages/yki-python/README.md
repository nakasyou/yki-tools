# Python YKI SDK

Synchronous Python bindings for the existing MoonBit YKI and 3D WASM modules using Wasmtime. Parsing, ID resolution, editing, validation, checksums, audio encoding/decoding, and medal model generation run inside WASM. The SDK does not invoke JavaScript or the legacy Python implementation at runtime.

## Build and install from this repository

Requires Python 3.10+, Node.js 24+, and MoonBit for building. From the repository root:

```sh
node packages/yki-python/scripts/build.mjs
python -m pip install ./packages/yki-python
```

The build script compiles both modules and copies them into `yki_sdk/wasm/`. They are included in wheels and source distributions. Installed users need Python and the `wasmtime` dependency; Node.js and MoonBit are unnecessary at runtime. No package has been published to PyPI.

```sh
python -m pip install build
python -m build packages/yki-python
python -m unittest discover -s packages/yki-python/tests -v
```

Run the WASM build before packaging. For development, use `pip install -e ./packages/yki-python`. Alternatively, supply WASM bytes or paths explicitly when constructing a binding.

## YKI editing

```python
from pathlib import Path
from yki_sdk import FileHost, YkiSDK

# read/transcode/gain/measure use this optional host. Codecs stay in WASM.
with FileHost("/path/to/config", stock_dir="/path/to/yki") as host:
    with YkiSDK(host=host) as sdk:
        result = sdk.build(
            {
                "extends": "base.yki",
                "version": 0,
                "overrides": [],
            }
        )
        Path("output.yki").write_bytes(result.data)
        print(result.manifest)
```

Numeric `extends` resolves `@stock/VerN_U.yki` and requires `stock_dir`. Audio conversion and loudness measurement require native FFmpeg; set `ffmpeg` on `FileHost` to choose another executable. Simple file reads, codecs, and 3D generation need no FFmpeg. The host has the same operations as the Node host. Paths resolve from `base_dir`; input files are not changed.

## Host-free codecs and 3D models

```python
from yki_sdk import Core, ThreeD

with Core() as core:
    encoded = core.encode_g7221(bytes(640))
    pcm = core.decode_g7221(encoded)

with ThreeD() as models:
    medal = models.generate_medal("1011 0110 0001 1010", mode="lite")
    print(medal["rows"], medal["filename"])
```

Medals return OpenSCAD source, oriented rows, mode, and a suggested filename. Save `medal["source"]` as `.scad`; rendering STL requires OpenSCAD. `YkiSDK` also exposes `generate_medal` and routes `request({"op": "generate_medal", ...})` to its independent 3D instance.

## Custom hosts and API

```python
from yki_sdk import Core

base = open("base.yki", "rb").read()


def host(request):
    if request["op"] == "read" and request["path"] == "base.yki":
        return {"hex": base.hex()}
    raise ValueError(f"Unsupported capability: {request['op']}")


with Core(host=host) as core:
    result = core.build({"extends": "base.yki", "overrides": []})
```

Hosts are synchronous callables accepting and returning JSON-compatible values. Binary host payloads use lowercase hex. Callback failures become `YkiError`; the instance remains usable. See the [core ABI and host documentation](../yki-core/README.md).

`Core` provides `request`, `schema`, `validate_config`, `inspect`, `describe`, `extract`, `roundtrip`, `resolve`, `validate`, `build`, `decode`, `encode_g7221`, and `decode_g7221`. `build` returns a `BuildResult` with `bytes` data and a manifest dictionary. Other structured results are dictionaries matching the WASM JSON API. Pass `strict=True` to `build`, `validate`, or `resolve` to enforce mapping confidence.

Each binding has its own WASM instance; operations are serialized with a lock. Recursive requests on the same instance are rejected. Context managers close the bindings, and later requests raise `YkiError`. Caller-supplied hosts are not closed by the SDK; manage their lifetime separately. The ABI input limit is 256 MB, and hex encoding increases memory use for large files.
