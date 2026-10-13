// Worker-environment shim for exercising the unmodified @ffmpeg/ffmpeg worker
// protocol in Node. Production uses the browser's built-in Worker/fetch.
import { parentPort } from 'node:worker_threads'
import { readFile } from 'node:fs/promises'
globalThis.self = globalThis
globalThis.location = { href: import.meta.url }
const originalFetch = globalThis.fetch
globalThis.fetch = async (input, init) => {
  const url = input instanceof Request ? input.url : String(input)
  if (url.startsWith('file:'))
    return new Response(await readFile(new URL(url)), {
      headers: { 'Content-Type': 'application/wasm' },
    })
  return originalFetch(input, init)
}
globalThis.postMessage = (data, transfer) => parentPort.postMessage(data, transfer)
await import(new URL('worker.js', import.meta.resolve('@ffmpeg/ffmpeg')).href)
parentPort.on('message', (data) => globalThis.onmessage({ data }))
