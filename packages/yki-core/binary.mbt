///|
pub(all) suberror YkiError {
  YkiError(String)
} derive(Debug)

///|
fn require(ok : Bool, message : String) -> Unit raise YkiError {
  if !ok {
    raise YkiError(message)
  }
}

///|
fn u16(b : Bytes, p : Int) -> Int {
  b[p].to_int() | (b[p + 1].to_int() << 8)
}

///|
fn u32(b : Bytes, p : Int) -> Int {
  u16(b, p) | (u16(b, p + 2) << 16)
}

///|
fn put16(b : FixedArray[Byte], p : Int, n : Int) -> Unit {
  b[p] = n.to_byte()
  b[p + 1] = (n >> 8).to_byte()
}

///|
fn put32(b : FixedArray[Byte], p : Int, n : Int) -> Unit {
  put16(b, p, n)
  put16(b, p + 2, n >> 16)
}

///|
fn cut(b : Bytes, start : Int, end : Int) -> Bytes {
  Bytes::makei(end - start, i => b[start + i])
}

///|
fn copy_bytes(dst : FixedArray[Byte], pos : Int, src : Bytes) -> Unit {
  for i in 0..<src.length() {
    dst[pos + i] = src[i]
  }
}

///|
pub fn hex_encode(b : Bytes) -> String {
  let out = StringBuilder::new()
  let digits = "0123456789abcdef"
  for byte in b {
    let n = byte.to_int()
    out.write_char(digits[n >> 4].to_char().unwrap())
    out.write_char(digits[n & 15].to_char().unwrap())
  }
  out.to_string()
}

///|
fn digit(c : Int) -> Int {
  if c >= 48 && c <= 57 {
    c - 48
  } else if c >= 65 && c <= 70 {
    c - 55
  } else if c >= 97 && c <= 102 {
    c - 87
  } else {
    -1
  }
}

///|
pub fn hex_decode(s : String) -> Bytes raise YkiError {
  require(s.length() % 2 == 0, "hex must have an even length")
  let b = FixedArray::make(s.length() / 2, (0).to_byte())
  for i in 0..<b.length() {
    let a = digit(s[2 * i].to_int())
    let z = digit(s[2 * i + 1].to_int())
    require(a >= 0 && z >= 0, "invalid hex")
    b[i] = ((a << 4) | z).to_byte()
  }
  Bytes::from_array(b[:])
}

///|
pub(all) struct Pair {
  tag : Int
  value : Int
} derive(Eq, ToJson, Debug)

///|
pub(all) enum Kind {
  Root
  MedalTable
  Led
  Sequence
  Audio
} derive(Eq, Debug)

///|
pub(all) struct Asset {
  kind : Kind
  blob : Bytes
  pairs : Array[Pair]
}

///|
pub struct Image {
  priv header : Bytes
  root : Array[Pair]
  rows : Array[Array[Pair]]
  assets : Array[Asset]
  priv padding : Bytes
  priv original_rows : Array[Array[Pair]]
  mut mapping : Array[Int]
}

///|
fn read_pairs(b : Bytes) -> Array[Pair] {
  Array::makei(b.length() / 4, i => {
    tag: u16(b, i * 4),
    value: u16(b, i * 4 + 2),
  })
}

///|
fn check_pairs(ps : Array[Pair], count : Int) -> Unit raise YkiError {
  for p in ps {
    match p.tag {
      0 => ()
      1 =>
        require(
          p.value >= 0 && p.value < count,
          "reference outside resource table",
        )
      65534 | 65535 => require(p.value == p.tag, "irregular marker")
      _ => raise YkiError("unknown pair tag")
    }
  }
}

///|
pub fn parse(data : Bytes) -> Image raise YkiError {
  let n = data.length()
  require(n >= 512 && n % 4096 == 0, "invalid file size")
  require(
    cut(data, 0, 32) == b"BandaiYokai3rd******************",
    "invalid magic",
  )
  let mut sum = 0
  for byte in data {
    sum = (sum + byte.to_int()) & 255
  }
  require(sum == 0, "invalid additive checksum")
  let base = u32(data, 34)
  require(base == 0x500800, "unsupported base address")
  require(
    u32(data, 38) == base + n / 2,
    "end address disagrees with file length",
  )
  let count = u16(data, 42)
  require(count > 2 && 512 + count * 4 < n, "invalid resource count")
  let offsets = Array::makei(count, i => (u32(data, 512 + i * 4) - base) * 2)
  require(offsets[0] == 512 + 4 * count, "unexpected gap after pointer table")
  for i in 0..<count {
    require(offsets[i] >= 512 && offsets[i] < n, "pointer outside file")
    if i > 0 {
      require(offsets[i - 1] < offsets[i], "non-monotonic pointers")
    }
  }
  require(offsets[1] - offsets[0] == 120, "invalid root size")
  require(offsets[2] - offsets[1] == 988 * 36, "invalid medal table size")
  let assets : Array[Asset] = []
  let mut padding = b""
  for i in 0..<count {
    let blob = cut(
      data,
      offsets[i],
      if i + 1 == count {
        n
      } else {
        offsets[i + 1]
      },
    )
    let kind = if i == 0 {
      Root
    } else if i == 1 {
      MedalTable
    } else if blob.length() >= 2 && blob[0] == b'A' && blob[1] == b'U' {
      Audio
    } else if blob.length() == 8 {
      Sequence
    } else {
      Led
    }
    let mut actual = blob
    let ps = if kind == Root || kind == Sequence {
      read_pairs(blob)
    } else {
      []
    }
    match kind {
      Audio => {
        require(blob.length() >= 32, "truncated AU header")
        require(
          u16(blob, 2) == 16000 &&
          u16(blob, 4) == 1600 &&
          u16(blob, 6) == 1 &&
          u16(blob, 26) == 16,
          "unsupported AU header",
        )
        let frames = u32(blob, 8)
        require(
          frames >= 0 &&
          frames <= (blob.length() - 32) / 40 &&
          u32(blob, 12) == frames * 20,
          "AU frame/payload size mismatch",
        )
        let end = 32 + frames * 40
        require(i == count - 1 || end == blob.length(), "AU extra bytes")
        actual = cut(blob, 0, end)
        if i == count - 1 {
          padding = cut(blob, end, blob.length())
        }
      }
      Sequence => require(ps[0].tag == 1, "sequence: unexpected first tag")
      Led => {
        require(
          blob.length() >= 8 && (blob.length() - 8) % 6 == 0,
          "invalid LED size",
        )
        require(u16(blob, 0) == 65535, "invalid LED start marker")
        for j in ((blob.length() - 6) / 2)..<(blob.length() / 2) {
          require(u16(blob, j * 2) == 65535, "invalid LED end marker")
        }
        for j in 1..<((blob.length() - 6) / 2) {
          require(u16(blob, j * 2) <= 255, "invalid LED channel")
        }
      }
      _ => ()
    }
    assets.push({ kind, blob: actual, pairs: ps })
  }
  let table = assets[1].blob
  let rows = Array::makei(988, i => read_pairs(cut(table, i * 36, (i + 1) * 36)))
  for row in rows {
    check_pairs(row, count)
  }
  for a in assets {
    check_pairs(a.pairs, count)
  }
  {
    header: cut(data, 0, 512),
    root: assets[0].pairs.copy(),
    rows,
    assets,
    padding,
    original_rows: rows.map(r => r.copy()),
    mapping: [],
  }
}

///|
pub fn Image::append(
  self : Image,
  kind : Kind,
  blob? : Bytes = b"",
  pairs? : Array[Pair] = [],
) -> Pair {
  self.assets.push({ kind, blob, pairs })
  { tag: 1, value: self.assets.length() - 1 }
}

///|
pub fn Image::kind(self : Image, p : Pair) -> Kind? {
  if p.tag == 1 && p.value >= 0 && p.value < self.assets.length() {
    Some(self.assets[p.value].kind)
  } else {
    None
  }
}

///|
pub fn Image::audio_pair(self : Image, p : Pair) -> Pair {
  if self.kind(p) == Some(Sequence) {
    self.assets[p.value].pairs[1]
  } else {
    p
  }
}

///|
pub fn Image::audio_blob(self : Image, p : Pair) -> Bytes? {
  let p = self.audio_pair(p)
  if self.kind(p) == Some(Audio) {
    Some(self.assets[p.value].blob)
  } else {
    None
  }
}

///|
pub fn Image::row_type(self : Image, row : Array[Pair]) -> String {
  if self.kind(row[1]) == Some(Sequence) ||
    row[0] == { tag: 65534, value: 65534 } {
    "song"
  } else {
    "normal"
  }
}

///|
pub fn Image::active(_self : Image, row : Array[Pair]) -> Bool {
  [0, 1, 2, 4].any(i => row[i].tag == 0 || row[i].tag == 1)
}

///|
fn kind_order(k : Kind) -> Int {
  match k {
    Root => 0
    MedalTable => 1
    Led => 2
    Sequence => 3
    Audio => 4
  }
}

///|
fn pair_bytes(ps : Array[Pair], mapping : Array[Int]) -> Bytes raise YkiError {
  let b = FixedArray::make(ps.length() * 4, (0).to_byte())
  for i, p in ps {
    require(
      p.tag >= 0 && p.tag <= 65535 && p.value >= 0 && p.value <= 65535,
      "pair exceeds u16",
    )
    if p.tag == 1 {
      require(p.value < mapping.length(), "bad stable handle")
    }
    put16(b, i * 4, p.tag)
    put16(b, i * 4 + 2, if p.tag == 1 { mapping[p.value] } else { p.value })
  }
  Bytes::from_array(b[:])
}

///|
pub fn Image::serialize(self : Image) -> Bytes raise YkiError {
  require(
    self.rows.length() == 988 && self.root.length() == 30,
    "invalid root or medal row count",
  )
  for row in self.rows {
    require(row.length() == 9, "invalid medal row size")
  }
  let count = self.assets.length()
  require(count <= 65535, "too many resources")
  let order = Array::makei(count, i => i)
  order.sort_by((a, b) => {
    let d = kind_order(self.assets[a].kind) - kind_order(self.assets[b].kind)
    if d == 0 {
      a - b
    } else {
      d
    }
  })
  let mapping = Array::make(count, 0)
  for i, handle in order {
    mapping[handle] = i
  }
  self.mapping = mapping
  let blobs : Array[Bytes] = []
  let mut cursor = 512 + 4 * count
  let offsets : Array[Int] = []
  for handle in order {
    let a = self.assets[handle]
    let blob = match a.kind {
      Root => pair_bytes(self.root, mapping)
      MedalTable => {
        let b = FixedArray::make(988 * 36, (0).to_byte())
        for i, row in self.rows {
          copy_bytes(b, i * 36, pair_bytes(row, mapping))
        }
        Bytes::from_array(b[:])
      }
      Sequence => pair_bytes(a.pairs, mapping)
      _ => a.blob
    }
    require(blob.length() % 2 == 0, "odd resource size")
    offsets.push(cursor)
    require(
      cursor <= 0x7fffffff - blob.length() - 4095,
      "YKI exceeds address limit",
    )
    cursor += blob.length()
    blobs.push(blob)
  }
  let size = (cursor + 4095) / 4096 * 4096
  require(
    size > 0 && size <= 0x7fffffff - 0x500800 * 2,
    "YKI exceeds address limit",
  )
  let data = FixedArray::make(size, (0).to_byte())
  copy_bytes(data, 0, self.header)
  put32(data, 38, 0x500800 + size / 2)
  put16(data, 42, count)
  put16(data, 46, 0)
  for i, blob in blobs {
    put32(data, 512 + i * 4, 0x500800 + offsets[i] / 2)
    copy_bytes(data, offsets[i], blob)
  }
  let pad_size = size - cursor
  if pad_size == self.padding.length() {
    copy_bytes(data, cursor, self.padding)
  } else {
    for i in 0..<pad_size {
      data[cursor + i] = if self.padding.length() >= 8 {
        self.padding[i % 8]
      } else {
        (255).to_byte()
      }
    }
    if pad_size >= 2 {
      put16(data, size - 2, 0)
    }
  }
  let mut sum = 0
  for b in data {
    sum = (sum + b.to_int()) & 255
  }
  put16(data, 46, (256 - sum) & 255)
  let result = Bytes::from_array(data[:])
  ignore(parse(result))
  result
}
