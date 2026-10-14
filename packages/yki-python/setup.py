"""Reject wheels with missing runtime assets instead of shipping a broken SDK."""

from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildWithWasm(build_py):
    def run(self):
        root = Path(__file__).parent / "yki_sdk" / "wasm"
        for name in ("yki-core.wasm", "yki-3d.wasm"):
            if not (root / name).is_file():
                raise RuntimeError(
                    "Missing WASM assets: run "
                    "node packages/yki-python/scripts/build.mjs from the repository root"
                )
        super().run()


setup(cmdclass={"build_py": BuildWithWasm})
