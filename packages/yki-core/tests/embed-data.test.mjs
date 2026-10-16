import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdtempSync, cpSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import { createCore } from '../js/index.mjs'
import { fixture } from './fixture.mjs'

const root = new URL('../', import.meta.url)
const schema = JSON.parse(readFileSync(new URL('data/schema.json', root), 'utf8'))
const lookup = JSON.parse(readFileSync(new URL('data/bump_confirmed_lookup.json', root), 'utf8'))
const evidence = JSON.parse(readFileSync(new URL('data/bump_lookup_evidence.json', root), 'utf8'))
const core = await createCore(readFileSync(new URL('dist/yki-core.wasm', root)))

test('compiled WASM uses the canonical schema, lookup and confidence evidence', () => {
  assert.deepEqual(core.schema(), schema)
  assert.equal(Object.keys(lookup).length, 166)
  assert.equal(Object.keys(evidence).length, 34)
  for (const [rail, row] of Object.entries(lookup)) {
    const reply = core.resolve(fixture(), `${rail}A`)
    assert.equal(reply.resolution.row, row)
    assert.equal(
      reply.resolution.confidence,
      evidence[rail]?.physical_printed_B_verified ? 'high' : 'medium',
    )
  }
})

test('tracked generated sources match the official embed command', () => {
  const directory = mkdtempSync(join(tmpdir(), 'yki-embed-'))
  try {
    for (const [name, file] of [
      ['schema_json', 'schema'],
      ['bump_lookup_json', 'bump_confirmed_lookup'],
      ['bump_evidence_json', 'bump_lookup_evidence'],
    ]) {
      const output = join(directory, `${file}.mbt`)
      const result = spawnSync(
        'moon',
        [
          'tool',
          'embed',
          '--text',
          '--input',
          fileURLToPath(new URL(`data/${file}.json`, root)),
          '--output',
          output,
          '--name',
          name,
        ],
        { encoding: 'utf8' },
      )
      assert.equal(result.status, 0, result.stderr)
      assert.equal(
        readFileSync(new URL(`${file}.generated.mbt`, root), 'utf8'),
        readFileSync(output, 'utf8'),
      )
    }
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
})

test('Moon build rules embed JSON edits and the WASM build rejects malformed JSON', async () => {
  const directory = mkdtempSync(join(tmpdir(), 'yki-build-'))
  try {
    cpSync(root, directory, {
      recursive: true,
      filter: (source) =>
        !source
          .split(/[\\/]/)
          .some((part) => ['_build', 'dist', 'node_modules', '.mooncakes'].includes(part)) &&
        !source.endsWith('.generated.mbt'),
    })
    const build = () =>
      spawnSync('moon', ['build', '--target', 'wasm', '--release'], {
        cwd: directory,
        encoding: 'utf8',
      })
    const changed = { ...schema, title: 'Official embedding test' }
    const input = join(directory, 'data/schema.json')
    writeFileSync(input, JSON.stringify(changed))
    let result = build()
    assert.equal(result.status, 0, result.stderr)
    const wasm = join(directory, '_build/wasm/release/build/wasm/wasm.wasm')
    assert.deepEqual((await createCore(readFileSync(wasm))).schema(), changed)
    changed.title = 'Updated JSON input'
    writeFileSync(input, JSON.stringify(changed))
    result = build()
    assert.equal(result.status, 0, result.stderr)
    assert.deepEqual((await createCore(readFileSync(wasm))).schema(), changed)
    const previous = readFileSync(wasm)
    writeFileSync(input, '{broken')
    result = spawnSync(process.execPath, [join(directory, 'scripts/build.mjs')], {
      encoding: 'utf8',
    })
    assert.notEqual(result.status, 0)
    assert.deepEqual(readFileSync(wasm), previous)
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
})
