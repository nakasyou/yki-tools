///|
pub fn led_frames(
  value : Json,
  host : Host,
) -> Array[Array[Int]] raise YkiError {
  let value = match value {
    String(path) => parse_json(@utf8.decode_lossy(load(host, path).view()))
    Array(_) => Json::object({ "frames": value })
    _ => value
  }
  let m = object(value)
  require(
    m.keys().all(k => k == "frames" || k == "repeat") && has(value, "frames"),
    "LED JSON must have frames and optional repeat",
  )
  let frames = array(get(value, "frames"))
  let repeat = int_default(value, "repeat", 1)
  require(
    frames.length() > 0 && repeat >= 1 && repeat <= 1024,
    "LED frames must be nonempty and repeat must be 1..1024",
  )
  require(
    frames.length() <= 1000000 / repeat,
    "LED expansion exceeds one million frames",
  )
  let fs : Array[Array[Int]] = []
  for frame in frames {
    let a = array(frame)
    require(a.length() == 3, "LED frame needs three integer channels in 0..255")
    let f = a.map(integer)
    require(
      f.all(n => n >= 0 && n <= 255),
      "LED frame needs three integer channels in 0..255",
    )
    fs.push(f)
  }
  Array::makei(fs.length() * repeat, i => fs[i % fs.length()].copy())
}

///|
fn make_led(
  image : Image,
  value : Json,
  host : Host,
  warn : (String) -> Unit,
) -> Pair raise YkiError {
  if has(value, "resource") {
    let index = integer(get(value, "resource"))
    require(
      index >= 0 &&
      index < image.assets.length() &&
      image.assets[index].kind == Led,
      "LED resource is not an RGB-like asset",
    )
    let repeat = int_default(value, "repeat", 1)
    require(repeat >= 1 && repeat <= 1024, "LED repeat must be 1..1024")
    if repeat == 1 {
      return { tag: 1, value: index }
    }
    let blob = image.assets[index].blob
    let count = (blob.length() - 8) / 6
    require(
      count > 0 && count <= 1000000 / repeat,
      "LED expansion exceeds one million frames",
    )
    warn(
      "LED resource \{index}: repeating \{count} frames \{repeat} times; tick period and hardware behavior remain unverified",
    )
    return image.append(
      Led,
      blob=cut(blob, 0, 2) +
        cut(blob, 2, blob.length() - 6).repeat(repeat) +
        cut(blob, blob.length() - 6, blob.length()),
    )
  }
  let frames = if value is Null { [[0, 0, 0]] } else { led_frames(value, host) }
  warn(
    "custom LED uses raw channels; RGB physical order and tick period remain unverified",
  )
  let b = FixedArray::make(8 + frames.length() * 6, (255).to_byte())
  for i, f in frames {
    for j in 0..<3 {
      put16(b, 2 + i * 6 + j * 2, f[j])
    }
  }
  image.append(Led, blob=Bytes::from_array(b[:]))
}

///|
pub(all) struct BuildResult {
  data : Bytes
  manifest : Json
  warnings : Array[String]
}

///|
fn source_path(config : Json) -> String raise YkiError {
  match get(config, "extends") {
    Number(_, ..) => "@stock/Ver\{integer(get(config,"extends"))}_U.yki"
    String(s) => s
    _ => raise YkiError("invalid extends")
  }
}

///|
pub fn build(
  config : Json,
  host : Host,
  strict? : Bool = false,
) -> BuildResult raise YkiError {
  validate_config(config)
  let source = source_path(config)
  let input = load(host, source)
  let image = parse(input)
  let warnings : Array[String] = []
  let warn = (s : String) => warnings.push(s)
  let strict = strict || get(config, "mappingPolicy") == "strict"
  let resolutions : Array[Json] = []
  let changes : Array[Json] = []
  let records : Array[Json] = []
  if has(config, "version") {
    let version = integer(get(config, "version"))
    image.root[11] = { tag: 0, value: 64 + version }
    if ![0, 2, 3, 4, 5, 6, 7].contains(version) {
      warn("version \{version}: spoken output is unverified")
    }
  }
  let sound = fn(value : Json, old : Pair) -> Pair raise YkiError {
    if value is Null {
      return empty
    }
    if has(value, "builtin") {
      return { tag: 0, value: integer(get(value, "builtin")) }
    }
    if has(value, "resource") {
      let i = integer(get(value, "resource"))
      require(
        i >= 0 && i < image.assets.length() && image.assets[i].kind == Audio,
        "sound resource is not an AU asset",
      )
      return { tag: 1, value: i }
    }
    let options = if has(config, "audio") {
      object(get(config, "audio")).copy()
    } else {
      Map([])
    }
    if value is Object(_) {
      for k, v in object(value) {
        if k != "file" {
          options[k] = v
        }
      }
    }
    let mut reference = image.audio_blob(old)
    if options.contains("referenceResource") {
      let i = integer(options["referenceResource"])
      require(
        i >= 0 && i < image.assets.length() && image.assets[i].kind == Audio,
        "referenceResource is not an AU asset",
      )
      reference = Some(image.assets[i].blob)
    }
    let path = match value {
      String(s) => s
      _ => text(get(value, "file"))
    }
    let encoded = encode_audio(path, options.to_json(), reference, host, warn)
    let p = image.append(Audio, blob=encoded.blob)
    object(encoded.record)["asset_handle"] = p.value.to_json()
    records.push(encoded.record)
    p
  }
  for index, edit in array(get(config, "overrides")) {
    let resolved = resolve_id(get(edit, "id"), image, warn, strict~)
    resolutions.push(resolved)
    let number = integer(get(resolved, "row"))
    let previous = image.rows[number - 1].copy()
    let is_new = !image.active(previous)
    let mut requested_type = str_default(edit, "type", image.row_type(previous))
    let converting = requested_type != image.row_type(previous)
    require(
      !is_new || has(edit, "type"),
      "B\{number}: new medal rows require type: normal or song",
    )
    let row = if has(edit, "template") {
      let template = integer(
        get(resolve_id(get(edit, "template"), image, warn, strict~), "row"),
      )
      let row = image.rows[template - 1].copy()
      require(image.active(row), "B\{template} is not an active template")
      if !has(edit, "type") {
        requested_type = image.row_type(row)
      } else {
        require(
          image.row_type(row) == requested_type,
          "template type does not match edit.type",
        )
      }
      row
    } else if is_new || requested_type != image.row_type(previous) {
      let template = if requested_type == "song" { 655 } else { 1 }
      let row = image.original_rows[template - 1].copy()
      if requested_type == "song" {
        require(
          image.kind(row[1]) == Some(Sequence),
          "base has no known B655 song template",
        )
      }
      for i in [4, 6, 8] {
        row[i] = empty
      }
      row
    } else {
      previous.copy()
    }
    let required = if requested_type == "song" {
      "songSound"
    } else {
      "nameSound"
    }
    if converting && !has(edit, "template") {
      require(
        get(edit, required) != Json::null(),
        "B\{number}: type conversion requires \{required} or an explicit template",
      )
    }
    if is_new {
      require(
        get(edit, required) != Json::null(),
        "B\{number}: new \{requested_type} medals require \{required}",
      )
      warn(
        "new B\{number} row initialized; physical bump recognition depends on watch conversion",
      )
    }
    require(
      requested_type != "normal" || !has(edit, "songSound"),
      "songSound is only valid for type: song",
    )
    for entry in fields {
      let (field, slot) = entry
      if !has(edit, field) {
        continue
      }
      let old = row[slot]
      let replacement = sound(get(edit, field), image.audio_pair(old))
      row[slot] = if image.kind(old) == Some(Sequence) && replacement != empty {
        image.append(Sequence, pairs=[
          image.assets[old.value].pairs[0],
          replacement,
        ])
      } else {
        replacement
      }
    }
    if requested_type == "song" && (has(edit, "songSound") || has(edit, "led")) {
      let old = row[1]
      require(
        image.kind(old) == Some(Sequence),
        "song edit needs an existing song template",
      )
      let ps = image.assets[old.value].pairs
      let audio = if has(edit, "songSound") {
        sound(get(edit, "songSound"), ps[1])
      } else {
        ps[1]
      }
      if audio == empty {
        require(!has(edit, "led"), "cannot attach LED data to a null songSound")
        row[1] = empty
      } else {
        let led = if has(edit, "led") {
          make_led(image, get(edit, "led"), host, warn)
        } else {
          ps[0]
        }
        row[1] = image.append(Sequence, pairs=[led, audio])
      }
    } else if requested_type == "normal" && has(edit, "led") {
      let audio = image.audio_pair(row[0])
      if get(edit, "led") is Null {
        row[0] = audio
      } else {
        require(
          audio.tag == 0 || audio.tag == 1,
          "normal medal LED needs summonSound or a template with a summon reference",
        )
        row[0] = image.append(Sequence, pairs=[
          make_led(image, get(edit, "led"), host, warn),
          audio,
        ])
      }
    }
    image.rows[number - 1] = row
    changes.push({
      "override_index": index.to_json(),
      "medal_row": number.to_json(),
      "type": requested_type.to_json(),
      "new": is_new.to_json(),
      "previous_pairs": pairs_json(previous),
      "edited_pairs_stable_handles": pairs_json(row),
    })
  }
  let data = image.serialize()
  let output = parse(data)
  for change in changes {
    object(change)["output_pairs"] = pairs_json(
      output.rows[integer(get(change, "medal_row")) - 1],
    )
  }
  for record in records {
    let handle = integer(get(record, "asset_handle"))
    let resource = image.mapping[handle]
    object(record)["resource"] = resource.to_json()
    require(
      output.assets[resource].blob == image.assets[handle].blob,
      "saved AU differs from encoded AU",
    )
  }
  let mapping : Map[String, Json] = Map([])
  for i, v in image.mapping {
    mapping[i.to_string()] = v.to_json()
  }
  let manifest : Json = {
    "source": source.to_json(),
    "source_sha256": sha256(input).to_json(),
    "output_sha256": sha256(data).to_json(),
    "size": data.length().to_json(),
    "version_spoken_id": output.root[11].value.to_json(),
    "version": (output.root[11].value - 64).to_json(),
    "version_semantics": "spoken version selection; firmware compatibility identity is not proven",
    "resolutions": resolutions.to_json(),
    "overrides": changes.to_json(),
    "audio": records.to_json(),
    "resource_count": output.assets.length().to_json(),
    "handle_to_output_resource": mapping.to_json(),
    "validation": validation(),
    "hardware_tested": false,
    "warnings": warnings.to_json(),
    "notes": [
      "Existing assets are retained; edited references use copy-on-write.", "LED stops after audio on tested shortened B655 song; other paths unverified.",
    ],
  }
  { data, manifest, warnings }
}

///|
fn pairs_json(ps : Array[Pair]) -> Json {
  ps.map(p => [p.tag, p.value]).to_json()
}

///|
fn validation() -> Json {
  {
    "byte_coverage": 1.0,
    "lossless_rebuild": true,
    "additive_checksum_valid": true,
    "reference_bounds_valid": true,
  }
}

///|
pub fn inspect(data : Bytes) -> Json raise YkiError {
  let image = parse(data)
  let kinds : Map[String, Json] = Map([])
  for asset in image.assets {
    let name = match asset.kind {
      Root => "root"
      MedalTable => "medal_table"
      Led => "led_candidate"
      Sequence => "sequence"
      Audio => "audio"
    }
    kinds[name] = (integer(kinds.get(name).unwrap_or((0).to_json())) + 1).to_json()
  }
  {
    "size": data.length().to_json(),
    "sha256": sha256(data).to_json(),
    "version": (image.root[11].value - 64).to_json(),
    "version_spoken_id": image.root[11].value.to_json(),
    "resources": kinds.to_json(),
    "active_name_rows": image.rows
    .filter(r => r[4].tag == 0 || r[4].tag == 1)
    .length()
    .to_json(),
    "validation": validation(),
  }
}

///|
pub fn validate(
  config : Json,
  host : Host,
  strict? : Bool = false,
) -> Json raise YkiError {
  validate_config(config)
  let source = source_path(config)
  let image = parse(load(host, source))
  let strict = strict || get(config, "mappingPolicy") == "strict"
  let warnings : Array[String] = []
  let warn = (s : String) => warnings.push(s)
  let ids : Array[Json] = []
  for o in array(get(config, "overrides")) {
    ids.push(resolve_id(get(o, "id"), image, warn, strict~))
    if has(o, "template") {
      ignore(resolve_id(get(o, "template"), image, warn, strict~))
    }
    for field in fields.map(p => p.0) + ["songSound"] {
      let value = get(o, field)
      if value is String(_) || has(value, "file") {
        ignore(
          load(
            host,
            match value {
              String(s) => s
              _ => text(get(value, "file"))
            },
          ),
        )
      }
    }
    let led = get(o, "led")
    if has(o, "led") && led != Json::null() && !has(led, "resource") {
      ignore(led_frames(led, host))
    }
  }
  {
    "schema_valid": true,
    "base": source.to_json(),
    "resolutions": ids.to_json(),
    "warnings": warnings.to_json(),
    "encoded": false,
  }
}
