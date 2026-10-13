import array
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
from .format import ROOT

BIT_REVERSE = bytes(int(f"{i:08b}"[::-1], 2) for i in range(256))


def command(args):
    try:
        return subprocess.run([str(a) for a in args], check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise ValueError(f"required executable not found: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        raise ValueError(f"{args[0]} failed: {exc.stderr.decode(errors='replace')[-2000:]}") from exc


def native_codec():
    src = ROOT / "third_party/local/work/libg7221/src"
    names = ["encoder.c", "encoderf.c", "decoder.c", "decoderf.c", "sam2coef.c", "coef2sam.c",
             "commonf.c", "bitstream.c", "dct4.c", "tables.c", "huff_tab.c", "utilities.c"]
    wrapper = ROOT / "packages/custom-legacy/native/codec.c"
    files = [wrapper, ROOT/"third_party/local/work/dec/dct4.h"] + [src/n for n in names]
    files += sorted(src.glob("*.h")) + sorted((src/"g722_1").glob("*.h"))
    cc = shutil.which("cc")
    if not cc:
        raise ValueError("audio encoding requires a C compiler (cc)")
    digest = hashlib.sha256(cc.encode()+b"".join(f.read_bytes() for f in files)).hexdigest()[:16]
    cache = ROOT / "packages/custom-legacy/.cache"
    cache.mkdir(exist_ok=True)
    executable = cache / f"codec-{digest}"
    if not executable.exists():
        with tempfile.TemporaryDirectory(dir=cache) as temp:
            output = Path(temp)/"codec"
            command([cc,"-O2","-I",src,"-I",ROOT/"third_party/local/work/dec",wrapper,
                     *(src/n for n in names),"-lm","-o",output])
            output.replace(executable)
    return executable


def pcm_values(raw):
    values = array.array("h")
    values.frombytes(raw)
    import sys
    if sys.byteorder != "little":
        values.byteswap()
    return values


class AudioEncoder:
    def __init__(self, temp, warn):
        self.temp = Path(temp)
        self.warn = warn
        self._codec = None
        self._reference_cache = {}
        self.records = []

    def codec(self):
        if self._codec is None:
            self._codec = native_codec()
        return self._codec

    def decode(self, code):
        if not code or len(code)%40:
            raise ValueError("Audio32 payload must consist of complete 40-byte frames")
        inp, out = self.temp/"decode.g7221", self.temp/"decode.pcm"
        inp.write_bytes(code)
        command([self.codec(),"decode",inp,out])
        raw = out.read_bytes()
        if len(raw) != len(code)//40*640:
            raise ValueError("decoded sample count mismatch")
        return raw

    def measure(self, raw):
        inp = self.temp/"measure.pcm"
        inp.write_bytes(raw)
        stderr = command(["ffmpeg","-hide_banner","-nostats","-f","s16le","-ar","16000",
                          "-ac","1","-i",inp,"-af","loudnorm=print_format=json","-f","null","-"]).stderr.decode()
        result = json.loads(stderr[stderr.rfind("{"):stderr.rfind("}")+1])
        values = pcm_values(raw)
        peak = max(abs(v) for v in values)
        return dict(lufs=float(result["input_i"]), true_peak_dbtp=float(result["input_tp"]),
                    lra=float(result["input_lra"]), sample_peak=peak,
                    sample_peak_dbfs=20*math.log10(peak/32768) if peak else None)

    def reference(self, blob):
        key = hashlib.sha256(blob).hexdigest()
        if key not in self._reference_cache:
            self._reference_cache[key] = self.measure(self.decode(blob[32:].translate(BIT_REVERSE)))
        return self._reference_cache[key]

    def encode(self, path, options, reference=None):
        path = Path(path)
        if not path.is_file():
            raise ValueError(f"audio file not found: {path}")
        raw_path = self.temp/"input.pcm"
        command(["ffmpeg","-hide_banner","-loglevel","error","-y","-i",path,"-map","0:a:0",
                 "-ar","16000","-ac","1","-c:a","pcm_s16le","-f","s16le",raw_path])
        raw = raw_path.read_bytes()
        source_samples = len(raw)//2
        remainder = source_samples%320
        alignment = options.get("frameAlignment","trim")
        if remainder:
            if alignment == "error":
                raise ValueError(f"{path}: {source_samples} samples is not a multiple of 320")
            if alignment == "pad":
                raw += b"\0"*(2*(320-remainder))
            else:
                raw = raw[:len(raw)-2*remainder]
        if not raw:
            raise ValueError("audio is shorter than one 20 ms frame")
        if len(raw)>64000000:
            raise ValueError("PCM exceeds the native encoder's 64 MB per-audio limit")
        raw_path.write_bytes(raw)
        mode = options.get("volume","preserve")
        if mode == "match" and reference is None:
            raise ValueError("volume: match needs an existing local AU reference or referenceResource; built-in sound waveforms are unavailable")
        ref = self.reference(reference) if reference is not None and mode != "preserve" else None
        if mode == "peak" and ref and not ref["sample_peak"]:
            raise ValueError("cannot peak-match a silent reference")
        peak = max(abs(v) for v in pcm_values(raw))
        clipping = options.get("allowClipping",False)
        maximum_gain = 8.0 if clipping else (32767/peak if peak else 1.0)
        trials = []

        def trial(gain):
            filtered, code_path = self.temp/"filtered.pcm", self.temp/"encoded.g7221"
            if gain == 1:
                filtered.write_bytes(raw)
            else:
                command(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","s16le","-ar","16000",
                         "-ac","1","-i",raw_path,"-af",f"volume={gain:.9f}","-c:a","pcm_s16le",
                         "-f","s16le",filtered])
            if filtered.stat().st_size != len(raw):
                raise ValueError("volume conversion changed the PCM length")
            command([self.codec(),"encode",filtered,code_path])
            code = code_path.read_bytes()
            if len(code) != len(raw)//640*40:
                raise ValueError("encoded payload length mismatch")
            metrics = self.measure(self.decode(code))
            trials.append(dict(gain=gain, **metrics))
            return code, metrics

        if mode == "match":
            target = ref["lufs"]
            if not math.isfinite(target):
                raise ValueError("cannot loudness-match a silent reference")
            low, high = 0.0625, maximum_gain
            best = None
            for _ in range(9):
                gain = math.sqrt(low*high)
                code, metrics = trial(gain)
                if not math.isfinite(metrics["lufs"]):
                    raise ValueError("cannot loudness-match silent input audio")
                distance = abs(metrics["lufs"]-target)
                if best is None or distance < best[0]:
                    best = (distance, code, metrics, gain)
                if distance <= 0.05:
                    break
                if metrics["lufs"] < target:
                    low = gain
                else:
                    high = gain
            distance, code, metrics, gain = best
            if distance > 0.2:
                self.warn(f"{path.name}: loudness target {target:.2f} LUFS not reached ({metrics['lufs']:.2f}); allowClipping is {clipping}")
        else:
            gain = min(maximum_gain, ((ref["sample_peak"] if ref else 32767)/peak)) if mode == "peak" and peak else 1.0
            code, metrics = trial(gain)
        if clipping and gain*peak > 32767:
            self.warn(f"{path.name}: matching volume uses PCM full-scale saturation; waveform clipping is enabled explicitly")
        frames = len(code)//40
        if frames/50 > 47.56:
            self.warn(f"{path.name}: {frames/50:.2f}s exceeds the longest stock AU (47.56s); hardware duration limit is unknown")
        # Flags copy the constants found in all 1071 stock AU assets.
        header = b"AU" + struct.pack("<HHHII8H",16000,1600,1,frames,frames*20,
                                     0,0,0,0xFFFF,0,16,0xFFFF,0xFFFF)
        record = dict(file=str(path.resolve()), input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      frames=frames, duration_seconds=frames/50, source_samples=source_samples,
                      added_padding_samples=max(0,len(raw)//2-source_samples),
                      trimmed_samples=max(0,source_samples-len(raw)//2), volume_mode=mode,
                      gain_db=20*math.log10(gain), reference=ref, decoded=metrics, trials=trials)
        self.records.append(record)
        return header + code.translate(BIT_REVERSE), record
