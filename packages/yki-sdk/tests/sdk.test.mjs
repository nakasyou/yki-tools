import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createCore, toHex } from '@nakasyou/yki-core'
import { createAsyncCore } from '../dist/async-core.mjs'
import { createYkiSDK, filesLoader } from '../dist/index.mjs'
import { createFFmpegHost } from '../dist/ffmpeg-host.mjs'
import { fixture } from '../../yki-core/tests/fixture.mjs'
const wasm = readFileSync(new URL('../../yki-core/dist/yki-core.wasm', import.meta.url))
const base = fixture()
test('async replay calls I/O once, serializes concurrent builds, and recovers from errors', async () => {
  const calls = []
  const core = await createAsyncCore(wasm, async (request) => {
    calls.push(request)
    await new Promise((resolve) => setTimeout(resolve, 1))
    if (request.op === 'read') return { hex: toHex(base) }
    throw new Error('missing media')
  })
  const [first, second] = await Promise.all([
    core.build({ extends: 2, overrides: [] }),
    core.build({ extends: 2, version: 0, overrides: [] }),
  ])
  assert.deepEqual(first.data, new Uint8Array(base))
  assert.equal(second.manifest.version, 0)
  assert.equal(calls.length, 2)
  await assert.rejects(
    core.build({ extends: 2, overrides: [{ id: 655, songSound: 'missing.wav' }] }),
    /missing media/,
  )
  assert.equal((await core.build({ extends: 2, overrides: [] })).manifest.version, 2)
})
test('file map and Blob loader', async () => {
  const map = filesLoader(new Map([['base.yki', base]]))
  assert.equal(await map('base.yki'), base)
  assert.throws(() => map('missing.yki'), /File not found/)
  const ffmpeg = { on() {}, off() {} }
  const adapter = createFFmpegHost({
    ffmpeg,
    readFile: filesLoader({ 'base.yki': new Blob([base]) }),
  })
  assert.equal((await adapter.host({ op: 'read', path: 'base.yki' })).hex, toHex(base))
  await adapter.close()
  await assert.rejects(adapter.host({ op: 'read', path: 'base.yki' }), /closed/)
})
test('close waits for a complete in-flight build and does not terminate borrowed FFmpeg', async () => {
  let terminated = false
  let loaded = false
  const ffmpeg = {
    loaded: true,
    on() {},
    off() {},
    terminate() {
      terminated = true
    },
  }
  const sdk = await createYkiSDK({
    wasm,
    ffmpeg,
    readFile: async () => {
      await new Promise((resolve) => setTimeout(resolve, 5))
      loaded = true
      return base
    },
  })
  const pending = sdk.build({ extends: 2, overrides: [] })
  const closed = sdk.close()
  assert.equal((await pending).manifest.version, 2)
  await closed
  assert.equal(loaded, true)
  assert.equal(terminated, false)
  await assert.rejects(sdk.schema(), /closed/)
})
test('failed FFmpeg conversion cleans files and unregisters log callback', async () => {
  const files = new Map()
  let listener
  let removed = false
  const ffmpeg = {
    on(_event, fn) {
      listener = fn
    },
    off(_event, fn) {
      assert.equal(fn, listener)
      removed = true
    },
    async writeFile(path, data) {
      files.set(path, data)
    },
    async exec() {
      listener({ message: 'unsupported input' })
      return 1
    },
    async deleteFile(path) {
      files.delete(path)
    },
  }
  const media = new Uint8Array([1, 2, 3])
  const host = createFFmpegHost({ ffmpeg, readFile: () => media })
  await assert.rejects(host.host({ op: 'transcode', path: 'input.wav' }), /unsupported input/)
  assert.equal(files.size, 0)
  assert.equal(removed, true)
  assert.deepEqual(media, new Uint8Array([1, 2, 3]))
  await host.close()
})
test('async codec API uses MoonBit without any host capability', async () => {
  const core = await createAsyncCore(wasm, async () => {
    throw new Error('host forbidden')
  })
  const pcm = new Uint8Array(640)
  const payload = await core.encodeG7221(pcm)
  assert.equal(payload.length, 40)
  assert.equal((await core.decodeG7221(payload)).length, 640)
})
