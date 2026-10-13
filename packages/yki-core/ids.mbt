///|
let fields : Array[(String, Int)] = [
  ("summonSound", 0),
  ("tribeSound", 2),
  ("nameSound", 4),
  ("introSound", 5),
  ("postSound", 6),
  ("callSound", 8),
]

///|
let empty : Pair = { tag: 65535, value: 65535 }

///|
fn reverse_nibble(n : Int) -> Int {
  ((n & 1) << 3) | ((n & 2) << 1) | ((n & 4) >> 1) | ((n & 8) >> 3)
}

///|
fn bump_mapping(value : Json) -> Json raise YkiError {
  let ns : Array[Int] = []
  match value {
    String(s) => {
      let s = if s.has_prefix("0x") || s.has_prefix("0X") {
        s[2:].to_owned()
      } else {
        s
      }
      require(s.length() == 4, "bumpsHex must have all four nibbles")
      for c in s.code_units() {
        let d = digit(c.to_int())
        require(d >= 0, "invalid bumps hex")
        ns.push(d)
      }
    }
    Array(a) => {
      require(
        a.length() == 4,
        "bumps must be four strings of four binary digits",
      )
      for s in a {
        let s = text(s)
        require(matches_pattern(s, "^[01]{4}$"), "invalid bump binary row")
        let mut n = 0
        for c in s.code_units() {
          n = n * 2 + c.to_int() - 48
        }
        ns.push(n)
      }
    }
    _ => raise YkiError("unsupported bump format")
  }
  if ns[3] == 5 {
    for i in 0..<4 {
      ns[i] = reverse_nibble(ns[i])
    }
  }
  require(ns[3] == 10, "terminal bump row must be 1010 or mirrored 0101")
  let rail = hex_encode(
      Bytes::makei(2, i => {
        if i == 0 {
          ((ns[0] << 4) | ns[1]).to_byte()
        } else {
          ((ns[2] << 4) | 10).to_byte()
        }
      }),
    )[:3]
    .to_owned()
    .to_upper()
  let lookup = parse_json(bump_lookup_json)
  let evidence = get(parse_json(bump_evidence_json), rail)
  let mut confidence = "low"
  let row = if has(lookup, rail) {
    confidence = if get(evidence, "physical_printed_B_verified") is True {
      "high"
    } else {
      "medium"
    }
    integer(get(lookup, rail))
  } else {
    let mut rank = 0
    let mut found = -1
    for x in 1..<16 {
      if x == 5 || x == 10 || x == ns[0] {
        continue
      }
      for y in 1..<16 {
        if y == 5 || y == 10 || y == ns[0] || y == x {
          continue
        }
        if x == ns[1] && y == ns[2] {
          found = rank
        }
        rank += 1
      }
    }
    require(found >= 0, "no known bump-to-row mapping for \{rail}A")
    let n = match ns[0] {
      15 => 725 + found
      12 => if found < 100 { 361 + found } else { -1 }
      9 | 11 | 13 => {
        let candidate = (if ns[0] == 9 {
            -41
          } else if ns[0] == 11 {
            49
          } else {
            139
          }) +
          found
        if (ns[1] > 4 || (ns[1] == 4 && ns[2] >= 14)) &&
          candidate >= 1 &&
          candidate <= 240 {
          candidate
        } else {
          -1
        }
      }
      _ => -1
    }
    require(n >= 1, "no known bump-to-row mapping for \{rail}A")
    n
  }
  let rows = ns.map(n => {
    let sb = StringBuilder::new()
    for i in 0..<4 {
      sb.write_char(if (n & (1 << (3 - i))) != 0 { '1' } else { '0' })
    }
    Json::string(sb.to_string())
  })
  {
    "row": row.to_json(),
    "confidence": confidence.to_json(),
    "rail_hex": rail.to_json(),
    "canonical_rows": rows.to_json(),
    "evidence": if evidence != Json::null() {
      evidence
    } else {
      {
        "kind": if confidence == "low" {
          "unverified block formula; not a proven general conversion"
        } else {
          "legacy source lookup; provenance not fully audited"
        },
      }
    },
  }
}

///|
pub fn resolve_id(
  value : Json,
  image : Image,
  warn : (String) -> Unit,
  strict? : Bool = false,
) -> Json raise YkiError {
  let explicit = (n : Int, source : String) => {
    Json::object({
      "row": n.to_json(),
      "confidence": "explicit",
      "source": source.to_json(),
    })
  }
  let result = match value {
    Number(_, ..) => explicit(integer(value), "medal row")
    String(s) =>
      if is_b_number(s) {
        let mut n = 0
        for c in s[1:].to_owned().code_units() {
          n = n * 10 + c.to_int() - 48
        }
        explicit(n, "medal B number")
      } else {
        bump_mapping(value)
      }
    Array(_) => bump_mapping(value)
    Object(_) =>
      if has(value, "medal") && !has(value, "sound") {
        explicit(integer(get(value, "medal")), "medal row")
      } else if has(value, "bumpsHex") {
        bump_mapping(get(value, "bumpsHex"))
      } else if has(value, "bumps") {
        bump_mapping(get(value, "bumps"))
      } else if has(value, "sound") {
        let field = str_default(value, "field", "nameSound")
        let sound_namespace = str_default(value, "namespace", "builtin")
        require(
          sound_namespace == "builtin" || sound_namespace == "resource",
          "invalid sound sound_namespace",
        )
        let tag = if sound_namespace == "resource" { 1 } else { 0 }
        let sound = integer(get(value, "sound"))
        let hits : Array[Int] = []
        for i, row in image.rows {
          let pair = if field == "songSound" {
            if image.kind(row[1]) != Some(Sequence) {
              continue
            }
            image.audio_pair(row[1])
          } else {
            let slots = fields.filter(p => p.0 == field)
            require(slots.length() == 1, "unknown sound field")
            image.audio_pair(row[slots[0].1])
          }
          if pair == { tag, value: sound } &&
            (!has(value, "medal") || integer(get(value, "medal")) == i + 1) {
            hits.push(i + 1)
          }
        }
        let hits_text = hits.map(n => n.to_string()).join(", ")
        require(
          hits.length() == 1,
          "internal sound ID \{sound} matches rows [\{hits_text}]; specify id.medal to disambiguate",
        )
        {
          "row": hits[0].to_json(),
          "confidence": "exact-existing-reference",
          "source": "internal sound ID",
          "sound": sound.to_json(),
          "namespace": sound_namespace.to_json(),
          "field": field.to_json(),
        }
      } else {
        raise YkiError("unsupported ID")
      }
    _ => raise YkiError("unsupported ID")
  }
  let row = integer(get(result, "row"))
  require(row >= 1 && row <= 988, "medal row must be between 1 and 988")
  let confidence = text(get(result, "confidence"))
  if confidence == "low" || confidence == "medium" {
    let rail = get(result, "rail_hex").stringify()
    let evidence = get(result, "evidence").stringify()
    let message = "ID mapping \{rail} → B\{row} has \{confidence} confidence: \{evidence}"
    require(!strict, message)
    warn(message)
  }
  result
}
