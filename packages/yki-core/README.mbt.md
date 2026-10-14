# yki-core

A reusable MoonBit library and WebAssembly port of the Python implementation in `custom-legacy/`. Parse, edit, and generate YKI without running Python. The original JSON configuration format and `build` / `validate` / `inspect` / `schema` operations are preserved.

File loading and FFmpeg are separated into a **host API**. The 16 kHz / 16 kbps YKI codec is implemented in MoonBit in [g7221](g7221/README.md) and bundled in the same WASM. No C compiler, Emscripten, or external codec is required. MoonBit handles schema validation, ID resolution, editing, new rows and type conversion, copy-on-write, LED generation, PCM frame alignment, volume matching, AU headers and bit reversal, resource relocation, SHA-256, and checksums. Replace the host to use the library in browsers or other applications.

## Build and CLI

From the repository root:

```sh
pnpm install --frozen-lockfile
pnpm run build
pnpm run cli inspect yki/Ver2_U.yki
pnpm run cli build packages/custom-legacy/examples/mogumogu.json -o outputs/custom_yki/moonbit.yki
```

Core output: `packages/yki-core/dist/yki-core.wasm`. Vite+ Pack bundles JavaScript and declarations. The CLI supports `build`, `validate`, `inspect`, `schema`, stdin, `--base-dir`, and `--strict-mapping`.

The Node host uses native FFmpeg for media conversion and loudness measurement. Set FFMPEG to override the executable. Encoding and decoding run inside MoonBit.

## JavaScript / TypeScript usage

```js
import { readFileSync } from 'node:fs'
import { createCore } from '@nakasyou/yki-core'
import { createNodeHost } from '@nakasyou/yki-core/node-host'

const adapter = createNodeHost({ baseDir: '/path/to/configs', stockDir: '/path/to/yki' })
try {
  const core = await createCore(
    readFileSync(new URL(import.meta.resolve('@nakasyou/yki-core/wasm'))),
    { host: adapter.host },
  )
  const { data, manifest } = core.build({
    extends: 2,
    overrides: [{ id: 'E7BA', songSound: { builtin: 107 }, led: { resource: 5, repeat: 12 } }],
  })
  // data: Uint8Array; manifest: relocated resource IDs, audio measurements, warnings, etc.
} finally {
  adapter.close()
}
```

In browsers, supply files through synchronous callbacks instead of using the Node host. Builds without audio conversion only require `read`.

```js
import { createCore, toHex } from '@nakasyou/yki-core'
const base = new Uint8Array(await (await fetch('/base.yki')).arrayBuffer())
const wasm = await (await fetch('/yki-core.wasm')).arrayBuffer()
const core = await createCore(wasm, {
  host(request) {
    if (request.op === 'read' && request.path === 'base.yki') return { hex: toHex(base) }
    throw new Error(`Unknown file/capability: ${request.op}`)
  },
})
const result = core.build({ extends: 'base.yki', version: 0, overrides: [] })
```

Each instance has independent state. Recursive calls on the same instance are rejected. Load asynchronous files and media ahead of time, or provide a synchronous host inside a Worker. JavaScript type declarations are in `js/index.d.mts`.

## TypeScript SDK

The asynchronous SDK lives in [../yki-sdk](../yki-sdk/README.md). The CLI lives in [../../apps/cli](../../apps/cli/README.md).

## Public MoonBit API

The module is `nakasyou/yki-core`. Its public interface is generated in `pkg.generated.mbti`.

- `parse(Bytes) -> Image` / `Image::serialize() -> Bytes`: parsing and reconstruction, with stable handles for row and resource edits.
- `build(Json, Host, strict?) -> BuildResult`: generated binary, manifest, and warnings.
- `validate(Json, Host, strict?)` / `inspect(Bytes)` / `schema()`。
- `resolve_id(Json, Image, warn, strict?)`: resolve B numbers, peg patterns, and sound references.
- `led_frames(Json, Host)` / `encode_audio(...)` / `decode_audio(...)` / `make_au(Bytes)` / `reverse_bits(Bytes)` / `sha256(Bytes)`。
- `request(Json, Host)`: the JSON API shared with WASM.

Input errors are returned as `YkiError`. When editing a public `Image` directly, `serialize()` still validates references and format.

## Host API and WASM ABI

`Host` is `(Json) -> Json raise YkiError`. Binary data in JSON uses lowercase hex. Errors are exceptions or `{ "error": "message" }`.

| op          | Input            | Result                                                           |
| ----------- | ---------------- | ---------------------------------------------------------------- |
| `read`      | `path`           | `{hex}`: file contents. Numeric extends uses `@stock/VerN_U.yki` |
| `transcode` | `path`           | `{hex}`: mono 16 kHz s16le PCM                                   |
| `gain`      | `hex`, `gain`    | `{hex}`: apply the specified gain to PCM                         |
| `measure`   | `hex`: s16le PCM | `{lufs, true_peak_dbtp, lra}`: non-finite values are null        |

Replacing gain or LUFS implementations can change audio output due to rounding or measurement differences. The standard Node host uses the same commands as the original FFmpeg / codec implementation.

Hosts without the JavaScript adapter send UTF-8 JSON through `input_begin(length)` and `input_write(offset, word)`, then call `invoke()`. Read responses through `output_length()` / `output_read(offset)`. Each word is four bytes in little-endian order; only bytes within the declared length are used. `invoke()` returns 0 on success and 1 on error. During host RPC, read `host_request_length/read`, write the response through `host_response_begin/write`, and return 0. The input limit is 256 MB. Account for hex encoding overhead with large media.

## Validation

```sh
pnpm run build
pnpm test
pnpm run test:parity
```

Tests include MoonBit unit tests and Node / WASM integration tests using synthetic YKI files. If original YKI files are available, byte equality is also checked for all six versions.

Only `test:parity` uses the Python environment in `custom-legacy` for comparison. The standard Node host was compared across 21 cases: unchanged reconstruction of all six versions, Ver.0, ID resolution, LED repeats, new medals, type changes, sequential edits, and MP3 trim/pad with preserve/peak/match. Generated bytes and major manifest fields matched the original implementation.

## Data and hardware interpretation

The schema, existing peg lookup table, and evidence are embedded in `data.mbt`; runtime operations do not read Python code from `custom-legacy` or `research`. Mappings retain high / medium / low confidence, and strict mode rejects medium / low confidence. Physical recognition, LED RGB order and timing, and firmware update decisions remain unverified as before. No new hardware validation has been performed for output from this port.

Raw codec APIs: encode_g7221(Bytes) / decode_g7221(Bytes). JavaScript: createG7221(wasm), Core.encodeG7221(pcm), Core.decodeG7221(payload). No host is required.

Raw codec APIs: encode_g7221(Bytes) / decode_g7221(Bytes). JavaScript: createG7221(wasm), Core.encodeG7221(pcm), Core.decodeG7221(payload). No host is required.

3D model generation lives in the independent [packages/3d](../3d/README.md) MoonBit/WASM package. The [SDK](../yki-sdk/README.md) binds both modules.
