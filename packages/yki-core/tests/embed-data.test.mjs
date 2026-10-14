import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, writeFileSync, mkdirSync, mkdtempSync, cpSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
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

test('build-time generator detects stale output, embeds edits and rejects invalid JSON', () => {
  const directory = mkdtempSync(join(tmpdir(), 'yki-data-'))
  try {
    mkdirSync(join(directory, 'scripts'))
    cpSync(new URL('scripts/embed-data.mjs', root), join(directory, 'scripts/embed-data.mjs'))
    cpSync(new URL('data/', root), join(directory, 'data'), { recursive: true })
    cpSync(new URL('data.mbt', root), join(directory, 'data.mbt'))
    const run = (...args) =>
      spawnSync(process.execPath, [join(directory, 'scripts/embed-data.mjs'), ...args], {
        encoding: 'utf8',
      })
    assert.equal(run('--check').status, 0)
    const changed = { ...schema, title: 'Build-time embedding test' }
    writeFileSync(join(directory, 'data/schema.json'), JSON.stringify(changed))
    assert.notEqual(run('--check').status, 0)
    assert.equal(run().status, 0)
    assert.equal(run('--check').status, 0)
    const generated = readFileSync(join(directory, 'data.mbt'), 'utf8')
    const match = generated.match(/let schema_json : String = ("(?:\\.|[^"\\])*")/)
    assert.deepEqual(JSON.parse(JSON.parse(match[1])), changed)
    writeFileSync(join(directory, 'data/schema.json'), '{broken')
    assert.notEqual(run().status, 0)
    assert.equal(readFileSync(join(directory, 'data.mbt'), 'utf8'), generated)
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
})
