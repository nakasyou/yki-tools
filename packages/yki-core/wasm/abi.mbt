///|
priv struct Bridge {
  mut input : FixedArray[Byte]
  mut output : Bytes
  mut host_request : Bytes
  mut host_response : FixedArray[Byte]
}

///|
let bridge : Bridge = {
  input: [],
  output: b"",
  host_request: b"",
  host_response: [],
}

///|
extern "wasm" fn host_rpc() -> Int = "yki_host" "rpc"

///|
fn write(b : FixedArray[Byte], offset : Int, word : Int) -> Unit {
  if offset >= 0 && offset < b.length() {
    for i in 0..<4 {
      if offset + i < b.length() {
        b[offset + i] = (word >> (i * 8)).to_byte()
      }
    }
  }
}

///|
fn read(b : Bytes, offset : Int) -> Int {
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
pub fn input_begin(length : Int) -> Int {
  if length < 0 || length > 256000000 {
    return -1
  }
  bridge.input = FixedArray::make(length, (0).to_byte())
  bridge.output = b""
  0
}

///|
pub fn input_write(offset : Int, word : Int) -> Unit {
  write(bridge.input, offset, word)
}

///|
pub fn output_length() -> Int {
  bridge.output.length()
}

///|
pub fn output_read(offset : Int) -> Int {
  read(bridge.output, offset)
}

///|
pub fn host_request_length() -> Int {
  bridge.host_request.length()
}

///|
pub fn host_request_read(offset : Int) -> Int {
  read(bridge.host_request, offset)
}

///|
pub fn host_response_begin(length : Int) -> Int {
  if length < 0 || length > 256000000 {
    return -1
  }
  bridge.host_response = FixedArray::make(length, (0).to_byte())
  0
}

///|
pub fn host_response_write(offset : Int, word : Int) -> Unit {
  write(bridge.host_response, offset, word)
}

///|
fn host(value : Json) -> Json raise @core.YkiError {
  bridge.host_request = @utf8.encode(value.stringify())
  bridge.host_response = []
  let status = host_rpc()
  if status != 0 {
    raise @core.YkiError("host callback failed")
  }
  @json.parse(
    @utf8.decode_lossy(Bytes::from_array(bridge.host_response[:]).view()),
  ) catch {
    e => raise @core.YkiError(e.to_string())
  }
}

///|
pub fn invoke() -> Int {
  let result : Json = try {
    let value = @json.parse(
      @utf8.decode_lossy(Bytes::from_array(bridge.input[:]).view()),
    )
    @core.request(value, host)
  } catch {
    @core.YkiError(s) => { "error": s.to_json() }
    e => { "error": e.to_string().to_json() }
  }
  bridge.output = @utf8.encode(result.stringify())
  bridge.input = []
  bridge.host_request = b""
  bridge.host_response = []
  if result is { "error": _, .. } {
    1
  } else {
    0
  }
}
