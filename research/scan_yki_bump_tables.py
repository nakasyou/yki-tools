"""Search known pairs in fixed-stride forward/inverse tables.

This covers only explicitly enumerated uncompressed encodings, never all
possible algorithms or compressed representations.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

OUT = Path(__file__).parent / "data"
PAIRS = json.loads((OUT / 'bump_confirmed_lookup.json').read_text())
ROOT = Path(__file__).resolve().parents[1] / 'yki'


def encodings(code):
    canonical = [int(c, 16) for c in code]
    for mirror in (False, True):
        digits = [int(f'{x:04b}'[::-1], 2) if mirror else x for x in canonical]
        for backwards in (False, True):
            ds = digits[::-1] if backwards else digits
            label = f'mirror={mirror},reverse_rows={backwards}'
            v = (ds[0] << 8) | (ds[1] << 4) | ds[2]
            yield label + ',nibble_bytes', bytes(ds), v
            for terminal in (False, True):
                n = (v << 4) | (5 if mirror else 10) if terminal else v
                for endian in ('little', 'big'):
                    for width in (2, 4):
                        yield f'{label},terminal={terminal},{endian}{width}', n.to_bytes(width, endian), n


def scan(path):
    data = path.read_bytes()
    offsets = []
    for pos in range(0x200, len(data), 4):
        v = struct.unpack_from('<I', data, pos)[0]
        off = (v - 0x500800) * 2
        if v == 0xffffffff or not 0 <= off <= len(data) or offsets and off <= offsets[-1]:
            break
        offsets.append(off)
    boundary = next(off for off in offsets if data[off:off + 2] == b'AU')
    metadata = data[:boundary]
    scores = {}
    for code, b_number in PAIRS.items():
        for label, pattern, _ in encodings(code):
            positions = []
            start = 0
            while True:
                pos = metadata.find(pattern, start)
                if pos < 0:
                    break
                positions.append(pos)
                start = pos + 1
            for stride in range(len(pattern), 65):
                counter = scores.setdefault((label, stride), Counter())
                for pos in positions:
                    base = pos - (b_number - 1) * stride
                    if base >= 0 and base + 987 * stride + len(pattern) <= boundary:
                        counter[base] += 1
    best = sorted(({'encoding': label, 'stride': stride, 'base': base, 'matches': count}
                   for (label, stride), counts in scores.items()
                   for base, count in counts.items()), key=lambda r: -r['matches'])[:10]
    inverse_scores = {}
    inverse_pairs = {code: n for code, n in PAIRS.items() if n >= 241}
    for code, b_number in inverse_pairs.items():
        indices = {}
        for label, _, value in encodings(code):
            if ',nibble_bytes' in label:
                continue
            index_label = label.rsplit(',', 1)[0]
            indices[index_label] = value
        for endian in ('little', 'big'):
            for width in (2, 4):
                for zero_based in (False, True):
                    pattern = (b_number - int(zero_based)).to_bytes(width, endian)
                    positions = []
                    start = 0
                    while True:
                        pos = metadata.find(pattern, start)
                        if pos < 0:
                            break
                        positions.append(pos)
                        start = pos + 1
                    for index_label, value in indices.items():
                        maximum_index = 65535 if 'terminal=True' in index_label else 4095
                        for stride in range(width, 17):
                            key = (index_label, endian, width, zero_based, stride)
                            counter = inverse_scores.setdefault(key, Counter())
                            for pos in positions:
                                base = pos - value * stride
                                if base >= 0 and base + maximum_index * stride + width <= boundary:
                                    counter[base] += 1
    inverse_best = sorted(({'index_encoding': label, 'value_endian': endian,
                            'value_bytes': width, 'zero_based_B': zero_based,
                            'stride': stride, 'base': base, 'matches': count}
                           for (label, endian, width, zero_based, stride), counts in inverse_scores.items()
                           for base, count in counts.items()), key=lambda r: -r['matches'])[:10]
    return {'path': str(path), 'sha256': hashlib.sha256(data).hexdigest(),
            'metadata_bytes_scanned': boundary, 'known_pair_count': len(PAIRS),
            'best_forward_candidates': best,
            'inverse_known_pair_count': len(inverse_pairs),
            'best_inverse_candidates': inverse_best}


if __name__ == '__main__':
    result = {'scope': 'Header and resource region before first AU; B-indexed tables of988 entries with strides up to64; code-indexed full4096/65536-entry tables with strides up to16, B or B-1 stored as2/4 bytes; inverse tests use known B>=241',
              'encodings': 'Nibble bytes or packed 12/16-bit code in 2/4 bytes; both byte orders, row orders and per-nibble mirror orientations',
              'limitation': 'Does not test compressed tables, permutations of sensor wires, variable-length tables, embedded AU data, algorithmic conversion, or internal watch ROM',
              'files': []}
    for path in sorted(ROOT.glob('*.yki')):
        row = scan(path)
        result['files'].append(row)
        print(path.name, 'metadata', row['metadata_bytes_scanned'], 'forward', row['best_forward_candidates'][:1], 'inverse', row['best_inverse_candidates'][:1], flush=True)
    (OUT / 'bump_yki_table_scan.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
