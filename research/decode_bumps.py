#!/usr/bin/env python3
"""Partial decoder. Returns evidence-backed pairs or explicitly marked models.

Rows must be in insertion order. Convex=1. Terminal row 1010 is
canonical; terminal 0101 triggers reversal of each row's four bits.
Unresolved blocks deliberately return unknown.
"""
import argparse
import json
from pathlib import Path


def rank_pairs(a):
    return [(b, c) for b in range(1, 16) for c in range(1, 16)
            if b not in (5, 10, a) and c not in (5, 10, a, b)]


def decode(rows):
    if len(rows) != 4 or any(len(s) != 4 or set(s) - {'0', '1'} for s in rows):
        raise ValueError('Expected four rows of four binary digits')
    if rows[-1] == '0101':
        rows = [s[::-1] for s in rows]
    if rows[-1] != '1010':
        raise ValueError('Terminal row must be 1010 or mirrored 0101')
    a, b, c, _ = map(lambda s: int(s, 2), rows)
    rail = f'{a:X}{b:X}{c:X}'
    confirmed = json.loads((Path(__file__).resolve().parents[1] / 'packages/yki-core/data/bump_confirmed_lookup.json').read_text())
    if rail in confirmed:
        result = {'rail_hex': rail, 'B_number': confirmed[rail], 'status': 'source-backed pair'}
        evidence_path = (Path(__file__).resolve().parents[1] / 'packages/yki-core/data/bump_lookup_evidence.json')
        evidence = json.loads(evidence_path.read_text()) if evidence_path.exists() else {}
        if rail in evidence:
            result['status'] = evidence[rail]['evidence_kind']
            result['evidence'] = evidence[rail]
        return result
    pairs = rank_pairs(a)
    if (b, c) not in pairs:
        return {'rail_hex': rail, 'B_number': None, 'status': 'unresolved special pattern'}
    rank = pairs.index((b, c))
    if a == 15:
        return {'rail_hex': rail, 'B_number': 725 + rank, 'status': 'F block model; unverified individual pair'}
    if a == 12 and rank < 100:
        return {'rail_hex': rail, 'B_number': 361 + rank, 'status': 'C block model; unverified individual pair'}
    if a in (9, 11, 13):
        n = {9: -41, 11: 49, 13: 139}[a] + rank
        if (b, c) >= (4, 14) and 1 <= n <= 240:
            return {'rail_hex': rail, 'B_number': n, 'status': 'initial block model; unverified individual pair'}
    return {'rail_hex': rail, 'B_number': None, 'status': 'unresolved block'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rows', nargs=4)
    args = parser.parse_args()
    try:
        print(json.dumps(decode(args.rows), ensure_ascii=False, indent=2))
    except ValueError as exc:
        parser.error(str(exc))
