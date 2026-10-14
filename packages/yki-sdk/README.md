# @nakasyou/yki-sdk

Promise-based TypeScript SDK for Yo-kai Watch YKI editing, browser audio conversion, and 3D medal generation. The package bundles the portable MoonBit core and 3D JavaScript bindings, types, both WASM modules, and the single-threaded FFmpeg browser assets. It has no runtime dependency on the private `@nakasyou/yki-core` or `@nakasyou/yki-3d` workspace packages.

## Installation

```sh
pnpm add @nakasyou/yki-sdk
```

Bundle the SDK with Vite or another browser bundler that supports `@ffmpeg/ffmpeg` workers. Copy the files in `node_modules/@nakasyou/yki-sdk/dist/browser/` to your application's static asset directory (for example `/assets/yki/`). This directory contains `yki-core.wasm`, `yki-3d.wasm`, `ffmpeg-core.js`, and `ffmpeg-core.wasm`. The WASM modules are also exported as `@nakasyou/yki-sdk/wasm` and `@nakasyou/yki-sdk/wasm3d`; browser assets are exported under `@nakasyou/yki-sdk/browser/*`.

```ts
import { createYkiSDK, filesLoader } from '@nakasyou/yki-sdk'

const assets = new URL('/assets/yki/', location.href)
const sdk = await createYkiSDK({
  wasm: await (await fetch(new URL('yki-core.wasm', assets))).arrayBuffer(),
  wasm3d: await (await fetch(new URL('yki-3d.wasm', assets))).arrayBuffer(),
  ffmpegLoad: {
    coreURL: new URL('ffmpeg-core.js', assets).href,
    wasmURL: new URL('ffmpeg-core.wasm', assets).href,
  },
  readFile: filesLoader({ 'base.yki': baseFile, 'song.mp3': songFile }),
})
try {
  const { data, manifest } = await sdk.build({
    extends: 'base.yki',
    audio: { frameAlignment: 'trim', volume: 'match' },
    overrides: [{ id: 655, songSound: 'song.mp3' }],
  })
  // data is the generated YKI Uint8Array; input files may be Files or Blobs.
} finally {
  await sdk.close()
}
```

See `examples/browser-sdk.ts` for a type-checked example. `filesLoader` accepts `File`, `Blob`, `Uint8Array`, and `ArrayBuffer`. Paths are exact logical keys; numeric `extends: 2` uses `@stock/Ver2_U.yki`. Implement relative path resolution in your own `readFile` callback when needed.

The SDK exposes `build`, `validate`, `validateConfig`, `inspect`, `resolve`, `roundtrip`, `decode`, `schema`, `request`, `generateMedal`, and `close`. Operations return promises; YKI operations are serialized within each instance. `generateMedal(bits, options)` uses the independent 3D WASM and returns `{ source, rows, mode, filename }`. `request({ op: 'generate_medal', bits, ...options })` routes to the same module. `close()` waits for pending work and terminates SDK-owned FFmpeg workers; borrowed FFmpeg instances remain alive and should not be used concurrently outside the SDK.

The async host replays synchronous WASM requests using cached host responses. Each FFmpeg operation runs once, but MoonBit computations may run repeatedly. Use a dedicated Worker for large files to keep the UI responsive. The supplied single-threaded FFmpeg core requires neither SharedArrayBuffer nor COOP/COEP. No native FFmpeg, Python, C compiler, or MoonBit installation is needed at runtime.

`createG7221(wasm)` (also exported as `loadG7221`) provides the standalone MoonBit codec. The low-level async core exposes `encodeG7221` and `decodeG7221`.

For model generation without FFmpeg or a YKI file, use the standalone binding:

```ts
import { create3D } from '@nakasyou/yki-sdk'
const threeD = await create3D(await (await fetch(new URL('yki-3d.wasm', assets))).arrayBuffer())
const medal = threeD.generateMedal('1011 0110 0001 1010', { mode: 'lite' })
```

Migration: `createYkiSDK` now requires `wasm3d` alongside `wasm`. The former `core.generateMedal` API moves to `create3D` or `sdk.generateMedal`. `MedalOptions` and `GeneratedMedal` are exported from the SDK and the 3D package.

## Development and local publication

From the repository root, install Node.js 24+, pnpm 12.6.0, and the [MoonBit toolchain](https://www.moonbitlang.com/download), then run:

```sh
pnpm install --frozen-lockfile
pnpm --dir packages/yki-core run build
pnpm --dir packages/yki-sdk run build
pnpm --dir packages/yki-sdk run typecheck
pnpm --dir packages/yki-sdk run test
pnpm --dir packages/yki-sdk run test:media
```

From `packages/yki-sdk`, `pnpm exec vp pack` bundles all three entry points and their declarations, builds both MoonBit WASM modules, and prepares browser assets. `pnpm publish` builds, type-checks, and tests through `prepublishOnly`. Authenticate locally before publishing:

```sh
cd packages/yki-sdk
npm login
pnpm publish --access public
```

Inspect the archive with `npm pack --dry-run`. Unit tests cover async replay, shutdown, buffer handling, and failure cleanup. Media tests run the actual FFmpeg WASM and workers in Node.

## GitHub Actions releases

The `Publish yki-sdk` action in `.github/workflows/publish.yml` runs only through manual dispatch. Choose `patch`, `minor`, or `major`. It checks out the default branch, reads the current npm `latest` version, increments it, synchronizes the pnpm lockfile, builds and validates the SDK, and checks npm/tag collisions. It prepares a commit and annotated `v<version>` tag, publishes through `npm publish` with OIDC, then pushes the commit/tag and creates a GitHub Release. Concurrent releases are serialized. A failed npm publish does not push the release commit or tag.

The package must already have an initial published version; a missing package or failed registry lookup stops the action. For the first release, publish locally with the command above, then configure the package's npm **Trusted Publisher** settings:

- Provider: GitHub Actions
- Organization or user: `nakasyou`
- Repository: `yki-tools`
- Workflow filename: `publish.yml`
- Environment: leave empty
- Allowed actions: enable `npm publish`

See [npm trusted publishing](https://docs.npmjs.com/trusted-publishers/). The workflow uses a GitHub-hosted runner, Node 24, npm 11, and `id-token: write`; no npm publishing token is required. The repository must permit the workflow to push to its default branch. If npm publication succeeds but the subsequent push fails, reconcile the release commit/tag before attempting another release.
