///|
fn object(j : Json) -> Map[String, Json] raise YkiError {
  match j {
    Object(m) => m
    _ => raise YkiError("expected object")
  }
}

///|
fn array(j : Json) -> Array[Json] raise YkiError {
  match j {
    Array(a) => a
    _ => raise YkiError("expected array")
  }
}

///|
fn text(j : Json) -> String raise YkiError {
  match j {
    String(s) => s
    _ => raise YkiError("expected string")
  }
}

///|
fn integer(j : Json) -> Int raise YkiError {
  match j {
    Number(n, ..) => {
      require(
        n >= -2147483648.0 && n <= 2147483647.0 && n == n.to_int().to_double(),
        "expected integer",
      )
      n.to_int()
    }
    _ => raise YkiError("expected integer")
  }
}

///|
fn get(j : Json, key : String) -> Json {
  match j {
    Object(m) => m.get(key).unwrap_or(Json::null())
    _ => Json::null()
  }
}

///|
fn has(j : Json, key : String) -> Bool {
  match j {
    Object(m) => m.contains(key)
    _ => false
  }
}

///|
fn str_default(
  j : Json,
  key : String,
  fallback : String,
) -> String raise YkiError {
  if has(j, key) {
    text(get(j, key))
  } else {
    fallback
  }
}

///|
fn int_default(j : Json, key : String, fallback : Int) -> Int raise YkiError {
  if has(j, key) {
    integer(get(j, key))
  } else {
    fallback
  }
}

///|
fn decimal(j : Json) -> Double raise YkiError {
  match j {
    Number(n, ..) => n
    _ => raise YkiError("expected number")
  }
}

///|
fn json_bytes(j : Json) -> Bytes raise YkiError {
  hex_decode(text(j))
}

///|
fn parse_json(s : String) -> Json raise YkiError {
  @json.parse(s) catch {
    e => raise YkiError(e.to_string())
  }
}

///|
fn is_b_number(s : String) -> Bool {
  s.length() >= 2 &&
  s.length() <= 4 &&
  (s[0].to_int() == 66 || s[0].to_int() == 98) &&
  s[1:].to_owned().all(c => c >= '0' && c <= '9')
}

///|
fn matches_pattern(s : String, pattern : String) -> Bool {
  match pattern {
    "^[Bb][0-9]{1,3}$" => is_b_number(s)
    "^(0[xX])?[0-9a-fA-F]{4}$" => {
      let s = if s.has_prefix("0x") || s.has_prefix("0X") {
        s[2:].to_owned()
      } else {
        s
      }
      s.length() == 4 && s.code_units().all(c => digit(c.to_int()) >= 0)
    }
    "^[01]{4}$" => s.length() == 4 && s.all(c => c == '0' || c == '1')
    "\\.[yY][kK][iI]$" => s.to_lower().has_suffix(".yki")
    _ => false
  }
}

///|
fn schema_matches(value : Json, schema : Json, root : Json) -> Bool {
  try {
    validate_schema(value, schema, root)
    true
  } catch {
    _ => false
  }
}

///|
fn validate_schema(
  value : Json,
  schema : Json,
  root : Json,
) -> Unit raise YkiError {
  if has(schema, "$ref") {
    let reference = text(get(schema, "$ref"))
    let name = reference[8:].to_owned()
    validate_schema(value, get(get(root, "$defs"), name), root)
    return
  }
  if has(schema, "oneOf") {
    let mut hits = 0
    for choice in array(get(schema, "oneOf")) {
      if schema_matches(value, choice, root) {
        hits += 1
      }
    }
    require(
      hits == 1,
      "configuration does not match exactly one permitted shape",
    )
  }
  if has(schema, "type") {
    let ok = match text(get(schema, "type")) {
      "object" => value is Object(_)
      "array" => value is Array(_)
      "string" => value is String(_)
      "boolean" => value is True || value is False
      "null" => value is Null
      "integer" =>
        match value {
          Number(n, ..) =>
            n >= -2147483648.0 &&
            n <= 2147483647.0 &&
            n == n.to_int().to_double()
          _ => false
        }
      _ => false
    }
    require(ok, "JSON schema: unexpected value type")
  }
  if has(schema, "enum") {
    require(
      array(get(schema, "enum")).contains(value),
      "JSON schema: invalid enum value",
    )
  }
  if has(schema, "const") {
    require(value == get(schema, "const"), "JSON schema: unexpected constant")
  }
  if has(schema, "not") {
    require(
      !schema_matches(value, get(schema, "not"), root),
      "JSON schema: forbidden shape",
    )
  }
  match value {
    Object(m) => {
      let props = get(schema, "properties")
      if has(schema, "required") {
        for key in array(get(schema, "required")) {
          require(
            m.contains(text(key)),
            "JSON schema: missing required field \{text(key)}",
          )
        }
      }
      for key, v in m {
        if has(props, key) {
          validate_schema(v, get(props, key), root)
        } else if get(schema, "additionalProperties") is False {
          raise YkiError("JSON schema: unknown field \{key}")
        }
      }
    }
    Array(a) => {
      if has(schema, "minItems") {
        require(
          a.length() >= integer(get(schema, "minItems")),
          "JSON schema: too few items",
        )
      }
      if has(schema, "maxItems") {
        require(
          a.length() <= integer(get(schema, "maxItems")),
          "JSON schema: too many items",
        )
      }
      if has(schema, "items") {
        for v in a {
          validate_schema(v, get(schema, "items"), root)
        }
      }
    }
    String(s) => {
      if has(schema, "minLength") {
        require(
          s.length() >= integer(get(schema, "minLength")),
          "JSON schema: empty string",
        )
      }
      if has(schema, "pattern") {
        require(
          matches_pattern(s, text(get(schema, "pattern"))),
          "JSON schema: string pattern mismatch",
        )
      }
    }
    Number(n, ..) => {
      if has(schema, "minimum") {
        require(
          n >= decimal(get(schema, "minimum")),
          "JSON schema: below minimum",
        )
      }
      if has(schema, "maximum") {
        require(
          n <= decimal(get(schema, "maximum")),
          "JSON schema: above maximum",
        )
      }
    }
    _ => ()
  }
  if has(schema, "allOf") {
    for rule in array(get(schema, "allOf")) {
      if has(rule, "if") {
        if schema_matches(value, get(rule, "if"), root) && has(rule, "then") {
          validate_schema(value, get(rule, "then"), root)
        }
      } else {
        validate_schema(value, rule, root)
      }
    }
  }
}

///|
pub fn validate_config(config : Json) -> Unit raise YkiError {
  let schema = parse_json(schema_json)
  validate_schema(config, schema, schema)
}

///|
pub fn schema() -> Json raise YkiError {
  parse_json(schema_json)
}
