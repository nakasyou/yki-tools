///|
/// Generate a printable medal's OpenSCAD source without host capabilities.
pub fn generate_medal(
  bits : String,
  mode? : String = "normal",
  orientation? : String = "canonical",
  mirror? : Bool = false,
) -> Json raise YkiError {
  require(
    mode == "normal" || mode == "classic" || mode == "lite",
    "モードはnormal、classic、liteのいずれかにしてください",
  )
  require(
    orientation == "canonical" || orientation == "physical",
    "向きはcanonicalまたはphysicalにしてください",
  )
  let digits : Array[String] = []
  for c in bits.code_units() {
    match c.to_int() {
      48 => digits.push("0")
      49 => digits.push("1")
      // Python's whitespace separators, including Unicode whitespace.
      9
      | 10
      | 11
      | 12
      | 13
      | 28
      | 29
      | 30
      | 31
      | 32
      | 44
      | 45
      | 47
      | 95
      | 133
      | 160
      | 5760
      | 8192
      | 8193
      | 8194
      | 8195
      | 8196
      | 8197
      | 8198
      | 8199
      | 8200
      | 8201
      | 8202
      | 8232
      | 8233
      | 8239
      | 8287
      | 12288 => ()
      _ =>
        raise YkiError(
          "16桁の0/1、または4桁×4行を指定してください",
        )
    }
  }
  require(
    digits.length() == 16,
    "16桁の0/1、または4桁×4行を指定してください",
  )
  let reverse = (orientation == "canonical") != mirror
  let rows = Array::makei(4, row => {
    let start = row * 4
    if reverse {
      digits[start + 3] + digits[start + 2] + digits[start + 1] + digits[start]
    } else {
      digits[start] + digits[start + 1] + digits[start + 2] + digits[start + 3]
    }
  })
  let mut source = "// Generated bits (top to bottom, left to right): " +
    rows.join("/") +
    "\n" +
    medal_template[0]
  for i in 0..<4 {
    source += "code\{i + 1} = \"\{rows[i]}\";" + medal_template[i + 1]
  }
  source += "mode = \"\{mode}\";" + medal_template[5]
  {
    "source": source.to_json(),
    "rows": rows.to_json(),
    "mode": mode.to_json(),
    "filename": ("medal_" + rows.join("") + "_" + mode + ".scad").to_json(),
  }
}
