// Run the actual @ffmpeg/core WASM, with the same filesystem/exec interface as
// @ffmpeg/ffmpeg's browser worker. No native ffmpeg is used by the SDK in this test.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createYkiSDK, filesLoader, createG7221 } from '../dist/index.mjs'
import { fromHex, toHex } from '@nakasyou/yki-core'
import { fixture, fixChecksum, resource, row } from '../../yki-core/tests/fixture.mjs'
const coreURL = new URL('../esm/ffmpeg-core.js', import.meta.resolve('@ffmpeg/core'))
globalThis.self = { location: { href: coreURL.href } }
const { default: factory } = await import(coreURL.href)
const media = await factory({ wasmBinary: readFileSync(new URL('ffmpeg-core.wasm', coreURL)) })
const logs = new Set()
media.setLogger((log) => {
  for (const listener of logs) listener(log)
})
const ffmpeg = {
  loaded: true,
  on(_event, listener) {
    logs.add(listener)
  },
  off(_event, listener) {
    logs.delete(listener)
  },
  async exec(args) {
    media.exec(...args)
    const result = media.ret
    media.reset()
    return result
  },
  async writeFile(path, data) {
    const copy = structuredClone(data, { transfer: [data.buffer] })
    media.FS.writeFile(path, copy)
  },
  async readFile(path) {
    return media.FS.readFile(path)
  },
  async deleteFile(path) {
    media.FS.unlink(path)
  },
}
const codec = await createG7221(
  readFileSync(new URL('../../yki-core/dist/yki-core.wasm', import.meta.url)),
)
function pcm(samples, amplitude = 8000) {
  const b = Buffer.alloc(samples * 2)
  for (let i = 0; i < samples; i++)
    b.writeInt16LE(Math.round(amplitude * Math.sin((i * 2 * Math.PI * 440) / 16000)), i * 2)
  return b
}
function wav(pcm) {
  const b = Buffer.alloc(44 + pcm.length)
  b.write('RIFF')
  b.writeUInt32LE(b.length - 8, 4)
  b.write('WAVEfmt ', 8)
  b.writeUInt32LE(16, 16)
  b.writeUInt16LE(1, 20)
  b.writeUInt16LE(1, 22)
  b.writeUInt32LE(16000, 24)
  b.writeUInt32LE(32000, 28)
  b.writeUInt16LE(2, 32)
  b.writeUInt16LE(16, 34)
  b.write('data', 36)
  b.writeUInt32LE(pcm.length, 40)
  pcm.copy(b, 44)
  return new Uint8Array(b)
}
function baseWithReference() {
  const old = fixture()
  const payload = codec.encode(pcm(320 * 60, 12000))
  const au = Buffer.alloc(32 + payload.length)
  resource(old, 4).copy(au, 0, 0, 32)
  au.writeUInt32LE(payload.length / 40, 8)
  au.writeUInt32LE(payload.length / 2, 12)
  for (let i = 0; i < payload.length; i++) {
    let n = payload[i],
      v = 0
    for (let j = 0; j < 8; j++) {
      v = (v << 1) | (n & 1)
      n >>= 1
    }
    au[32 + i] = v
  }
  const offset = (old.readUInt32LE(528) - 0x500800) * 2
  const size = Math.ceil((offset + au.length) / 4096) * 4096
  const result = Buffer.alloc(size, 255)
  old.copy(result, 0, 0, offset)
  au.copy(result, offset)
  result.writeUInt32LE(0x500800 + size / 2, 38)
  result.writeUInt16LE(0, size - 2)
  fixChecksum(result)
  return result
}
const base = baseWithReference()
const input = wav(pcm(320 * 60 + 123))
const sdk = await createYkiSDK({
  wasm: readFileSync(new URL('../../yki-core/dist/yki-core.wasm', import.meta.url)),
  ffmpeg,

  readFile: filesLoader({ 'base.yki': base, 'input.wav': input }),
})
test('actual ffmpeg-wasm: trim/pad/error, AU decode, peak and LUFS matching', async () => {
  try {
    for (const alignment of ['trim', 'pad'])
      for (const volume of ['preserve', 'peak', 'match']) {
        const result = await sdk.build({
          extends: 'base.yki',
          audio: { frameAlignment: alignment, volume },
          overrides: [{ id: 655, songSound: 'input.wav' }],
        })
        const record = result.manifest.audio[0]
        assert.equal(record.frames, alignment === 'trim' ? 60 : 61)
        assert.equal(record.volume_mode, volume)
        assert.ok(Number.isFinite(record.decoded.lufs))
        assert.equal(record.added_padding_samples, alignment === 'pad' ? 197 : 0)
        assert.equal(record.trimmed_samples, alignment === 'trim' ? 123 : 0)
        if (volume === 'match')
          assert.ok(Math.abs(record.reference.lufs - record.decoded.lufs) <= 0.2)
        const data = Buffer.from(result.data)
        const sequence = resource(data, row(data, 655)[1][1])
        const au = resource(data, sequence.readUInt16LE(6)).subarray(0, 32 + record.frames * 40)
        assert.equal((await sdk.decode(au)).length, record.frames * 640)
      }
    await assert.rejects(
      sdk.build({
        extends: 'base.yki',
        audio: { frameAlignment: 'error' },
        overrides: [{ id: 655, songSound: 'input.wav' }],
      }),
      /multiple of 320/,
    )
    assert.equal(
      input.length,
      44 + (320 * 60 + 123) * 2,
      'loader input must not be detached by FFmpeg',
    )
    assert.equal(logs.size, 0)
    assert.equal(media.FS.readdir('/').filter((name) => name.startsWith('yki-')).length, 0)
  } finally {
    await sdk.close()
  }
})
