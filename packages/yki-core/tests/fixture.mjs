// Independently constructed valid tiny YKI: 988 rows, one LED, one sequence, one AU.
export function fixture() {
  const count = 5
  const root = Buffer.alloc(120, 255)
  root.writeUInt16LE(0, 44)
  root.writeUInt16LE(66, 46)
  const rows = Buffer.alloc(988 * 36, 255)
  function pair(row, slot, tag, value) {
    const p = (row - 1) * 36 + slot * 4
    rows.writeUInt16LE(tag, p)
    rows.writeUInt16LE(value, p + 2)
  }
  pair(1, 0, 0, 37)
  pair(1, 2, 0, 1)
  pair(1, 4, 0, 117)
  pair(655, 0, 65534, 65534)
  pair(655, 1, 1, 3)
  const led = Buffer.from('ffff010002000300ffffffffffff', 'hex')
  const sequence = Buffer.from('0100020001000400', 'hex')
  const audio = Buffer.alloc(72)
  audio.write('AU')
  audio.writeUInt16LE(16000, 2)
  audio.writeUInt16LE(1600, 4)
  audio.writeUInt16LE(1, 6)
  audio.writeUInt32LE(1, 8)
  audio.writeUInt32LE(20, 12)
  audio.writeUInt16LE(65535, 22)
  audio.writeUInt16LE(16, 26)
  audio.writeUInt16LE(65535, 28)
  audio.writeUInt16LE(65535, 30)
  const blobs = [root, rows, led, sequence, audio]
  let cursor = 512 + count * 4
  const offsets = blobs.map((b) => {
    const p = cursor
    cursor += b.length
    return p
  })
  const size = Math.ceil(cursor / 4096) * 4096
  const data = Buffer.alloc(size, 255)
  data.fill(0, 0, 512 + count * 4)
  data.write('BandaiYokai3rd******************')
  data.writeUInt32LE(0x500800, 34)
  data.writeUInt32LE(0x500800 + size / 2, 38)
  data.writeUInt16LE(count, 42)
  blobs.forEach((b, i) => {
    data.writeUInt32LE(0x500800 + offsets[i] / 2, 512 + i * 4)
    b.copy(data, offsets[i])
  })
  data.writeUInt16LE(0, size - 2)
  fixChecksum(data)
  return data
}
export function fixChecksum(data) {
  data.writeUInt16LE(0, 46)
  let sum = 0
  for (const b of data) sum = (sum + b) & 255
  data.writeUInt16LE(-sum & 255, 46)
}
export function resource(data, id) {
  const offset = (data.readUInt32LE(512 + id * 4) - 0x500800) * 2
  const count = data.readUInt16LE(42)
  const end = id + 1 < count ? (data.readUInt32LE(516 + id * 4) - 0x500800) * 2 : data.length
  return data.subarray(offset, end)
}
export function row(data, id) {
  const table = resource(data, 1)
  return Array.from({ length: 9 }, (_, i) => [
    table.readUInt16LE((id - 1) * 36 + i * 4),
    table.readUInt16LE((id - 1) * 36 + i * 4 + 2),
  ])
}
