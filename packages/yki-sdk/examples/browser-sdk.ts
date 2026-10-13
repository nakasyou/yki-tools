import { createYkiSDK, filesLoader } from '@nakasyou/yki-sdk'

/** Call from a browser application bundled with Vite/Webpack/etc.
 * Serve npm run prepare:browser's output from assetsURL.
 */
export async function buildSong(base: File, song: File, assetsURL: URL) {
  const wasmResponse = await fetch(new URL('yki-core.wasm', assetsURL))
  if (!wasmResponse.ok) throw new Error(`YKI WASM load failed: ${wasmResponse.status}`)
  const sdk = await createYkiSDK({
    wasm: await wasmResponse.arrayBuffer(),
    ffmpegLoad: {
      coreURL: new URL('ffmpeg-core.js', assetsURL).href,
      wasmURL: new URL('ffmpeg-core.wasm', assetsURL).href,
    },
    readFile: filesLoader({ 'base.yki': base, 'song.mp3': song }),
  })
  try {
    const result = await sdk.build({
      extends: 'base.yki',
      audio: { frameAlignment: 'trim', volume: 'preserve' },
      overrides: [{ id: 655, songSound: 'song.mp3' }],
    })
    return {
      blob: new Blob([result.data.slice().buffer], { type: 'application/octet-stream' }),
      manifest: result.manifest,
    }
  } finally {
    await sdk.close()
  }
}
