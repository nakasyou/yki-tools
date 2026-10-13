import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, mkdtempSync, rmSync, writeFileSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { createCore } from '../js/index.mjs'

const core = await createCore(readFileSync(new URL('../dist/yki-core.wasm', import.meta.url)))
const template = readFileSync(
  new URL('../../3d-generator/templates/classical-yo-kai-medal.scad', import.meta.url),
  'utf8',
)
const cli = fileURLToPath(new URL('../../3d-generator/generate_medal.mjs', import.meta.url))

test('all modes and orientations preserve the complete original model', () => {
  for (const mode of ['normal', 'classic', 'lite']) {
    for (const orientation of ['canonical', 'physical']) {
      for (const mirror of [false, true]) {
        const rows = ['1011', '0110', '0001', '1010'].map((row) =>
          (orientation === 'canonical') !== mirror ? [...row].reverse().join('') : row,
        )
        let expected = template
        rows.forEach((row, i) => {
          expected = expected.replace(
            new RegExp(`code${i + 1} = "[01]+";`),
            `code${i + 1} = "${row}";`,
          )
        })
        expected = expected.replace('mode = "normal";', `mode = "${mode}";`)
        const result = core.generateMedal('1011 0110 0001 1010', { mode, orientation, mirror })
        assert.deepEqual(result.rows, rows)
        assert.equal(
          result.source,
          `// Generated bits (top to bottom, left to right): ${rows.join('/')}\n${expected}`,
        )
        assert.equal(result.filename, `medal_${rows.join('')}_${mode}.scad`)
      }
    }
  }
})

test('separators and arbitrary terminal bits work; invalid input is rejected', () => {
  const expected = core.generateMedal('1001010011100000')
  for (const bits of ['1001/0100/1110/0000', '1001,0100_1110-0000', '1001\t0100\n1110\u30000000'])
    assert.deepEqual(core.generateMedal(bits), expected)
  for (const bits of ['', '0000', '00000000000000000', '000000000000000x'])
    assert.throws(() => core.generateMedal(bits), /16桁/)
  assert.throws(() => core.generateMedal('0'.repeat(16), { mode: 'unknown' }), /モード/)
  assert.throws(() => core.generateMedal('0'.repeat(16), { orientation: 'unknown' }), /向き/)
  assert.throws(() => core.generateMedal('0'.repeat(16), { mirror: 'yes' }), /boolean/)
})

test('CLI writes SCAD, defaults filenames, and preserves output on rendering failure', () => {
  const directory = mkdtempSync(join(tmpdir(), 'medal-test-'))
  const run = (...args) =>
    spawnSync(process.execPath, [cli, ...args], { cwd: directory, encoding: 'utf8' })
  try {
    const result = run('1011', '0110', '0001', '1010', '--lite')
    assert.equal(result.status, 0, result.stderr)
    const expected = core.generateMedal('1011011000011010', { mode: 'lite' })
    assert.equal(readFileSync(join(directory, expected.filename), 'utf8'), expected.source)
    assert.equal(run('0'.repeat(16), '-o', 'nested/medal.scad').status, 0)
    assert.equal(run('0'.repeat(16), '--mode', 'normal', '--lite').status, 1)
    assert.equal(run('0'.repeat(16), '-o', 'bad.txt').status, 1)
    const target = join(directory, 'original.stl')
    writeFileSync(target, 'original')
    assert.equal(
      run('0'.repeat(16), '-o', target, '--openscad', join(directory, 'missing-openscad')).status,
      1,
    )
    assert.equal(readFileSync(target, 'utf8'), 'original')
    assert.ok(readdirSync(directory).every((name) => !name.startsWith('.medal-')))
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
})
