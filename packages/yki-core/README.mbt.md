# yki-core

`custom-legacy/` の Python 実装を、再利用できる MoonBit ライブラリと WebAssembly に移植したものです。Python を実行せずに YKI を解析・編集・生成できます。元の JSON 設定形式と `build` / `validate` / `inspect` / `schema` を維持しています。

ファイル読み込み・FFmpeg は **ホスト API** に分離しています。YKI 用の 16 kHz / 16 kbps コーデックは [g7221](g7221/README.md) に MoonBit で実装し、同じ WASM に内蔵しています。C コンパイラ・Emscripten・外部コーデックは不要です。MoonBit 側がスキーマ検証、ID 解決、編集、新規行・タイプ変換、コピーオンライト、LED 生成、PCM フレーム調整、音量マッチングの探索、AU ヘッダー・ビット反転、リソース再配置、SHA-256・チェックサムを担当します。ホストを差し替えてブラウザーや別アプリから利用できます。

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

## JavaScript / TypeScript から再利用

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
  // data: Uint8Array; manifest: 再配置後のリソース番号・音声測定値・警告など
} finally {
  adapter.close()
}
```

ブラウザーでは Node ホストを使わず、同期コールバックで必要なファイルを供給します。音声ファイルを変更しないビルドでは `read` のみで十分です。

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

インスタンスごとに独立した状態を持ちます。1つのインスタンスへの再帰呼び出しは拒否されます。非同期のファイルやメディアは事前に取得するか、Worker 内で同期ホストを用意してください。JS の型定義は `js/index.d.mts` にあります。

## TypeScript SDK

The asynchronous SDK lives in [../yki-sdk](../yki-sdk/README.md). The CLI lives in [../../apps/cli](../../apps/cli/README.md).

## MoonBit の公開 API

モジュール名は `nakasyou/yki-core`。公開インターフェースは `pkg.generated.mbti` に生成します。

- `parse(Bytes) -> Image` / `Image::serialize() -> Bytes`：解析と再構築。行・リソースの編集に安定したハンドルを使います。
- `build(Json, Host, strict?) -> BuildResult`：生成バイナリ・マニフェスト・警告。
- `validate(Json, Host, strict?)` / `inspect(Bytes)` / `schema()`。
- `resolve_id(Json, Image, warn, strict?)`：B 番号、凸パターン、音声参照の解決。
- `led_frames(Json, Host)` / `encode_audio(...)` / `decode_audio(...)` / `make_au(Bytes)` / `reverse_bits(Bytes)` / `sha256(Bytes)`。
- `request(Json, Host)`：WASM と共通の JSON API。

入力エラーは `YkiError` として返します。公開 `Image` を直接編集するときも、`serialize()` は参照・フォーマットを検証します。

## ホスト API と WASM ABI

`Host` は `(Json) -> Json raise YkiError`。JSON 中のバイナリは小文字 hex です。エラーは例外または `{ "error": "message" }`。

| op          | 入力             | 結果                                                       |
| ----------- | ---------------- | ---------------------------------------------------------- |
| `read`      | `path`           | `{hex}`：ファイル内容。数値 extends は `@stock/VerN_U.yki` |
| `transcode` | `path`           | `{hex}`：モノラル 16 kHz s16le PCM                         |
| `gain`      | `hex`, `gain`    | `{hex}`：PCM に指定のゲインを適用                          |
| `measure`   | `hex`：s16le PCM | `{lufs, true_peak_dbtp, lra}`：非有限値は null             |

ゲイン処理・LUFS 測定を別実装に差し替えると、その実装の丸めや測定特性で音声出力が変わることがあります。標準 Node ホストでは元の FFmpeg / コーデックと同じコマンドを使います。

JS アダプターを使わないホストでは、UTF-8 JSON を `input_begin(length)` と `input_write(offset, word)` に渡して `invoke()` を実行します。`output_length()` / `output_read(offset)` から応答を取得します。word は4バイトの little-endian で、最後の端数は切り捨てます。`invoke()` は成功0・エラー1。ホスト RPC の際は `host_request_length/read` を読み、応答を `host_response_begin/write` に書き込んで0を返します。入力上限は256 MB。大きいメディアでは hex によるメモリー増加を考慮してください。

## 検証

```sh
pnpm run build
pnpm test
pnpm run test:parity
```

MoonBit のユニットテストと、合成 YKI を使う Node / WASM の統合テストを含みます。元 YKI が手元にあれば全6種類のバイト一致も検証します。

`test:parity` のみ比較用に `custom-legacy` の Python 環境を使用します。標準 Node ホストで21ケースを比較し、全6種類の無変更再構築、Ver.0、ID 解決、LED 繰り返し、新規メダル、タイプ変更、逐次編集、MP3 の trim/pad と preserve/peak/match が、元の生成バイナリと主要マニフェスト項目で一致することを確認しました。

## データと実機上の意味

スキーマ・既存の凸パターン対応表・根拠は `data.mbt` に組み込んでおり、実行時に `custom-legacy` や `research` の Python コードを読みません。対応表には従来どおり high / medium / low の確度があり、strict は medium / low を拒否します。物理認識・LED の RGB 順序と周期・ファームウェア更新判定は既存の未検証事項を引き継ぎます。この移植の生成結果について新たな実機検証は行っていません。

Raw codec APIs: encode_g7221(Bytes) / decode_g7221(Bytes). JavaScript: createG7221(wasm), Core.encodeG7221(pcm), Core.decodeG7221(payload). No host is required.

Raw codec APIs: encode_g7221(Bytes) / decode_g7221(Bytes). JavaScript: createG7221(wasm), Core.encodeG7221(pcm), Core.decodeG7221(payload). No host is required.

3D model generation lives in the independent [packages/3d](../3d/README.md) MoonBit/WASM package. The [SDK](../yki-sdk/README.md) binds both modules.
