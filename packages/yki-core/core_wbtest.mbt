///|
test "SHA-256 known vectors and hex" {
  assert_eq(
    sha256(b""),
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  )
  assert_eq(
    sha256(b"abc"),
    "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
  )
  assert_eq(
    sha256(b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
    "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
  )
  assert_eq(hex_decode("00AaFF"), b"\x00\xaa\xff")
  assert_eq(hex_encode(b"\x00\xaa\xff"), "00aaff")
}

///|
test "schema rejects Python bool-as-int pitfalls and typos" {
  validate_config({ "extends": 2, "overrides": [{ "id": "B655" }] })
  let bad : Array[Json] = [
    { "extends": 2, "overrides": [{ "id": true }] },
    { "extends": 2, "overrides": [{ "id": 1000 }] },
    { "extends": 2, "overrides": [{ "id": 655, "songSond": "a.mp3" }] },
    {
      "extends": 2,
      "overrides": [{ "id": 655, "type": "normal", "songSound": "a.mp3" }],
    },
    {
      "extends": 2,
      "overrides": [{ "id": 655, "led": { "frames": [[256, 0, 0]] } }],
    },
    {
      "extends": 2,
      "overrides": [{ "id": 655, "led": { "resource": 5, "repeat": true } }],
    },
  ]
  for value in bad {
    let rejected = try {
      validate_config(value)
      false
    } catch {
      _ => true
    }
    assert_true(rejected)
  }
}

///|
test "bump canonicalization and confidence" {
  let a = bump_mapping("E7BA")
  let b = bump_mapping("7ED5")
  assert_eq(get(a, "row"), (655).to_json())
  assert_eq(get(a, "confidence"), "high")
  assert_eq(a, b)
  assert_eq(get(bump_mapping("F12A"), "confidence"), "low")
  let rejected = try {
    ignore(bump_mapping("000A"))
    false
  } catch {
    _ => true
  }
  assert_true(rejected)
}

///|
test "audio framing, bit reversal and LED bounds" {
  let b = Bytes::makei(256, i => i.to_byte())
  assert_eq(reverse_bits(reverse_bits(b)), b)
  let au = make_au(Bytes::make(40, 1))
  assert_eq(au.length(), 72)
  assert_eq(u16(au, 2), 16000)
  assert_eq(u32(au, 8), 1)
  assert_eq(u32(au, 12), 20)
  assert_eq(au[32], (128).to_byte())
  let host : Host = fn(_r) raise YkiError {
    raise YkiError("host should not be invoked")
  }
  assert_eq(led_frames({ "frames": [[1, 2, 3]], "repeat": 2 }, host), [
    [1, 2, 3],
    [1, 2, 3],
  ])
  let rejected = try {
    ignore(led_frames({ "frames": [[999, 2, 3]] }, host))
    false
  } catch {
    _ => true
  }
  assert_true(rejected)
}
