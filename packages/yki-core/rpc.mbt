///|
/// JSON entrypoint shared by the WASM adapter and other MoonBit hosts.
pub fn request(value : Json, host : Host) -> Json raise YkiError {
  match text(get(value, "op")) {
    "generate_medal" =>
      generate_medal(
        text(get(value, "bits")),
        mode=str_default(value, "mode", "normal"),
        orientation=str_default(value, "orientation", "canonical"),
        mirror=if has(value, "mirror") {
          match get(value, "mirror") {
            True => true
            False => false
            _ => raise YkiError("mirror must be a boolean")
          }
        } else {
          false
        },
      )
    "g7221_encode" =>
      {
        "hex": hex_encode(encode_g7221(json_bytes(get(value, "hex")))).to_json(),
      }
    "g7221_decode" =>
      {
        "hex": hex_encode(decode_g7221(json_bytes(get(value, "hex")))).to_json(),
      }
    "schema" => schema()
    "validate_config" => {
      validate_config(get(value, "config"))
      { "schema_valid": true }
    }
    "inspect" => inspect(json_bytes(get(value, "hex")))
    "describe" => describe(json_bytes(get(value, "hex")))
    "extract" => {
      let image = parse(json_bytes(get(value, "hex")))
      let resource = integer(get(value, "resource"))
      require(
        resource >= 0 && resource < image.assets.length(),
        "resource outside table",
      )
      { "hex": hex_encode(image.assets[resource].blob).to_json() }
    }
    "roundtrip" => {
      let image = parse(json_bytes(get(value, "hex")))
      { "hex": hex_encode(image.serialize()).to_json() }
    }
    "resolve" => {
      let image = parse(json_bytes(get(value, "hex")))
      let warnings : Array[String] = []
      let resolved = resolve_id(
        get(value, "id"),
        image,
        s => warnings.push(s),
        strict=get(value, "strict") is True,
      )
      { "resolution": resolved, "warnings": warnings.to_json() }
    }
    "build" => {
      let result = build(
        get(value, "config"),
        host,
        strict=get(value, "strict") is True,
      )
      { "hex": hex_encode(result.data).to_json(), "manifest": result.manifest }
    }
    "validate" =>
      validate(get(value, "config"), host, strict=get(value, "strict") is True)
    "decode" =>
      {
        "hex": hex_encode(decode_audio(json_bytes(get(value, "hex")), host)).to_json(),
      }
    _ => raise YkiError("unknown operation")
  }
}

///|
pub fn describe(data : Bytes) -> Json raise YkiError {
  let image = parse(data)
  let rows = image.rows.mapi((i, row) => {
    "id": (i + 1).to_json(),
    "type": image.row_type(row).to_json(),
    "active": image.active(row).to_json(),
    "pairs": pairs_json(row),
  })
  let resources = image.assets.mapi((id, asset) => {
    let kind = match asset.kind {
      Root => "root"
      MedalTable => "medal_table"
      Led => "led"
      Sequence => "sequence"
      Audio => "audio"
    }
    let record : Map[String, Json] = {
      "id": id.to_json(),
      "kind": kind.to_json(),
      "bytes": asset.blob.length().to_json(),
      "pairs": pairs_json(asset.pairs),
    }
    if asset.kind == Audio {
      record["frames"] = u32(asset.blob, 8).to_json()
      record["duration"] = (u32(asset.blob, 8).to_double() / 50.0).to_json()
    }
    if asset.kind == Led {
      record["frames"] = ((asset.blob.length() - 8) / 6).to_json()
    }
    record.to_json()
  })
  {
    "summary": inspect(data),
    "rows": rows.to_json(),
    "resources": resources.to_json(),
  }
}
