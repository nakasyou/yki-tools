import { test, expect } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { createCore } from '@nakasyou/yki-core'
// Independent tiny YKI, also used by the binary parser's integration tests.
// @ts-expect-error JavaScript test fixture deliberately has no declaration file
import { fixture, row, resource } from '../../../packages/yki-core/tests/fixture.mjs'
const base = fixture() as Buffer
async function load(page: import('@playwright/test').Page) {
  await page.goto('/')
  await expect(page.getByRole('region', { name: 'YKI 読み込み' })).toBeVisible()
  await expect(page.getByRole('region', { name: 'バイナリ', exact: true })).toHaveCount(0)
  await expect(page.getByLabel('メニュー', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('region', { name: '詳細', exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'エクスポート', exact: true })).toHaveCount(0)
  await page
    .getByLabel('YKI をインポート', { exact: true })
    .setInputFiles({ name: 'base.yki', mimeType: 'application/octet-stream', buffer: base })
  await expect(page.getByText('2 枚の登録済みメダルを読み込みました。')).toBeVisible()
}
async function displayedBytesMatch(page: import('@playwright/test').Page, output: Buffer) {
  await expect
    .poll(async () => {
      const displayed = await page
        .locator('#hex-viewport [data-offset]')
        .evaluateAll((elements) =>
          elements.map((element) => ({
            offset: Number(element.getAttribute('data-offset')),
            hex: element.textContent,
          })),
        )
      return (
        displayed.length > 0 &&
        displayed.every(
          ({ offset, hex }) => hex === output[offset].toString(16).toUpperCase().padStart(2, '0'),
        )
      )
    })
    .toBe(true)
}
test('unchanged YKI downloads losslessly; edits affect only selected medal', async ({ page }) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await load(page)
  await page.screenshot({
    path: new URL('../../../outputs/web/editor.png', import.meta.url).pathname,
    fullPage: true,
  })
  await page.getByRole('button', { name: 'エクスポート', exact: true }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog).toBeVisible()
  await dialog.getByLabel('出力ファイル名').fill('invalid.txt')
  await dialog.getByRole('button', { name: 'YKI をエクスポート', exact: true }).click()
  await expect(dialog.getByText('出力ファイル名は .yki にしてください。')).toBeVisible()
  await expect(dialog).toBeVisible()
  await dialog.getByLabel('出力ファイル名').fill('export.yki')
  await page.keyboard.press('Escape')
  await expect(dialog).not.toBeVisible()
  const unchanged = page.waitForEvent('download')
  await page.getByRole('button', { name: 'エクスポート', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: 'YKI をエクスポート', exact: true }).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  const first = await unchanged
  expect(first.suggestedFilename()).toBe('export.yki')
  expect(readFileSync((await first.path())!)).toEqual(base)
  await page.getByLabel('うた / Song のソース').selectOption('builtin')
  await page.getByLabel('内蔵サウンド ID').fill('107')
  await expect
    .poll(async () =>
      (await page.locator('#hex-viewport .hex-selected').allTextContents()).join(''),
    )
    .toBe('00006B00')
  await page.getByRole('tab', { name: 'LED パターン' }).click()
  await page.getByLabel('LED の設定').selectOption('frames')
  await page.getByLabel('RGB フレーム / [[r, g, b], …]').fill('[[255,0,0],[0,0,255]]')
  await page.getByRole('button', { name: 'フレームを反映' }).click()
  await expect(page.locator('#hex-viewport .hex-selected[data-kind="led"]')).toHaveCount(20)
  const edited = page.waitForEvent('download')
  await page.getByRole('button', { name: 'エクスポート', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: 'YKI をエクスポート', exact: true }).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  const output = readFileSync((await (await edited).path())!)
  const sequence = resource(output, row(output, 655)[1][1]) as Buffer
  expect(sequence.readUInt16LE(4)).toBe(0)
  expect(sequence.readUInt16LE(6)).toBe(107)
  expect(row(output, 1)).toEqual(row(base, 1))
  await displayedBytesMatch(page, output)
  await page.getByRole('tab', { name: '音声', exact: true }).click()
  await page.getByLabel('うた / Song のソース').focus()
  await expect
    .poll(async () =>
      (await page.locator('#hex-viewport .hex-selected').allTextContents()).join(''),
    )
    .toBe('00006B00')
  await displayedBytesMatch(page, output)
  await page.getByRole('button', { name: '編集をリセット' }).click()
  const originalRow = (base.readUInt32LE(516) - base.readUInt32LE(34)) * 2 + 654 * 36
  await expect(page.locator(`#hex-viewport [data-offset="${originalRow + 6}"]`)).toHaveText('03')
  await displayedBytesMatch(page, base)
  expect(errors).toEqual([])
})
test('browser ffmpeg-wasm converts a local WAV and produces playable AU', async ({ page }) => {
  await load(page)
  await page.getByLabel('うた / Song のソース').selectOption('file')
  const wav = Buffer.alloc(44 + 640 * 60)
  wav.write('RIFF')
  wav.writeUInt32LE(wav.length - 8, 4)
  wav.write('WAVEfmt ', 8)
  wav.writeUInt32LE(16, 16)
  wav.writeUInt16LE(1, 20)
  wav.writeUInt16LE(1, 22)
  wav.writeUInt32LE(16000, 24)
  wav.writeUInt32LE(32000, 28)
  wav.writeUInt16LE(2, 32)
  wav.writeUInt16LE(16, 34)
  wav.write('data', 36)
  wav.writeUInt32LE(wav.length - 44, 40)
  await page
    .getByLabel('うた / Song の音声ファイル')
    .setInputFiles({ name: 'silence.wav', mimeType: 'audio/wav', buffer: wav })
  await page.getByLabel('うた / Song の音声ファイル').focus()
  await expect(
    page.getByRole('region', { name: 'バイナリ', exact: true }).getByText('編集内容を反映中…'),
  ).toHaveCount(0, { timeout: 30000 })
  await expect
    .poll(() => page.locator('#hex-viewport .hex-selected[data-kind="audio"]').count())
    .toBeGreaterThan(100)
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'エクスポート', exact: true }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.getByRole('button', { name: 'YKI をエクスポート', exact: true }).click()
  await expect(page.getByRole('dialog')).not.toBeVisible()
  const output = readFileSync((await (await download).path())!)
  const core = await createCore(
    readFileSync(new URL('../../../packages/yki-core/dist/yki-core.wasm', import.meta.url)),
  )
  const sequence = resource(output, row(output, 655)[1][1]) as Buffer
  const audio = resource(output, sequence.readUInt16LE(6)) as Buffer
  expect(audio.subarray(0, 2).toString()).toBe('AU')
  expect(audio.readUInt32LE(8)).toBe(60)
  await displayedBytesMatch(page, output)
  expect(core.inspect(output).version).toBe(2)
  await expect(page.getByText('YKI を生成しました。元のファイルは変更されません。')).toBeVisible()
})
test('binary view follows menu and sound selection; mobile stays within viewport', async ({
  page,
}) => {
  const errors: string[] = []
  page.on('pageerror', (error) => errors.push(error.message))
  await load(page)
  await expect(page.getByRole('tab', { name: 'JSON 設定' })).toHaveCount(0)
  const binary = page.getByRole('region', { name: 'バイナリ', exact: true })
  const medalOffset = (base.readUInt32LE(516) - base.readUInt32LE(34)) * 2 + 654 * 36
  await expect(page.getByLabel('バイナリの色分け凡例')).toContainText('音声')
  await expect(page.locator(`#hex-viewport [data-offset="${medalOffset}"]`)).toHaveAttribute(
    'data-kind',
    'medal_table',
  )
  await expect(page.locator(`#hex-viewport [data-offset="${medalOffset}"]`)).toHaveClass(
    /hex-selected/,
  )
  await expect(
    binary.getByText(`B655 · 0x${medalOffset.toString(16).toUpperCase().padStart(8, '0')}`, {
      exact: true,
    }),
  ).toBeVisible()
  await expect(page.locator('#hex-viewport .mono')).toHaveCount(28)
  await page.getByRole('button', { name: 'ヘッダー', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'ヘッダー', exact: true })).toBeVisible()
  await expect(binary.getByText('ヘッダー · 0x00000000', { exact: true })).toBeVisible()
  await expect(page.locator('#hex-viewport .mono').first()).toContainText('42')
  await expect(page.locator('#hex-viewport [data-offset="0"]')).toHaveAttribute(
    'data-kind',
    'header',
  )
  await page.getByRole('button', { name: /B655.*うた/ }).click()
  await page.getByLabel('うた / Song のソース').focus()
  const seq = resource(base, row(base, 655)[1][1]) as Buffer
  const audioId = seq.readUInt16LE(6)
  const audioOffset = (base.readUInt32LE(512 + audioId * 4) - base.readUInt32LE(34)) * 2
  await expect(page.locator(`#hex-viewport [data-offset="${audioOffset}"]`)).toHaveAttribute(
    'data-kind',
    'audio',
  )
  await expect(
    binary.getByText(`songSound · 0x${audioOffset.toString(16).toUpperCase().padStart(8, '0')}`, {
      exact: true,
    }),
  ).toBeVisible()
  await page.getByLabel('16進オフセット').fill('20')
  await page.getByRole('button', { name: '移動', exact: true }).click()
  await expect(page.locator('#hex-viewport .mono').first()).toContainText('00000020')
  await page.getByLabel('読み取り専用16進ビュー').press('End')
  await expect(page.locator('#hex-viewport .mono').last()).toContainText(
    (base.length - 16).toString(16).toUpperCase().padStart(8, '0'),
  )
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({
    path: new URL('../../../outputs/web/mobile.png', import.meta.url).pathname,
    fullPage: true,
  })
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390)
  expect(errors).toEqual([])
})
test('large binary keeps rendering bounded and reaches the final bytes', async ({ page }) => {
  const large = Buffer.alloc(8 * 1024 * 1024)
  base.copy(large)
  large.writeUInt32LE(large.readUInt32LE(34) + large.length / 2, 38)
  large[32] = 0
  const sum = large.reduce((total, byte) => (total + byte) & 255, 0)
  large[32] = -sum & 255
  await page.goto('/')
  await page.getByLabel('YKI をインポート', { exact: true }).setInputFiles({
    name: 'large.yki',
    mimeType: 'application/octet-stream',
    buffer: large,
  })
  await expect(page.getByText('2 枚の登録済みメダルを読み込みました。')).toBeVisible()
  await page.getByLabel('16進オフセット').fill('7FFFF0')
  await page.getByRole('button', { name: '移動', exact: true }).click()
  await expect(page.locator('#hex-viewport .mono').last()).toContainText('007FFFF0')
  await expect(page.locator('#hex-viewport .mono')).toHaveCount(28)
  expect(
    await page.locator('#hex-viewport > div').evaluate((el) => el.getBoundingClientRect().height),
  ).toBeLessThanOrEqual(1000000)
  await page.getByRole('button', { name: 'ヘッダー', exact: true }).click()
  await expect(page.locator('#hex-viewport .mono').first()).toContainText('00000000')
})
test('header version edits are shared with export and saved in YKI', async ({ page }) => {
  await load(page)
  await page.getByRole('button', { name: 'ヘッダー', exact: true }).click()
  await page.getByLabel('バージョン', { exact: true }).selectOption('7')
  const versionOffset = (base.readUInt32LE(512) - base.readUInt32LE(34)) * 2 + 46
  await expect(page.locator(`#hex-viewport [data-offset="${versionOffset}"]`)).toHaveAttribute(
    'data-kind',
    'version',
  )
  await expect(page.locator(`#hex-viewport [data-offset="${versionOffset}"]`)).toHaveText('47')
  await page.getByRole('button', { name: 'エクスポート', exact: true }).click()
  await expect(page.getByLabel('読み上げバージョン')).toHaveValue('7')
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'YKI をエクスポート', exact: true }).click()
  const output = readFileSync((await (await download).path())!)
  const root = resource(output, 0) as Buffer
  expect(root.readUInt16LE(46)).toBe(64 + 7)
  await page.getByLabel('バージョン', { exact: true }).selectOption('inherit')
  await expect(page.locator(`#hex-viewport [data-offset="${versionOffset}"]`)).toHaveText('42')
  await page.getByRole('button', { name: 'エクスポート', exact: true }).click()
  await expect(page.getByLabel('読み上げバージョン')).toHaveValue('inherit')
})

test('invalid edits keep the last binary marked stale and recover with the latest change', async ({
  page,
}) => {
  await load(page)
  await page.getByLabel('うた / Song のソース').selectOption('file')
  const binary = page.getByRole('region', { name: 'バイナリ', exact: true })
  await expect(binary.getByRole('alert')).toContainText('編集内容は未反映')
  await page.getByLabel('うた / Song のソース').selectOption('builtin')
  await page.getByLabel('内蔵サウンド ID').fill('108')
  await page.getByLabel('内蔵サウンド ID').fill('109')
  await expect
    .poll(async () =>
      (await page.locator('#hex-viewport .hex-selected').allTextContents()).join(''),
    )
    .toBe('00006D00')
  await expect(binary.getByRole('alert')).toHaveCount(0)
  await page.getByRole('button', { name: 'ヘッダー', exact: true }).click()
  await page.getByLabel('バージョン', { exact: true }).selectOption('7')
  await expect
    .poll(async () =>
      (await page.locator('#hex-viewport .hex-selected').allTextContents()).join(''),
    )
    .toBe('00004700')
  await page.getByRole('button', { name: /B655.*うた/ }).click()
  await page.getByLabel('うた / Song のソース').focus()
  await expect
    .poll(async () =>
      (await page.locator('#hex-viewport .hex-selected').allTextContents()).join(''),
    )
    .toBe('00006D00')
})
