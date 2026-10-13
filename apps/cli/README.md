# MoonBit custom CLI

This application is a thin TypeScript launcher for the MoonBit YKI core. Python is not used at runtime.

From the repository root:

```sh
pnpm run build
pnpm run cli schema
pnpm run cli inspect yki/Ver2_U.yki
pnpm run cli validate packages/custom-legacy/examples/mogumogu.json
pnpm run cli build packages/custom-legacy/examples/mogumogu.json -o outputs/custom_yki/custom.yki
```

The built Node executable is `apps/cli/dist/index.mjs` (`yki-cli` bin). Relative paths resolve from the configuration directory. Stdin, `--base-dir`, `--strict-mapping`, and `--output` are supported. The media host needs FFmpeg for conversion and loudness measurement. Encoding and decoding use the MoonBit codec inside yki-core.wasm; no C source or compiler is needed.

The original Python application remains in `custom-legacy` for reference and parity comparisons.
