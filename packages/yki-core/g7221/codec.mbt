///|
/// YKI's Siren7 / G.722.1-derived profile: mono 16 kHz, 16 kbps, 320 samples.
/// The signal processing and bitstream implementation are entirely MoonBit.
/// Tables and interoperability rules are documented in README.md.
pub suberror CodecError {
  InvalidInput(String)
} derive(Debug)

///|
fn clamp(n : Int, lo : Int, hi : Int) -> Int {
  n.max(lo).min(hi)
}

///|
/// Five radix-two stages followed by 10-point DCT-IV kernels and rotations.
/// Float intermediates deliberately round to IEEE 754 binary32.
fn transform(input : Array[Float]) -> Array[Float] {
  let mut a = input.copy()
  let mut b = Array::make(320, (0.0 : Float))
  for stage in 0..<5 {
    let span = 320 >> stage
    for base in 0..<(1 << stage) {
      let p = base * span
      for i in 0..<(span / 2) {
        let x = a[p + 2 * i]
        let y = a[p + 2 * i + 1]
        b[p + i] = x + y
        b[p + span - 1 - i] = x - y
      }
    }
    let tmp = a
    a = b
    b = tmp
  }
  for base in 0..<32 {
    for k in 0..<10 {
      let mut sum : Float = 0.0
      for i in 0..<10 {
        sum = sum + a[base * 10 + i] * dct_core[k * 10 + i]
      }
      b[base * 10 + k] = sum
    }
  }
  let tmp = a
  a = b
  b = tmp
  for stage = 4; stage >= 0; stage = stage - 1 {
    let span = 320 >> stage
    let rot = match span {
      20 => rotation_10
      40 => rotation_20
      80 => rotation_40
      160 => rotation_80
      _ => rotation_160
    }
    for base in 0..<(1 << stage) {
      let p = base * span
      for i = 0; i < span / 2; i = i + 2 {
        let x = a[p + i]
        let y = a[p + span / 2 + i]
        let c = rot[2 * i]
        let s = rot[2 * i + 1]
        b[p + i] = c * x - s * y
        b[p + span - 1 - i] = s * x + c * y
        let x = a[p + i + 1]
        let y = a[p + span / 2 + i + 1]
        let c = rot[2 * i + 2]
        let s = rot[2 * i + 3]
        b[p + i + 1] = c * x + s * y
        b[p + span - 2 - i] = s * x - c * y
      }
    }
    let tmp = a
    a = b
    b = tmp
  }
  a
}

///|
/// Return the finest categorization and the 15 transitions to coarser ones.
fn categories(power : Array[Int], budget : Int) -> (Array[Int], Array[Int]) {
  let mut offset = -32
  let mut delta = 32
  while delta > 0 {
    let candidate = offset + delta
    let mut cost = 0
    for r in 0..<14 {
      cost = cost +
        expected_bits_table[clamp((candidate - power[r]) >> 1, 0, 7)]
    }
    if cost >= budget - 32 {
      offset = candidate
    }
    delta = delta >> 1
  }
  let fine = Array::makei(14, r => clamp((offset - power[r]) >> 1, 0, 7))
  let coarse = fine.copy()
  let transitions = Array::make(32, 0)
  let mut cost = 0
  for c in fine {
    cost = cost + expected_bits_table[c]
  }
  let mut high = cost
  let mut low = cost
  let mut left = 16
  let mut right = 16
  let mut chosen_fine = 0
  let mut chosen_coarse = 0
  for _ in 0..<15 {
    if high + low <= 2 * budget {
      let mut best = 99
      for r in 0..<14 {
        let score = offset - power[r] - 2 * fine[r]
        if fine[r] > 0 && score < best {
          best = score
          chosen_fine = r
        }
      }
      left = left - 1
      transitions[left] = chosen_fine
      high = high - expected_bits_table[fine[chosen_fine]]
      fine[chosen_fine] = fine[chosen_fine] - 1
      high = high + expected_bits_table[fine[chosen_fine]]
    } else {
      let mut best = -99
      for r = 13; r >= 0; r = r - 1 {
        let score = offset - power[r] - 2 * coarse[r]
        if coarse[r] < 7 && score > best {
          best = score
          chosen_coarse = r
        }
      }
      transitions[right] = chosen_coarse
      right = right + 1
      low = low - expected_bits_table[coarse[chosen_coarse]]
      coarse[chosen_coarse] = coarse[chosen_coarse] + 1
      low = low + expected_bits_table[coarse[chosen_coarse]]
    }
  }
  (fine, Array::makei(15, i => transitions[left + i]))
}

///|
fn code_table(category : Int) -> Array[Int] {
  match category {
    0 => mlt_sqvh_code_category_0
    1 => mlt_sqvh_code_category_1
    2 => mlt_sqvh_code_category_2
    3 => mlt_sqvh_code_category_3
    4 => mlt_sqvh_code_category_4
    5 => mlt_sqvh_code_category_5
    _ => mlt_sqvh_code_category_6
  }
}

///|
fn bit_table(category : Int) -> Array[Int] {
  match category {
    0 => mlt_sqvh_bitcount_category_0
    1 => mlt_sqvh_bitcount_category_1
    2 => mlt_sqvh_bitcount_category_2
    3 => mlt_sqvh_bitcount_category_3
    4 => mlt_sqvh_bitcount_category_4
    5 => mlt_sqvh_bitcount_category_5
    _ => mlt_sqvh_bitcount_category_6
  }
}

///|
fn append_bits(bits : Array[Int], value : Int, count : Int) -> Unit {
  for shift = count - 1; shift >= 0; shift = shift - 1 {
    bits.push((value >> shift) & 1)
  }
}

///|
fn quantize(
  coefs : Array[Float],
  region : Int,
  category : Int,
  power : Int,
) -> Array[Int] {
  let bits : Array[Int] = []
  if category == 7 {
    return bits
  }
  let dim = vector_dimension[category]
  let radix = max_bin[category] + 1
  let scale = step_size_inverse_table[category] *
    standard_deviation_inverse_table[power + 24]
  let codes = code_table(category)
  let sizes = bit_table(category)
  for v in 0..<(20 / dim) {
    let mut index = 0
    let mut signs = 0
    let mut nonzero = 0
    for j in 0..<dim {
      let x = coefs[region * 20 + v * dim + j]
      let k = (x.abs() * scale + dead_zone[category]).to_int().min(radix - 1)
      index = index * radix + k
      if k != 0 {
        signs = (signs << 1) | (if x > 0.0 { 1 } else { 0 })
        nonzero = nonzero + 1
      }
    }
    append_bits(bits, codes[index], sizes[index])
    append_bits(bits, signs, nonzero)
  }
  bits
}

///|
fn encode_frame(samples : Array[Float], history : Array[Float]) -> Array[Int] {
  let windowed = Array::make(320, (0.0 : Float))
  for i in 0..<160 {
    windowed[i] = analysis_window[159 - i] * history[159 - i] +
      analysis_window[160 + i] * history[160 + i]
    windowed[160 + i] = analysis_window[319 - i] * samples[i] -
      analysis_window[i] * samples[319 - i]
  }
  for i in 0..<320 {
    history[i] = samples[i]
  }
  let coefs = transform(windowed)
  let scale : Float = 1.0 / 22.0
  for i in 0..<320 {
    coefs[i] = coefs[i] * scale
  }
  let powers = Array::make(14, 0)
  for r in 0..<14 {
    let mut energy : Float = 0.0
    for j in 0..<20 {
      let x = coefs[r * 20 + j]
      energy = energy + x * x
    }
    energy = energy * (0.05 : Float)
    let mut lo = 0
    let mut hi = 64
    for _ in 0..<6 {
      let mid = (lo + hi) >> 1
      if energy < region_power_table_boundary[mid - 1] {
        hi = mid
      } else {
        lo = mid
      }
    }
    powers[r] = lo - 24
  }
  for r = 12; r >= 0; r = r - 1 {
    powers[r] = powers[r].max(powers[r + 1] - 11)
  }
  powers[0] = clamp(powers[0], 1 - 7, 31 - 7)
  for r in 1..<14 {
    powers[r] = clamp(powers[r], -8 - 7, 31 - 7)
  }
  let bits : Array[Int] = []
  append_bits(bits, powers[0] + 7, 5)
  for r in 1..<14 {
    let diff = (powers[r] - powers[r - 1]).max(-12)
    powers[r] = powers[r - 1] + diff
    let index = r * 24 + diff + 12
    append_bits(
      bits,
      differential_region_power_codes[index],
      differential_region_power_bits[index],
    )
  }
  let budget = 320 - bits.length() - 4
  let (cats, balances) = categories(powers, budget)
  for i in 0..<7 {
    cats[balances[i]] = cats[balances[i]] + 1
  }
  let regions = Array::makei(14, r => quantize(coefs, r, cats[r], powers[r]))
  let mut cost = 0
  for b in regions {
    cost = cost + b.length()
  }
  let mut control = 7
  while cost < budget && control > 0 {
    control = control - 1
    let r = balances[control]
    cats[r] = cats[r] - 1
    cost = cost - regions[r].length()
    regions[r] = quantize(coefs, r, cats[r], powers[r])
    cost = cost + regions[r].length()
  }
  while cost > budget && control < 15 {
    let r = balances[control]
    cats[r] = cats[r] + 1
    cost = cost - regions[r].length()
    regions[r] = quantize(coefs, r, cats[r], powers[r])
    cost = cost + regions[r].length()
    control = control + 1
  }
  append_bits(bits, control, 4)
  for region in regions {
    for bit in region {
      if bits.length() < 320 {
        bits.push(bit)
      }
    }
  }
  while bits.length() < 320 {
    bits.push(1)
  }
  bits
}

///|
pub fn encode(pcm : Bytes) -> Bytes raise CodecError {
  if pcm.length() == 0 || pcm.length() % 640 != 0 || pcm.length() > 64000000 {
    raise InvalidInput(
      "PCM must contain complete 320-sample s16le frames, up to 64 MB",
    )
  }
  let history = Array::make(320, (0.0 : Float))
  let out = FixedArray::make(pcm.length() / 16, (0).to_byte())
  for frame in 0..<(pcm.length() / 640) {
    let samples = Array::makei(320, i => {
      let p = frame * 640 + i * 2
      let n = pcm[p].to_int() | (pcm[p + 1].to_int() << 8)
      Float::from_int(if n >= 32768 { n - 65536 } else { n })
    })
    let bits = encode_frame(samples, history)
    for i in 0..<40 {
      let mut byte = 0
      for j in 0..<8 {
        byte = (byte << 1) | bits[i * 8 + j]
      }
      out[frame * 40 + i] = byte.to_byte()
    }
  }
  Bytes::from_array(out[:])
}

///|
priv struct Huffman {
  zero : Array[Int]
  one : Array[Int]
  symbol : Array[Int]
}

///|
/// Construct prefix trees from the wire codebooks rather than storing a second
/// decoder-only representation of those same tables.
fn huffman(codes : Array[Int], sizes : Array[Int]) -> Huffman {
  let tree : Huffman = { zero: [-1], one: [-1], symbol: [-1] }
  for symbol in 0..<codes.length() {
    if sizes[symbol] > 0 && sizes[symbol] <= 16 {
      let mut node = 0
      for shift = sizes[symbol] - 1; shift >= 0; shift = shift - 1 {
        let branch = if ((codes[symbol] >> shift) & 1) == 0 {
          tree.zero
        } else {
          tree.one
        }
        if branch[node] == -1 {
          branch[node] = tree.symbol.length()
          tree.zero.push(-1)
          tree.one.push(-1)
          tree.symbol.push(-1)
        }
        node = branch[node]
      }
      if tree.symbol[node] == -1 {
        tree.symbol[node] = symbol
      }
    }
  }
  tree
}

///|
let vector_trees : Array[Huffman] = Array::makei(7, c => {
  huffman(code_table(c), bit_table(c))
})

///|
let envelope_trees : Array[Huffman] = Array::makei(14, r => {
  huffman(
    Array::makei(24, i => differential_region_power_codes[r * 24 + i]),
    Array::makei(24, i => differential_region_power_bits[r * 24 + i]),
  )
})

///|
priv struct Reader {
  data : Bytes
  start : Int
  mut pos : Int
  mut invalid : Bool
}

///|
fn Reader::read(self : Reader, count : Int) -> Int {
  let mut n = 0
  for _ in 0..<count {
    n = n << 1
    if self.pos < 320 {
      n = n |
        (
          (self.data[self.start + self.pos / 8].to_int() >> (7 - self.pos % 8)) &
          1
        )
    } else {
      self.invalid = true
    }
    self.pos = self.pos + 1
  }
  n
}

///|
fn Reader::symbol(self : Reader, tree : Huffman) -> Int {
  let mut node = 0
  for _ in 0..<16 {
    let bit = self.read(1)
    node = if bit == 0 { tree.zero[node] } else { tree.one[node] }
    if node < 0 || self.invalid {
      self.invalid = true
      return 0
    }
    if tree.symbol[node] >= 0 {
      return tree.symbol[node]
    }
  }
  self.invalid = true
  0
}

///|
fn random_word(seed : Array[Int]) -> Int {
  let mut n = (seed[0] + seed[3]) & 65535
  if (n & 32768) != 0 {
    n = (n + 1) & 65535
  }
  seed[3] = seed[2]
  seed[2] = seed[1]
  seed[1] = seed[0]
  seed[0] = if n >= 32768 { n - 65536 } else { n }
  seed[0]
}

///|
fn decode_frame(
  reader : Reader,
  old : Array[Float],
  seed : Array[Int],
) -> Array[Float] {
  let power = Array::make(14, 0)
  power[0] = reader.read(5) - 7
  for r in 1..<14 {
    power[r] = power[r - 1] + reader.symbol(envelope_trees[r]) - 12
  }
  let control = reader.read(4)
  let (cats, balances) = categories(power, (320 - reader.pos).max(0))
  for i in 0..<control {
    cats[balances[i]] = cats[balances[i]] + 1
  }
  let coef = Array::make(320, (0.0 : Float))
  let mut bad = reader.invalid
  for p in power {
    if p + 7 > 31 || p + 7 < -8 {
      bad = true
    }
  }
  let mut exhausted = reader.invalid
  for r in 0..<14 {
    let deviation = region_standard_deviation_table[clamp(power[r] + 24, 0, 63)]
    let mut cat = if exhausted { 7 } else { cats[r] }
    if cat < 7 {
      let dim = vector_dimension[cat]
      for v in 0..<(20 / dim) {
        if reader.pos >= 320 {
          exhausted = true
          break
        }
        let mut index = reader.symbol(vector_trees[cat])
        if reader.invalid {
          exhausted = true
          break
        }
        let bins = Array::make(dim, 0)
        let radix = max_bin[cat] + 1
        let mut signs = 0
        for j = dim - 1; j >= 0; j = j - 1 {
          bins[j] = index % radix
          index = index / radix
          if bins[j] != 0 {
            signs = signs + 1
          }
        }
        if reader.pos + signs > 320 {
          exhausted = true
          break
        }
        let sign_bits = reader.read(signs)
        let mut shift = signs - 1
        for j in 0..<dim {
          let mut x = deviation *
            mlt_quant_centroid[cat * 16 + bins[j]] *
            (22.0 : Float)
          if bins[j] != 0 {
            if ((sign_bits >> shift) & 1) == 0 {
              x = -x
            }
            shift = shift - 1
          }
          coef[r * 20 + v * dim + j] = x
        }
      }
      if exhausted {
        cat = 7
      }
    }
    if cat >= 5 {
      let mut occupied = 0
      for j in 0..<20 {
        let x = coef[r * 20 + j]
        if x != 0.0 {
          occupied = occupied + 1
          if cat == 5 && x.abs() > (44.0 : Float) * deviation {
            occupied = occupied + 3
          }
        }
      }
      let factor : Float = if cat == 5 {
        match occupied.min(19) {
          0 => 0.70711
          1 => 0.6179
          2 => 0.5005
          3 => 0.3220
          _ => 0.17678
        }
      } else if cat == 6 {
        match occupied.min(19) {
          0 => 0.70711
          1 => 0.5686
          2 => 0.3563
          _ => 0.25
        }
      } else {
        0.70711
      }
      let noise = deviation * factor
      for half in 0..<2 {
        let mut word = random_word(seed)
        for j in 0..<10 {
          let p = r * 20 + half * 10 + j
          if cat == 7 || coef[p] == 0.0 {
            coef[p] = (if (word & 1) == 0 { -noise } else { noise }) *
              (22.0 : Float)
            word = word >> 1
          }
        }
      }
    }
  }
  if exhausted && control < 15 {
    bad = true
  }
  if !exhausted {
    while reader.pos < 320 {
      if reader.read(1) != 1 {
        bad = true
      }
    }
  }
  for i in 0..<280 {
    if bad {
      coef[i] = old[i]
      old[i] = 0.0
    } else {
      old[i] = coef[i]
    }
  }
  coef
}

///|
/// Invalid frames repeat the last good spectrum once, then conceal with silence.
/// Length errors are rejected before processing. No out-of-bounds bit reads.
pub fn decode(payload : Bytes) -> Bytes raise CodecError {
  if payload.length() == 0 ||
    payload.length() % 40 != 0 ||
    payload.length() > 4000000 {
    raise InvalidInput(
      "Payload must contain complete 40-byte frames, up to 4 MB",
    )
  }
  let old = Array::make(320, (0.0 : Float))
  let overlap = Array::make(160, (0.0 : Float))
  let seed = [1, 1, 1, 1]
  let out = FixedArray::make(payload.length() * 16, (0).to_byte())
  for frame in 0..<(payload.length() / 40) {
    let reader : Reader = {
      data: payload,
      start: frame * 40,
      pos: 0,
      invalid: false,
    }
    let samples = transform(decode_frame(reader, old, seed))
    let pcm = Array::make(320, (0.0 : Float))
    for i in 0..<160 {
      pcm[i] = synthesis_window[i] * samples[159 - i] +
        synthesis_window[319 - i] * overlap[i]
      pcm[160 + i] = synthesis_window[160 + i] * samples[i] -
        synthesis_window[159 - i] * overlap[159 - i]
    }
    for i in 0..<160 {
      overlap[i] = samples[160 + i]
    }
    for i in 0..<320 {
      let x = pcm[i]
      let sample = if x >= 0.0 {
        if x < 32767.0 {
          (x + (0.5 : Float)).to_int()
        } else {
          32767
        }
      } else if x > -32768.0 {
        (x - (0.5 : Float)).to_int()
      } else {
        -32768
      }
      let p = frame * 640 + 2 * i
      out[p] = sample.to_byte()
      out[p + 1] = (sample >> 8).to_byte()
    }
  }
  Bytes::from_array(out[:])
}
