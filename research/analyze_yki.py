"""Lossless structural analysis of the six locally available Yo-kai Watch U YKIs.

Run: python research/analyze_yki.py [--decode-audio]
No device behavior is assumed for built-in IDs, markers, or LED timing.
"""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs/yki_analysis"
MAGIC = b"BandaiYokai3rd******************"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pairs(data):
    require(len(data) % 4 == 0, "pair list must be a multiple of 4 bytes")
    return [list(p) for p in struct.iter_unpack("<HH", data)]


def parse(data):
    require(len(data) >= 512 and len(data) % 4096 == 0, "invalid file size")
    require(data[:32] == MAGIC, "invalid magic")
    require(sum(data) % 256 == 0, "invalid additive checksum")
    flag, base, end, count, flag2, check, flag3 = struct.unpack_from("<HIIHHHH", data, 32)
    require(base == 0x500800, "unsupported base address")
    require(end == base + len(data) // 2, "end address disagrees with file length")
    require(2 < count and 512 + count * 4 < len(data), "invalid resource count")
    addresses = list(struct.unpack_from(f"<{count}I", data, 512))
    offsets = [(a - base) * 2 for a in addresses]
    require(offsets[0] == 512 + 4 * count, "unexpected gap after pointer table")
    require(all(a < b for a, b in zip(offsets, offsets[1:])), "non-monotonic pointers")
    require(all(512 <= o < len(data) for o in offsets), "pointer outside file")
    bounds = offsets + [len(data)]
    blobs = [data[a:b] for a, b in zip(bounds, bounds[1:])]
    require(len(blobs[0]) == 120, "invalid root size")
    require(len(blobs[1]) == 988 * 36, "invalid medal table size")
    resources = []
    segments = []

    def segment(start, stop, kind, resource=None):
        if start != stop:
            segments.append(dict(start=start, end=stop, size=stop-start, kind=kind,
                                 resource=resource, sha256=sha(data[start:stop])))

    segment(0, 32, "magic")
    segment(32, 64, "header_fields")
    segment(64, 512, "header_reserved_pattern")
    segment(512, offsets[0], "resource_word_addresses")
    audio_fields = ["sample_rate", "bit_rate_raw", "channels", "frame_count",
                    "payload_words", "mark_flag", "silence_flag", "mbf", "pcs",
                    "rec", "header_words", "audio32_type", "padding_word"]
    for i, (a, b, blob) in enumerate(zip(bounds, bounds[1:], blobs)):
        r = dict(id=i, offset=a, span_bytes=b-a, raw_sha256=sha(blob))
        if i == 0:
            r.update(kind="root", pairs=pairs(blob))
            segment(a, b, "root_pairs", i)
        elif i == 1:
            r.update(kind="medal_table", record_count=988, record_bytes=36)
            segment(a, b, "medal_pairs", i)
        elif blob[:2] == b"AU":
            h = dict(zip(audio_fields, struct.unpack_from("<HHHII8H", blob, 2)))
            require(h["header_words"] == 16, f"AU {i}: unexpected header size")
            require(h["sample_rate"] == 16000 and h["channels"] == 1,
                    f"AU {i}: unexpected rate/channels")
            require(h["payload_words"] == h["frame_count"] * 20,
                    f"AU {i}: frame/payload size mismatch")
            payload_end = 32 + h["payload_words"] * 2
            require(payload_end <= len(blob), f"AU {i}: truncated payload")
            require(i == count-1 or payload_end == len(blob), f"AU {i}: extra bytes")
            require(h["bit_rate_raw"] == 1600, f"AU {i}: unexpected bit rate field")
            h.update(frame_bytes=40, decoded_samples_expected=h["frame_count"] * 320,
                     duration_seconds=h["frame_count"] / 50,
                     bit_rate_bits_per_second=16000)
            r.update(kind="audio", header=h, asset_bytes=payload_end,
                     asset_sha256=sha(blob[:payload_end]),
                     payload_sha256=sha(blob[32:payload_end]))
            segment(a, a+32, "audio_header", i)
            segment(a+32, a+payload_end, "compressed_audio_frames", i)
            segment(a+payload_end, b, "file_alignment_padding", i)
            if payload_end != len(blob):
                tail = blob[payload_end:]
                r["alignment_padding"] = dict(size=len(tail), hex=tail.hex(),
                    byte_counts=dict(collections.Counter(tail)),
                    aligned_end=(a+payload_end+4095)//4096*4096 == len(data))
        elif len(blob) == 8:
            r.update(kind="sequence", pairs=pairs(blob))
            require(r["pairs"][0][0] == 1, f"sequence {i}: unexpected first tag")
            segment(a, b, "sequence_pairs", i)
        else:
            require(len(blob) % 2 == 0, f"resource {i}: odd size")
            words = list(struct.unpack(f"<{len(blob)//2}H", blob))
            require(words[0] == 0xffff and words[-3:] == [0xffff]*3,
                    f"resource {i}: unexpected RGB-like framing")
            require((len(words)-4) % 3 == 0 and all(w <= 255 for w in words[1:-3]),
                    f"resource {i}: invalid RGB-like channels")
            frames = [words[j:j+3] for j in range(1, len(words)-3, 3)]
            r.update(kind="led_candidate", frame_count=len(frames), frames=frames,
                     start_marker=words[0], end_marker=words[-3:])
            segment(a, a+2, "led_start_marker", i)
            segment(a+2, b-6, "led_channel_triples", i)
            segment(b-6, b, "led_end_marker", i)
        resources.append(r)
    medals = [dict(row=i+1, pairs=pairs(blobs[1][i*36:(i+1)*36])) for i in range(988)]
    refs, builtins = [], collections.defaultdict(list)
    for owner, ps in [("root", resources[0]["pairs"])] + [
            (f"medal_row_{m['row']}", m["pairs"]) for m in medals] + [
            (f"sequence_{r['id']}", r["pairs"]) for r in resources if r["kind"] == "sequence"]:
        for slot, (tag, val) in enumerate(ps):
            require(tag in [0, 1, 0xfffe, 0xffff], f"{owner}/{slot}: unknown tag")
            if tag == 1:
                require(val < count, f"{owner}/{slot}: bad reference")
                target = resources[val]
                refs.append(dict(owner=owner, slot=slot, target=val, kind=target["kind"]))
            elif tag == 0:
                builtins[val].append(dict(owner=owner, slot=slot))
            else:
                require(val == tag, f"{owner}/{slot}: irregular marker")
    # Independently reconstruct from parsed fields, not by copying whole resources.
    chunks = [MAGIC, struct.pack("<HIIHHHH", flag, base, end, count, flag2, check, flag3),
              data[50:512], struct.pack(f"<{count}I", *addresses)]
    for r in resources:
        kind = r["kind"]
        if kind in ("root", "sequence"):
            chunks.append(b"".join(struct.pack("<HH", *p) for p in r["pairs"]))
        elif kind == "medal_table":
            chunks.append(b"".join(struct.pack("<HH", *p) for m in medals for p in m["pairs"]))
        elif kind == "led_candidate":
            w = [r["start_marker"]] + [v for f in r["frames"] for v in f] + r["end_marker"]
            chunks.append(struct.pack(f"<{len(w)}H", *w))
        else:
            h = r["header"]
            chunks.append(b"AU" + struct.pack("<HHHII8H", *(h[k] for k in audio_fields)))
            a = r["offset"]
            chunks.append(data[a+32:a+r["asset_bytes"]])
            chunks.append(bytes.fromhex(r.get("alignment_padding", {}).get("hex", "")))
    rebuilt = b"".join(chunks)
    require(rebuilt == data, "lossless rebuild failed")
    require(segments[0]["start"] == 0 and segments[-1]["end"] == len(data)
            and all(a["end"] == b["start"] for a, b in zip(segments, segments[1:])),
            "byte coverage gap or overlap")
    return dict(size=len(data), sha256=sha(data), header=dict(flag_20=flag,
                base_word_address=base, end_word_address=end, resource_count=count,
                flag_2c=flag2, checksum_u16=check, flag_30=flag3,
                reserved_32_3f_hex=data[50:64].hex(),
                reserved_40_1ff_hex=data[64:512].hex()),
                version_related_builtin=resources[0]["pairs"][11][1],
                inferred_version=resources[0]["pairs"][11][1]-0x40,
                resources=resources, medals=medals, references=refs,
                builtin_ids={str(k): v for k, v in sorted(builtins.items())},
                byte_segments=segments,
                validation=dict(byte_coverage=1.0, lossless_rebuild=True,
                                additive_checksum_valid=True, reference_bounds_valid=True))


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def decode_job(job):
    name, data, r = job
    folder = OUT / name / "audio"
    folder.mkdir(exist_ok=True)
    target = folder / f"res{r['id']:03d}.wav"
    lut = bytes(int(f"{i:08b}"[::-1], 2) for i in range(256))
    a = r["offset"]
    payload = data[a+32:a+r["asset_bytes"]].translate(lut)
    with tempfile.TemporaryDirectory(prefix="yki-audio-") as tmp:
        inp, pcm = Path(tmp)/"audio.bin", Path(tmp)/"audio.pcm"
        inp.write_bytes(payload)
        completed = subprocess.run([str(ROOT/"third_party/local/work/dec/dec2"), str(inp), str(pcm), "40"],
                                   capture_output=True, check=True)
        raw = pcm.read_bytes()
    require(len(raw) == r["header"]["decoded_samples_expected"] * 2,
            f"{name}/{r['id']}: wrong decoded sample count")
    with wave.open(str(target), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(raw)
    return dict(version=name, resource=r["id"], samples=len(raw)//2,
                wav=str(target.relative_to(ROOT)), pcm_sha256=sha(raw))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--decode-audio", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    analyses, datas, jobs = [], [], []
    for path in sorted((ROOT/"yki").glob("*.yki")):
        data = path.read_bytes()
        x = parse(data)
        x["file"] = path.name
        folder = OUT/path.stem
        folder.mkdir(exist_ok=True)
        write_json(folder/"decoded.json", x)
        with (folder/"medal_pairs.csv").open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["row"] + [f"p{i}_{k}" for i in range(9) for k in ["tag", "value"]])
            writer.writerows([m["row"]]+[v for p in m["pairs"] for v in p] for m in x["medals"])
        with (folder/"led_frames.csv").open("w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["resource", "frame", "channel_0", "channel_1", "channel_2"])
            for r in x["resources"]:
                if r["kind"] == "led_candidate":
                    writer.writerows([r["id"], i]+frame for i, frame in enumerate(r["frames"]))
                elif r["kind"] == "audio":
                    jobs.append((path.stem, data, r))
        analyses.append(x)
        datas.append(data)
        print(path.name, len(x["resources"]), "resources, lossless rebuild/checksum/coverage OK", flush=True)
    summary = dict(versions=[], unknowns=[
        "The exact device meaning of constant header flags and reserved patterns.",
        "Whether root pair 11 encodes update identity or selects the version announcement.",
        "The names, waveforms and control behavior of built-in IDs; target watch ROM unavailable.",
        "Actual execution order, branch behavior, and FFFE/FFFF handling on the watch.",
        "LED physical channel order, tick interval, synchronization, repeat behavior.",
        "Device semantics of constant Audio32 flags/type fields.",
        "The physical medal code to row conversion routine; not established by file structure.",
        "Bit-exact equivalence of the existing software audio decoder to the watch decoder."])
    for x in analyses:
        stats = []
        for slot in range(9):
            c = collections.Counter(tuple(m["pairs"][slot]) for m in x["medals"])
            stats.append(dict(slot=slot, tags=dict(collections.Counter(t for (t,v),num in c.items()
                         for _ in range(num))), unique_pairs=len(c),
                         most_common=[dict(tag=p[0], value=p[1], count=n) for p,n in c.most_common(8)],
                         reference_kinds=dict(collections.Counter(r["kind"] for r in x["references"]
                             if r["owner"].startswith("medal_") and r["slot"]==slot))))
        summary["versions"].append(dict(file=x["file"], size=x["size"], sha256=x["sha256"],
             header=x["header"], inferred_version=x["inferred_version"],
             resource_kinds=dict(collections.Counter(r["kind"] for r in x["resources"])),
             builtins=len(x["builtin_ids"]), medal_slot_statistics=stats,
             validation=x["validation"]))
    # Semantic stability: local references are compared by target asset hash.
    def normalized(x, ps):
        result=[]
        for tag,val in ps:
            if tag==1:
                r=x["resources"][val]
                if r["kind"]=="sequence":
                    result.append((tag, r["kind"], normalized(x,r["pairs"])))
                else:
                    result.append((tag,r["kind"],r.get("asset_sha256",r["raw_sha256"])))
            else:
                result.append((tag,val))
        return tuple(result)
    summary["cross_version"] = dict(
        raw_equal_medal_rows=sum(len({tuple(tuple(p) for p in x["medals"][i]["pairs"]) for x in analyses})==1
                                 for i in range(988)),
        normalized_equal_medal_rows=sum(len({normalized(x,x["medals"][i]["pairs"]) for x in analyses})==1
                                        for i in range(988)),
        adjacent=[])
    for a,b in zip(analyses,analyses[1:]):
        summary["cross_version"]["adjacent"].append(dict(
            before=a["file"], after=b["file"],
            raw_changed_rows=[i+1 for i in range(988) if a["medals"][i]["pairs"]!=b["medals"][i]["pairs"]],
            normalized_changed_rows=[i+1 for i in range(988)
                if normalized(a,a["medals"][i]["pairs"])!=normalized(b,b["medals"][i]["pairs"])]))
    # LED/audio lengths provide a timing hypothesis, not a clock measurement.
    timings=[]
    for x in analyses:
        for r in x["resources"]:
            if r["kind"] != "sequence": continue
            (tag,led),(atag,audio)=r["pairs"]
            require(x["resources"][led]["kind"]=="led_candidate", "bad sequence LED target")
            if atag==1:
                ar=x["resources"][audio]
                require(ar["kind"]=="audio", "bad sequence audio target")
                frames=x["resources"][led]["frame_count"]
                seconds=ar["header"]["duration_seconds"]
                timings.append(dict(version=x["file"],sequence=r["id"],led=led,audio=audio,
                                    led_frames=frames,audio_seconds=seconds,
                                    implied_hz=frames/seconds,
                                    residual_at_51_2_hz=frames-seconds*51.2))
    summary["led_audio_timing_hypothesis"] = dict(rows=timings,
        note="Frame counts suggest roughly 51.3 Hz for many sequences; not measured. Exact tick interval and physical channel order remain unknown.")
    unique_timings = {(r['led_frames'], r['audio_seconds']) for r in timings}
    summary['led_audio_timing_hypothesis']['candidate_rates'] = [dict(
        hz=hz, sum_absolute_frame_residuals=sum(abs(n-t*hz) for n,t in unique_timings))
        for hz in [50, 51.2, 1000/19.5, 51.3]]
    summary['asset_common_all_versions'] = {}
    for kind in ['led_candidate', 'audio']:
        sets = [{r.get('asset_sha256', r['raw_sha256']) for r in x['resources']
                 if r['kind']==kind} for x in analyses]
        summary['asset_common_all_versions'][kind] = len(set.intersection(*sets))
    # Corruption checks target failures that would otherwise silently misclassify bytes.
    mutations=[]
    data=datas[0]
    for name,offset in [("checksum",1000),("pointer",512),
                        ("audio_size",analyses[0]["resources"][-1]["offset"]+12),
                        ("led_channel",analyses[0]["resources"][2]["offset"]+3)]:
        corrupted=bytearray(data)
        corrupted[offset]^=1
        if name!="checksum":
            corrupted[46]=0
            corrupted[46]=(-sum(corrupted))%256
        try:
            parse(corrupted)
        except ValueError as e:
            mutations.append(dict(test=name,rejected=True,reason=str(e)))
        else:
            raise AssertionError(f"corruption accepted: {name}")
    summary["corruption_checks"]=mutations
    summary['reference_inventory'] = [dict(file=x['file'],
        local_reference_count=len(x['references']),
        unreferenced_assets=[r['id'] for r in x['resources'] if r['id']>1
            and r['id'] not in {ref['target'] for ref in x['references']}],
        special_marker_rows=[m['row'] for m in x['medals'] if m['pairs'][0]==[65534,65534]])
        for x in analyses]
    if args.decode_audio:
        with ThreadPoolExecutor(max_workers=4) as pool:
            decoded=list(pool.map(decode_job,jobs))
        write_json(OUT/"audio_decode_manifest.json",decoded)
        summary["audio_decode"]=dict(count=len(decoded), all_sample_counts_valid=True,
            decoder="Existing third_party/local/work/dec/dec2, full bit-reversed payload; device equivalence unverified")
        print("decoded",len(decoded),"complete audio payloads",flush=True)
        old_diff=[]
        for x in analyses:
            folder=ROOT/'outputs/yki_audio'/Path(x['file']).stem
            for r in x['resources']:
                if r['kind']!='audio': continue
                old=list(folder.glob(f"au*_0x{r['offset']:x}.wav"))
                if len(old)!=1: continue
                new=OUT/Path(x['file']).stem/'audio'/f"res{r['id']:03d}.wav"
                with wave.open(str(old[0])) as w: prev=w.readframes(w.getnframes())
                with wave.open(str(new)) as w: now=w.readframes(w.getnframes())
                old_diff.append(dict(file=x['file'],resource=r['id'],different=prev!=now,
                                     same_except_final_frame=prev[:-640]==now[:-640],
                                     same_sample_count=len(prev)==len(now)))
        write_json(OUT/'previous_audio_comparison.json',old_diff)
        summary['audio_decode']['previous_comparison']=dict(compared=len(old_diff),
            different=sum(r['different'] for r in old_diff),
            same_except_final_frame=all(r['same_except_final_frame'] for r in old_diff),
            same_sample_count=all(r['same_sample_count'] for r in old_diff))
    write_json(OUT/"summary.json",summary)
    print("cross-version:", {k:v for k,v in summary['cross_version'].items() if k!='adjacent'},flush=True)
    print("corruption checks:",mutations,flush=True)


if __name__ == "__main__":
    main()
