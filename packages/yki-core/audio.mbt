///|
/// External I/O and media primitives. All configuration, framing, volume search,
/// AU construction, validation and relocation stay in MoonBit.
pub type Host = (Json) -> Json raise YkiError

///|
fn host_call(host : Host, request : Json) -> Json raise YkiError {
  let result = host(request)
  if has(result, "error") {
    raise YkiError(text(get(result, "error")))
  }
  result
}

///|
fn load(host : Host, path : String) -> Bytes raise YkiError {
  json_bytes(
    get(host_call(host, { "op": "read", "path": path.to_json() }), "hex"),
  )
}

///|
fn measure(host : Host, b : Bytes) -> Json raise YkiError {
  let values = host_call(host, {
    "op": "measure",
    "hex": hex_encode(b).to_json(),
  })
  let peak = sample_peak(b)
  let m = object(values)
  m["sample_peak"] = peak.to_json()
  m["sample_peak_dbfs"] = if peak == 0 {
    Json::null()
  } else {
    (20.0 * @math.log10(peak.to_double() / 32768.0)).to_json()
  }
  values
}

///|
fn sample_peak(b : Bytes) -> Int {
  let mut peak = 0
  for i in 0..<(b.length() / 2) {
    let n = u16(b, 2 * i)
    let n = if n >= 32768 { n - 65536 } else { n }
    let n = if n < 0 { -n } else { n }
    if n > peak {
      peak = n
    }
  }
  peak
}

///|
pub fn reverse_bits(b : Bytes) -> Bytes {
  Bytes::makei(b.length(), i => {
    let mut n = b[i].to_int()
    let mut v = 0
    for _ in 0..<8 {
      v = (v << 1) | (n & 1)
      n = n >> 1
    }
    v.to_byte()
  })
}

///|
pub fn decode_audio(blob : Bytes, _host : Host) -> Bytes raise YkiError {
  require(
    blob.length() >= 32 && blob[0] == b'A' && blob[1] == b'U',
    "not an AU asset",
  )
  let count = u32(blob, 8)
  require(
    count > 0 &&
    count <= (blob.length() - 32) / 40 &&
    blob.length() == 32 + count * 40,
    "invalid AU payload",
  )
  let pcm = decode_g7221(reverse_bits(cut(blob, 32, blob.length())))
  require(pcm.length() == count * 640, "decoded sample count mismatch")
  pcm
}

///|
pub fn make_au(payload : Bytes) -> Bytes raise YkiError {
  require(
    payload.length() > 0 && payload.length() % 40 == 0,
    "Audio32 payload must consist of complete 40-byte frames",
  )
  let frames = payload.length() / 40
  let b = FixedArray::make(32, (0).to_byte())
  b[0] = b'A'
  b[1] = b'U'
  put16(b, 2, 16000)
  put16(b, 4, 1600)
  put16(b, 6, 1)
  put32(b, 8, frames)
  put32(b, 12, frames * 20)
  put16(b, 22, 65535)
  put16(b, 26, 16)
  put16(b, 28, 65535)
  put16(b, 30, 65535)
  Bytes::from_array(b[:]) + reverse_bits(payload)
}

///|
pub(all) struct EncodedAudio {
  blob : Bytes
  record : Json
}

///|
pub fn encode_audio(
  path : String,
  options : Json,
  reference : Bytes?,
  host : Host,
  warn : (String) -> Unit,
) -> EncodedAudio raise YkiError {
  let config_schema = schema()
  validate_schema(
    options,
    get(get(config_schema, "$defs"), "audioOptions"),
    config_schema,
  )
  let source_digest = sha256(load(host, path))
  let input = host_call(host, { "op": "transcode", "path": path.to_json() })
  let original = json_bytes(get(input, "hex"))
  require(original.length() % 2 == 0, "PCM must be s16le")
  let source_samples = original.length() / 2
  let remainder = source_samples % 320
  let alignment = str_default(options, "frameAlignment", "trim")
  let raw = if remainder == 0 {
    original
  } else if alignment == "error" {
    raise YkiError("\{source_samples} samples is not a multiple of 320")
  } else if alignment == "pad" {
    original + Bytes::make(2 * (320 - remainder), 0)
  } else {
    cut(original, 0, original.length() - 2 * remainder)
  }
  require(raw.length() > 0, "audio is shorter than one 20 ms frame")
  require(raw.length() <= 64000000, "PCM exceeds 64 MB per-audio limit")
  let mode = str_default(options, "volume", "preserve")
  require(
    mode != "match" || reference is Some(_),
    "volume: match needs an existing local AU reference or referenceResource; built-in sound waveforms are unavailable",
  )
  let reference_metrics = match reference {
    Some(b) =>
      if mode != "preserve" {
        measure(host, decode_audio(b, host))
      } else {
        Json::null()
      }
    None => Json::null()
  }
  if mode == "peak" && reference_metrics != Json::null() {
    require(
      integer(get(reference_metrics, "sample_peak")) > 0,
      "cannot peak-match a silent reference",
    )
  }
  let peak = sample_peak(raw)
  let clipping = get(options, "allowClipping") is True
  let maximum_gain = if clipping {
    8.0
  } else if peak > 0 {
    32767.0 / peak.to_double()
  } else {
    1.0
  }
  let trials : Array[Json] = []
  let trial = fn(gain : Double) -> (Bytes, Json) raise YkiError {
    let filtered = if gain == 1.0 {
      raw
    } else {
      json_bytes(
        get(
          host_call(host, {
            "op": "gain",
            "hex": hex_encode(raw).to_json(),
            "gain": gain.to_json(),
          }),
          "hex",
        ),
      )
    }
    require(
      filtered.length() == raw.length(),
      "volume conversion changed the PCM length",
    )
    let code = encode_g7221(filtered)
    require(
      code.length() == raw.length() / 640 * 40,
      "encoded payload length mismatch",
    )
    let decoded = decode_g7221(code)
    require(decoded.length() == raw.length(), "decoded sample count mismatch")
    let metrics = measure(host, decoded)
    let t = object(metrics).copy()
    t["gain"] = gain.to_json()
    trials.push(t.to_json())
    (code, metrics)
  }
  let mut gain = 1.0
  let mut code = b""
  let mut metrics = Json::null()
  if mode == "match" {
    require(
      get(reference_metrics, "lufs") != Json::null(),
      "cannot loudness-match a silent reference",
    )
    let target = decimal(get(reference_metrics, "lufs"))
    let mut low = 0.0625
    let mut high = maximum_gain
    let mut best = 1.0e100
    for _ in 0..<9 {
      let g = (low * high).sqrt()
      let (c, m) = trial(g)
      require(
        get(m, "lufs") != Json::null(),
        "cannot loudness-match silent input audio",
      )
      let lufs = decimal(get(m, "lufs"))
      let distance = (lufs - target).abs()
      if distance < best {
        best = distance
        code = c
        metrics = m
        gain = g
      }
      if distance <= 0.05 {
        break
      }
      if lufs < target {
        low = g
      } else {
        high = g
      }
    }
    if best > 0.2 {
      warn("\{path}: loudness target not reached; allowClipping is \{clipping}")
    }
  } else {
    if mode == "peak" && peak > 0 {
      let target = if reference_metrics != Json::null() {
        integer(get(reference_metrics, "sample_peak")).to_double()
      } else {
        32767.0
      }
      gain = (target / peak.to_double()).min(maximum_gain)
    }
    let (c, m) = trial(gain)
    code = c
    metrics = m
  }
  if clipping && gain * peak.to_double() > 32767.0 {
    warn("\{path}: waveform clipping is enabled explicitly")
  }
  let frames = code.length() / 40
  if frames > 2378 {
    warn(
      "\{path}: duration exceeds longest stock AU; hardware duration limit is unknown",
    )
  }
  let record : Json = {
    "file": path.to_json(),
    "input_sha256": source_digest.to_json(),
    "frames": frames.to_json(),
    "duration_seconds": (frames.to_double() / 50.0).to_json(),
    "source_samples": source_samples.to_json(),
    "added_padding_samples": (raw.length() / 2 - source_samples)
    .max(0)
    .to_json(),
    "trimmed_samples": (source_samples - raw.length() / 2).max(0).to_json(),
    "volume_mode": mode.to_json(),
    "gain_db": (20.0 * @math.log10(gain)).to_json(),
    "reference": reference_metrics,
    "decoded": metrics,
    "trials": trials.to_json(),
  }
  { blob: make_au(code), record }
}

///|
/// Raw MSB-first Siren7 profile payload (AU reverses each byte separately).
pub fn encode_g7221(pcm : Bytes) -> Bytes raise YkiError {
  @g7221.encode(pcm) catch {
    @g7221.InvalidInput(message) => raise YkiError(message)
  }
}

///|
pub fn decode_g7221(payload : Bytes) -> Bytes raise YkiError {
  @g7221.decode(payload) catch {
    @g7221.InvalidInput(message) => raise YkiError(message)
  }
}
