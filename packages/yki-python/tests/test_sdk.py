import concurrent.futures
import hashlib
import shutil
import struct
import tempfile
import unittest
import wave
from importlib.resources import files
from pathlib import Path

from yki_sdk import Core, FileHost, ThreeD, YkiError, YkiSDK


def fixture():
    """Construct a YKI independently of the parser under test."""
    root = bytearray(b"\xff" * 120)
    struct.pack_into("<HH", root, 44, 0, 66)
    rows = bytearray(b"\xff" * (988 * 36))
    for row, slot, tag, value in [
        (1, 0, 0, 37),
        (1, 2, 0, 1),
        (1, 4, 0, 117),
        (655, 0, 65534, 65534),
        (655, 1, 1, 3),
    ]:
        struct.pack_into("<HH", rows, (row - 1) * 36 + slot * 4, tag, value)
    led = bytes.fromhex("ffff010002000300ffffffffffff")
    sequence = bytes.fromhex("0100020001000400")
    audio = bytearray(72)
    struct.pack_into("<2sHHHII", audio, 0, b"AU", 16000, 1600, 1, 1, 20)
    for offset, value in [(22, 65535), (26, 16), (28, 65535), (30, 65535)]:
        struct.pack_into("<H", audio, offset, value)
    blobs = [root, rows, led, sequence, audio]
    cursor = 512 + len(blobs) * 4
    offsets = []
    for blob in blobs:
        offsets.append(cursor)
        cursor += len(blob)
    size = (cursor + 4095) // 4096 * 4096
    data = bytearray(b"\xff" * size)
    data[: 512 + len(blobs) * 4] = bytes(512 + len(blobs) * 4)
    magic = b"BandaiYokai3rd******************"
    data[: len(magic)] = magic
    struct.pack_into("<IIH", data, 34, 0x500800, 0x500800 + size // 2, len(blobs))
    for i, (offset, blob) in enumerate(zip(offsets, blobs)):
        struct.pack_into("<I", data, 512 + i * 4, 0x500800 + offset // 2)
        data[offset : offset + len(blob)] = blob
    struct.pack_into("<H", data, size - 2, 0)
    struct.pack_into("<H", data, 46, -sum(data) & 255)
    return bytes(data)


class SDKTests(unittest.TestCase):
    def setUp(self):
        self.base = fixture()

    def test_inspection_and_roundtrip(self):
        with Core() as core:
            self.assertEqual(
                core.inspect(self.base)["sha256"], hashlib.sha256(self.base).hexdigest()
            )
            self.assertEqual(core.roundtrip(self.base), self.base)
            self.assertEqual(len(core.describe(self.base)["rows"]), 988)
            self.assertEqual(core.extract(self.base, 4)[:2], b"AU")
            self.assertEqual(
                core.resolve(self.base, "E7BA", strict=True)["resolution"]["row"], 655
            )

    def test_build_and_version_edit(self):
        calls = []

        def host(request):
            calls.append(request)
            return {"hex": self.base.hex()}

        with YkiSDK(host=host) as sdk:
            self.assertEqual(sdk.build({"extends": 2, "overrides": []}).data, self.base)
            edited = sdk.build({"extends": 2, "version": 0, "overrides": []})
            self.assertEqual(edited.manifest["version"], 0)
            self.assertEqual(sdk.inspect(edited.data)["version"], 0)
            self.assertEqual(len(calls), 2)
            self.assertTrue(
                sdk.validate_config({"extends": 2, "overrides": []})["schema_valid"]
            )
            self.assertIsInstance(sdk.validate({"extends": 2, "overrides": []}), dict)

    def test_codec_is_host_free(self):
        with Core() as core:
            encoded = core.encode_g7221(bytes(640))
            self.assertEqual(len(encoded), 40)
            self.assertEqual(len(core.decode_g7221(encoded)), 640)
            audio = core.extract(self.base, 4)
            self.assertEqual(len(core.decode(audio)), 640)

    def test_error_recovery_and_host_errors(self):
        def failing_host(request):
            raise ValueError("test host failure")

        with Core(host=failing_host) as core:
            with self.assertRaisesRegex(YkiError, "test host failure"):
                core.build({"extends": 2, "overrides": []})
            with self.assertRaises(YkiError):
                core.inspect(b"bad")
            self.assertEqual(core.roundtrip(self.base), self.base)
        with Core() as core:
            with self.assertRaisesRegex(YkiError, "Host capability required"):
                core.build({"extends": 2, "overrides": []})
            with self.assertRaises(ValueError):
                core.request({"op": "inspect", "value": float("nan")})
            self.assertIsInstance(core.schema(), dict)

    def test_recursive_callback_is_rejected(self):
        with Core(host=lambda _: core.schema()) as core:
            with self.assertRaisesRegex(YkiError, "Recursive"):
                core.build({"extends": 2, "overrides": []})
            self.assertIsInstance(core.schema(), dict)

    def test_independent_instances_and_threads(self):
        with Core() as first, Core() as second:
            self.assertEqual(first.roundtrip(self.base), second.roundtrip(self.base))
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
                replies = list(
                    pool.map(lambda _: first.inspect(self.base)["version"], range(4))
                )
            self.assertEqual(replies, [2] * 4)

    def test_medal_model_and_json_routing(self):
        with YkiSDK() as sdk, ThreeD() as three_d:
            for mode in ("normal", "classic", "lite"):
                for orientation in ("canonical", "physical"):
                    for mirror in (False, True):
                        medal = sdk.generate_medal(
                            "1011 0110 0001 1010",
                            mode=mode,
                            orientation=orientation,
                            mirror=mirror,
                        )
                        rows = ["1011", "0110", "0001", "1010"]
                        if (orientation == "canonical") != mirror:
                            rows = [row[::-1] for row in rows]
                        self.assertEqual(medal["rows"], rows)
                        self.assertEqual(
                            medal["filename"], f"medal_{''.join(rows)}_{mode}.scad"
                        )
                        self.assertIn(f'mode = "{mode}";', medal["source"])
            expected = three_d.generate_medal("0" * 16)
            self.assertEqual(
                sdk.request({"op": "generate_medal", "bits": "0" * 16}), expected
            )
            with self.assertRaises(YkiError):
                sdk.generate_medal("bad")
            self.assertEqual(sdk.generate_medal("0" * 16), expected)
        with self.assertRaisesRegex(YkiError, "closed"):
            sdk.generate_medal("0" * 16)
        with self.assertRaisesRegex(YkiError, "closed"):
            sdk.schema()
        sdk.close()

    def test_explicit_wasm_path_and_bytes(self):
        data = files("yki_sdk").joinpath("wasm", "yki-core.wasm").read_bytes()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "core.wasm"
            path.write_bytes(data)
            with Core(path) as from_path, Core(data) as from_bytes:
                self.assertEqual(from_path.schema(), from_bytes.schema())

    def test_file_host_and_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "base.yki").write_bytes(self.base)
            with FileHost(directory, stock_dir=directory) as host:
                with Core(host=host) as core:
                    self.assertEqual(
                        core.build({"extends": "base.yki", "overrides": []}).data,
                        self.base,
                    )
                self.assertEqual(
                    host({"op": "read", "path": "@stock/base.yki"})["hex"],
                    self.base.hex(),
                )
                temporary = host._root
            self.assertFalse(temporary.exists())
            with self.assertRaisesRegex(YkiError, "closed"):
                host({"op": "read", "path": "base.yki"})

    @unittest.skipUnless(shutil.which("ffmpeg"), "Native FFmpeg is optional")
    def test_real_ffmpeg_media_host(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "base.yki").write_bytes(self.base)
            with wave.open(str(Path(directory, "tone.wav")), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(bytes(3200))
            with FileHost(directory) as host, Core(host=host) as core:
                built = core.build(
                    {
                        "extends": "base.yki",
                        "audio": {"volume": "preserve"},
                        "overrides": [{"id": 655, "songSound": "tone.wav"}],
                    }
                )
                self.assertEqual(built.manifest["audio"][0]["frames"], 5)
                self.assertEqual(
                    len(
                        host({"op": "gain", "hex": bytes(640).hex(), "gain": 1})["hex"]
                    ),
                    1280,
                )
                self.assertIsNone(
                    host({"op": "measure", "hex": bytes(3200).hex()})["lufs"]
                )


if __name__ == "__main__":
    unittest.main()
