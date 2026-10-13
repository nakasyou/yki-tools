import test from 'node:test'
import assert from 'node:assert/strict'
import { Worker as NodeWorker } from 'node:worker_threads'
import { readFileSync } from 'node:fs'
const { FFmpeg } = await import(new URL('classes.js', import.meta.resolve('@ffmpeg/ffmpeg')).href)
import { createYkiSDK, filesLoader } from '../dist/index.mjs'
import { fixture } from '../../yki-core/tests/fixture.mjs'
globalThis.Worker = class {
  constructor() {
    this.worker = new NodeWorker(new URL('./ffmpeg-worker-node.mjs', import.meta.url))
    this.worker.on('message', (data) => this.onmessage?.({ data }))
  }
  postMessage(data, transfer) {
    this.worker.postMessage(data, transfer)
  }
  terminate() {
    return this.worker.terminate()
  }
}
test(
  'real FFmpeg class and worker: file transfer, logs and SDK build',
  { timeout: 30000 },
  async () => {
    const ffmpeg = new FFmpeg()
    const coreURL = new URL('../esm/ffmpeg-core.js', import.meta.resolve('@ffmpeg/core')).href

    let sdk
    try {
      // Use the real browser-facing FFmpeg class and its unmodified worker.js.
      await ffmpeg.load({ coreURL })
      const pcm = new Uint8Array(320 * 60 * 2)
      const wave = new Uint8Array(44 + pcm.length)
      const view = new DataView(wave.buffer)
      const text = (offset, s) => wave.set(new TextEncoder().encode(s), offset)
      text(0, 'RIFF')
      view.setUint32(4, wave.length - 8, true)
      text(8, 'WAVEfmt ')
      view.setUint32(16, 16, true)
      view.setUint16(20, 1, true)
      view.setUint16(22, 1, true)
      view.setUint32(24, 16000, true)
      view.setUint32(28, 32000, true)
      view.setUint16(32, 2, true)
      view.setUint16(34, 16, true)
      text(36, 'data')
      view.setUint32(40, pcm.length, true)
      sdk = await createYkiSDK({
        wasm: readFileSync(new URL('../../yki-core/dist/yki-core.wasm', import.meta.url)),
        ffmpeg,

        readFile: filesLoader({ 'base.yki': fixture(), 'silence.wav': wave }),
      })
      const result = await sdk.build({
        extends: 'base.yki',
        overrides: [{ id: 655, songSound: 'silence.wav' }],
      })
      assert.equal(result.manifest.audio[0].frames, 60)
      assert.equal(result.manifest.audio[0].decoded.lufs, null)
      assert.equal(wave.byteLength, 38444, 'caller buffer retained across worker transfers')
      assert.equal(
        (await ffmpeg.listDir('/')).filter((item) => item.name.startsWith('yki-')).length,
        0,
      )
    } finally {
      if (sdk) await sdk.close()
      ffmpeg.terminate()
    }
  },
)
