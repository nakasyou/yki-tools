"""Check a shared permutation under the hypothetical 12-entry blocks.

For a permutation position P, removal of first nibble a implies
rank(c) = P(c) - (P(a) < P(c)). No actual block boundary is proved here.
"""
import itertools
import json
from pathlib import Path

ROOT = Path(__file__).parent / "data"
lookup = json.loads((ROOT / 'bump_confirmed_lookup.json').read_text())
samples = [('85E', 313), ('85B', 313), ('E5B', 253), ('F58', 241)]
constraints = []
domains = {}
for code, base in samples:
    a, _, c = [int(x, 16) for x in code]
    rank = lookup[code] - base
    constraints.append((a, c, rank))
    domains.setdefault(a, set(range(13)))
    domains[c] = domains.get(c, set(range(13))) & {rank, rank + 1}
variables = sorted(domains)
fits = 0
tested = 0
for positions in itertools.product(*(sorted(domains[x]) for x in variables)):
    tested += 1
    if len(set(positions)) != len(positions):
        continue
    pos = dict(zip(variables, positions))
    if all(pos[c] - int(pos[a] < pos[c]) == rank for a, c, rank in constraints):
        fits += 1
result = {
    'assumptions': ['12-entry blocks at B241+12*k',
                    'fixed first nibble per block',
                    'shared permutation of 1..F excluding 5,A; remove first nibble'],
    'samples': [{'code': code, 'B_number': lookup[code], 'assumed_base': base}
                for code, base in samples],
    'tested_position_assignments': tested,
    'satisfying_assignments': fits,
    'conclusion': 'Assumptions jointly contradicted' if not fits else 'Not rejected',
    'limitation': 'Does not establish true block boundaries or per-block ordering',
}
(ROOT / 'bump_special_shared_order_audit.json').write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(result, ensure_ascii=False, indent=2))
