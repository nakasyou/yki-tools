///|
priv struct Bridge {
  mut input : FixedArray[Byte]
  mut output : Bytes
}

///|
let bridge : Bridge = { input: [], output: b"", }

///|
fn write(b : FixedArray[Byte], offset : Int32, word : Int32) -> Unit {
  if offset >= 0 && offset < b.length() {
    for i in 0..<4 {
      if offset + i < b.length() {
        b[offset + i] = (word >> (i * 8)).to_byte()
      }
    }
  }
}

///|
fn read(b : Bytes, offset : Int32) -> Int32 {
  let mut word = 0
  if offset >= 0 && offset < b.length() {
    for i in 0..<4 {
      if offset + i < b.length() {
        word = word | (b[offset + i].to_int() << (i * 8))
      }
    }
  }
  word
}

///|
pub fn input_begin(length : Int32) -> Int32 {
  if length < 0 || length > 256000000 {
    return -1
  }
  bridge.input = FixedArray::make(length, (0).to_byte())
  bridge.output = b""
  0
}

///|
pub fn input_write(offset : Int32, word : Int32) -> Unit {
  write(bridge.input, offset, word)
}

///|
pub fn output_length() -> Int32 {
  bridge.output.length()
}

///|
pub fn output_read(offset : Int32) -> Int32 {
  read(bridge.output, offset)
}

///|
pub fn invoke() -> Int32 {
  let result : Json = try {
    let value = @json.parse(
      @utf8.decode_lossy(Bytes::from_array(bridge.input[:]).view()),
    )
    @three_d.request(value)
  } catch {
    @three_d.ThreeDError(s) => { "error": s.to_json() }
    e => { "error": e.to_string().to_json() }
  }
  bridge.output = @utf8.encode(result.stringify())
  bridge.input = []
  if result is { "error": _, .. } {
    1
  } else {
    0
  }
}
