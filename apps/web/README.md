# YKI Studio

A local-first Ripple + Tailwind SPA for editing Yo-kai Watch U files. Open a local `.yki`, select a medal, change sounds and LEDs, and download the result. Processing runs in a Web Worker.

From the repository root:

```sh
pnpm install --frozen-lockfile
pnpm run build
pnpm run dev
```

Dev URL: `http://127.0.0.1:5173`. Production output: `apps/web/dist`, served as static files. Engine assets are prepared from workspace packages before dev/build. Single-threaded FFmpeg does not require cross-origin isolation.

The editor supports inherited/file/builtin/resource/cleared sounds, new medals and templates, LED repetition, custom RGB frames, external LED JSON, audio alignment and gain, spoken version selection, JSON import/export, original audio preview, and manifests. The JSON editor exposes advanced options such as `referenceResource` and per-file audio settings. Imported IDs resolve to row numbers, and the loaded YKI replaces the imported `extends`. Attach referenced files with exact JSON filenames. JSON export saves configuration; attach local media again after importing.

Changes are held in memory. Save configuration before leaving or replacing the source. Spoken version selection does not establish firmware update eligibility. LED timing and physical-medal recognition still need hardware validation.

```sh
pnpm run check
pnpm --dir apps/web run test
pnpm run test:e2e
```

Browser tests use headless Brave by default. Set `BROWSER_PATH` to another Chromium executable. The Ripple formatter handles `.tsrx` with the same `semi: false` and `singleQuote: true` configuration; Vite+ formats the other workspace files.

The audio codec is implemented in MoonBit inside yki-core.wasm. No separate C codec WASM or Emscripten is required. Original AU preview uses the core directly without loading FFmpeg.
