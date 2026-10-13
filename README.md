# Yo-kai Watch U Medal Generation and YKI Analysis

This project organizes locally developed generation scripts and research records for publication. Official update files, audio, images, downloaded source trees, extracted data, and generated files are excluded from publication.

| Directory                 | Contents                                                           | Git tracking                              |
| ------------------------- | ------------------------------------------------------------------ | ----------------------------------------- |
| `packages/3d-generator/`                     | Medal and portrait relief generation scripts                       | Included                                  |
| `packages/custom-legacy/` | Custom YKI CLI, JSON schema, and configuration examples            | Included                                  |
| `packages/yki-core/`      | Reusable MoonBit library, WASM, and Node/browser adapters          | Source included; build artifacts excluded |
| `research/`               | Analysis scripts, lookup tables, and experiment records            | Included                                  |
| `yki/`                    | User-provided `Ver2_U.yki` through `Ver7_U.yki`                    | Excluded                                  |
| `third_party/`            | Third-party works, downloaded data, and attribution notes          | Notes only                                |
| `outputs/`                | Generated YKI files, STL models, decoded audio, and analysis dumps | Excluded                                  |

## Workspace applications

Initialized with Vite+ using Bun workspaces.

| Workspace                | Purpose                                          |
| ------------------------ | ------------------------------------------------ |
| `packages/yki-core`      | MoonBit parser/editor, WASM and JavaScript hosts |
| `packages/yki-sdk`       | Async TypeScript SDK with ffmpeg-wasm            |
| `apps/cli`               | MoonBit-powered custom CLI                       |
| `apps/web`               | Tailwind + Ripple SPA editor                     |
| `packages/custom-legacy` | Original Python implementation                   |

You need Node.js 24 or later and pnpm 12.6.0 or later.

```sh
pnpm install --frozen-lockfile
pnpm run build
pnpm run dev                 # http://127.0.0.1:5173
pnpm run cli schema
pnpm run check
pnpm run test
pnpm run test:e2e
pnpm run format:check
```

The codec is built inside yki-core.wasm; Emscripten is unnecessary. Formatting: `semi: false`, `singleQuote: true`. Usage: [Web editor](apps/web/README.md), [CLI](apps/cli/README.md), [SDK](packages/yki-sdk/README.md).

## Nix Development Environments

The flake provides development shells for x86_64 and aarch64 Linux:

```sh
# Python 3.13, jsonschema, uv, ffmpeg, OpenSCAD, and a C compiler.
nix develop

# Add portrait relief dependencies and Blender.
nix develop .#relief

# Also add PyTorch and Transformers for depth estimation.
nix develop .#depth
```

Inside the default shell, use `uv run --project packages/custom-legacy yki-cli ...` for the CLI. Inside the relief or depth shell, run the corresponding scripts directly with `python3` to use the Nix-provided Python packages. Depth estimation downloads its pinned model on first use. Original YKI files, input media, and local codec sources must still be supplied separately.

The shells pin their Nixpkgs input in `flake.lock`. They configure uv to use the Nix interpreter without downloading Python.

## 3D Generation

Medal generation runs in MoonBit/WASM with a Node.js host. Build the core first; STL output also requires OpenSCAD.

```sh
pnpm --dir packages/yki-core run build
pnpm medal 1001 0100 1110 1010 -o outputs/3d/medal.scad
```

See [3D generator README](packages/3d-generator/README.md) for usage. `packages/3d-generator/templates/` contains a modified third-party model, whose provenance differs from that of the local scripts. Attribution is documented in [third_party/README.md](third_party/README.md).

## Custom YKI Generation

Python 3.13 or later and uv are required. Audio processing also requires ffmpeg, a C compiler, and local codec sources.

1. Place original files at paths such as `yki/Ver2_U.yki`.
2. For examples that use audio, provide the input files in `third_party/media/` or update the paths in the JSON configuration.
3. Follow [packages/custom-legacy/README.md](packages/custom-legacy/README.md).

```sh
uv run --project packages/custom-legacy yki-cli schema
uv run --project packages/custom-legacy yki-cli build packages/custom-legacy/examples/mogumogu.json -o outputs/custom_yki/custom.yki
```

The reference audio codec implementation is not bundled. Required local paths are `third_party/local/work/libg7221/src/` and `third_party/local/work/dec/dct4.h`. The CLI uses analysis code and lookup tables elsewhere in this repository, so use the complete repository.

## MoonBit / WASM

`packages/yki-core/` implements the YKI editing logic in MoonBit and exposes a reusable WebAssembly API. It includes a compatible Node CLI and a browser adapter; the codec runs in MoonBit, while file I/O and FFmpeg are replaceable host capabilities. See [packages/yki-core/README.md](packages/yki-core/README.md).

```sh
pnpm install --frozen-lockfile
pnpm run build
pnpm run test
```

## Research

See [research/README.md](research/README.md).

This layout prepares files for publication; it does not publish or upload them. No distribution license has been selected for the local code as a whole. A license for local code does not apply to third-party materials.
