# Research

- `analyze_yki.py`: Analyzes YKI structure, references, and checksums. Original files are read from `../yki/`; extracted data is written to `../outputs/yki_analysis/`.
- `decode_bumps.py`: Resolves peg patterns to B numbers with supporting evidence and confidence levels.
- `audit_special_order.py`, `scan_yki_bump_tables.py`, and `compare_yki_unknowns.py`: Investigate mappings and unresolved regions.
- `data/`: JSON and CSV records of analysis results, mappings, sources, and hypotheses. Includes the lookup tables used by the CLI.
- `reports/`: Hardware experiment records.
- `experiments/`: Exploratory scripts, some of which depend on specific execution conditions or locally downloaded materials.

```sh
python3 research/analyze_yki.py
python3 research/decode_bumps.py --help
```

Downloaded web pages and third-party sources are kept in `../third_party/local/work/`. They are excluded from Git along with extracted binaries and audio in `../outputs/`. Historical paths in research records are retained as records of the original experiments. Refer to each record's confidence levels and notes to distinguish inferred behavior from hardware observations.
