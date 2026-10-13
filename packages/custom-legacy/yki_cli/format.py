import importlib.util
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("yki_verified_parser", ROOT / "research/analyze_yki.py")
_parser = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_parser)
parse = _parser.parse
EMPTY = [0xFFFF, 0xFFFF]
FIELDS = {"summonSound": 0, "tribeSound": 2, "nameSound": 4,
          "introSound": 5, "postSound": 6, "callSound": 8}


class Image:
    """Stable asset handles while editing; references are relocated only at serialize."""

    def __init__(self, data):
        self.original = bytes(data)
        self.parsed = parse(data)
        self.header = bytearray(data[:512])
        self.rows = [[p[:] for p in m["pairs"]] for m in self.parsed["medals"]]
        self.root = [p[:] for p in self.parsed["resources"][0]["pairs"]]
        self.assets = []
        for r in self.parsed["resources"]:
            stop = r["offset"] + r.get("asset_bytes", r["span_bytes"])
            self.assets.append(dict(kind=r["kind"], blob=bytes(data[r["offset"]:stop]),
                                   pairs=[p[:] for p in r.get("pairs", [])]))
        self.last_mapping = {}

    def append(self, kind, blob=b"", pairs=None):
        self.assets.append(dict(kind=kind, blob=blob, pairs=pairs or []))
        return [1, len(self.assets)-1]

    def kind(self, pair):
        return self.assets[pair[1]]["kind"] if pair[0] == 1 else None

    def audio_pair(self, pair):
        if self.kind(pair) == "sequence":
            return self.assets[pair[1]]["pairs"][1][:]
        return pair[:]

    def song_pair(self, row):
        pair = row[1]
        if self.kind(pair) != "sequence":
            raise ValueError("songSound requires a song sequence in p1; use type: song or a song template")
        return self.audio_pair(pair)

    def audio_blob(self, pair):
        pair = self.audio_pair(pair)
        if self.kind(pair) != "audio":
            return None
        return self.assets[pair[1]]["blob"]

    def row_type(self, row):
        return "song" if self.kind(row[1]) == "sequence" or row[0] == [0xFFFE]*2 else "normal"

    def active(self, row):
        # p5 often has a default even on unsupported rows; it is not an activation flag.
        return any(row[i][0] in (0, 1) for i in (0, 1, 2, 4))

    def serialize(self):
        kinds = ("root", "medal_table", "led_candidate", "sequence", "audio")
        order = sorted(range(len(self.assets)), key=lambda i: (kinds.index(self.assets[i]["kind"]), i))
        if len(order) > 65535:
            raise ValueError("too many resources for the u16 resource count")
        mapping = {old: new for new, old in enumerate(order)}
        self.last_mapping = mapping

        def pair_bytes(ps):
            return b"".join(struct.pack("<HH", t, mapping[v] if t == 1 else v) for t, v in ps)

        blobs = []
        for handle in order:
            a = self.assets[handle]
            if a["kind"] == "root":
                blob = pair_bytes(self.root)
            elif a["kind"] == "medal_table":
                blob = b"".join(pair_bytes(row) for row in self.rows)
            elif a["kind"] == "sequence":
                blob = pair_bytes(a["pairs"])
            else:
                blob = a["blob"]
            blobs.append(blob)
        cursor = 512 + 4 * len(blobs)
        offsets = []
        for blob in blobs:
            offsets.append(cursor)
            cursor += len(blob)
        size = (cursor + 4095) // 4096 * 4096
        base = self.parsed["header"]["base_word_address"]
        if base + size//2 > 0xFFFFFFFF:
            raise ValueError("YKI is too large for its word addresses")
        header = self.header[:]
        struct.pack_into("<I", header, 0x26, base + size//2)
        struct.pack_into("<H", header, 0x2A, len(blobs))
        struct.pack_into("<H", header, 0x2E, 0)
        pad_size = size-cursor
        old_pad = bytes.fromhex(self.parsed["resources"][-1].get("alignment_padding", {}).get("hex", ""))
        pattern = old_pad[:8] if len(old_pad) >= 8 else b"\xFF"*8
        if pad_size == len(old_pad):
            # Legacy fill changes phase within some blocks; preserve it byte-for-byte.
            pad = old_pad
        else:
            pad = (pattern * ((pad_size+7)//8))[:pad_size]
            if pad_size >= 2:
                pad = pad[:-2] + b"\0\0"
        table = struct.pack(f"<{len(offsets)}I", *(base + o//2 for o in offsets))
        data = bytearray(header + table + b"".join(blobs) + pad)
        struct.pack_into("<H", data, 0x2E, (-sum(data)) % 256)
        parse(data)
        return bytes(data)
