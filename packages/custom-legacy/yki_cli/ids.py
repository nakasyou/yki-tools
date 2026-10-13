import json
import re
from .format import ROOT, FIELDS


def bump_rows(value):
    if isinstance(value, str):
        text = value.removeprefix("0x").removeprefix("0X")
        if not re.fullmatch(r"[0-9A-Fa-f]{4}", text):
            raise ValueError("bumpsHex must have all four nibbles, including the terminal A/5")
        rows = [f"{int(c, 16):04b}" for c in text]
    else:
        rows = list(value)
    if len(rows) != 4 or any(not re.fullmatch("[01]{4}", s) for s in rows):
        raise ValueError("bumps must be four strings of four binary digits")
    if rows[-1] == "0101":
        rows = [s[::-1] for s in rows]
    if rows[-1] != "1010":
        raise ValueError("terminal bump row must be 1010 or mirrored 0101")
    return rows


def bump_mapping(value):
    rows = bump_rows(value)
    a, b, c, _ = [int(s, 2) for s in rows]
    rail = f"{a:X}{b:X}{c:X}"
    lookups = json.loads((ROOT / "research/data/bump_confirmed_lookup.json").read_text())
    evidence = json.loads((ROOT / "research/data/bump_lookup_evidence.json").read_text()).get(rail, {})
    if rail in lookups:
        confidence = "high" if evidence.get("physical_printed_B_verified") else "medium"
        return dict(row=lookups[rail], confidence=confidence, rail_hex=rail,
                    canonical_rows=rows, evidence=evidence or {"kind": "legacy source lookup; provenance not fully audited"})
    pairs = [(x,y) for x in range(1,16) for y in range(1,16)
             if x not in (5,10,a) and y not in (5,10,a,x)]
    number = None
    if (b,c) in pairs:
        rank = pairs.index((b,c))
        if a == 15:
            number = 725+rank
        elif a == 12 and rank < 100:
            number = 361+rank
        elif a in (9,11,13):
            candidate = {9:-41, 11:49, 13:139}[a]+rank
            if (b,c) >= (4,14) and 1 <= candidate <= 240:
                number = candidate
    if number is None:
        raise ValueError(f"no known bump-to-row mapping for {rail}A; use an explicit medal row only if independently known")
    return dict(row=number, confidence="low", rail_hex=rail, canonical_rows=rows,
                evidence={"kind":"unverified block formula; not a proven general conversion"})


def resolve_id(value, image, warn, strict=False):
    if isinstance(value, int):
        result = dict(row=value, confidence="explicit", source="medal row")
    elif isinstance(value, list):
        result = bump_mapping(value)
    elif isinstance(value, str):
        if re.fullmatch(r"B[0-9]{1,3}", value, re.IGNORECASE):
            result = dict(row=int(value[1:]), confidence="explicit", source="medal B number")
        else:
            result = bump_mapping(value)
    elif "medal" in value and "sound" not in value:
        result = dict(row=value["medal"], confidence="explicit", source="medal row")
    elif "bumpsHex" in value:
        result = bump_mapping(value["bumpsHex"])
    elif "bumps" in value:
        result = bump_mapping(value["bumps"])
    elif "sound" in value:
        field = value.get("field", "nameSound")
        tag = 1 if value.get("namespace", "builtin") == "resource" else 0
        hits = []
        for i, row in enumerate(image.rows):
            if field == "songSound":
                if image.kind(row[1]) != "sequence":
                    continue
                pair = image.song_pair(row)
            else:
                pair = image.audio_pair(row[FIELDS[field]])
            if pair == [tag,value["sound"]]:
                hits.append(i+1)
        if "medal" in value:
            hits = [n for n in hits if n == value["medal"]]
        if len(hits) != 1:
            raise ValueError(f"internal sound ID {value['sound']} matches rows {hits}; specify id.medal to disambiguate, or use a medal ID")
        result = dict(row=hits[0], confidence="exact-existing-reference", source="internal sound ID",
                      sound=value["sound"], namespace=value.get("namespace","builtin"), field=field)
    else:
        raise ValueError("unsupported ID")
    if not 1 <= result["row"] <= 988:
        raise ValueError("medal row must be between 1 and 988; extending the hardware lookup table is unverified")
    if result["confidence"] in ("low","medium"):
        text = f"ID mapping {result.get('rail_hex')} → B{result['row']} has {result['confidence']} confidence: {result['evidence']}"
        if strict:
            raise ValueError(text)
        warn(text)
    return result
