import { readFileSync } from 'node:fs'
import { createCore, toHex } from '../js/index.mjs'
import { createNodeHost } from '../js/node-host.mjs'
const requests = JSON.parse(readFileSync(0, 'utf8'))
const outputs = []
for (const request of requests) {
  const adapter = createNodeHost({ baseDir: request.directory })
  try {
    const core = await createCore(readFileSync(new URL('../dist/yki-core.wasm', import.meta.url)), {
      host: adapter.host,
    })
    const result = core.build(request.config)
    outputs.push({ hex: toHex(result.data), manifest: result.manifest })
  } catch (error) {
    outputs.push({ error: error.message })
  } finally {
    adapter.close()
  }
}
console.log(JSON.stringify(outputs))
