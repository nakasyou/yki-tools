import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync, mkdtempSync, writeFileSync, rmSync, symlinkSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { tmpdir } from 'node:os'
import { resolve, dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import { createCore, toHex } from '../js/index.mjs'
import { fixture, fixChecksum, resource, row } from './fixture.mjs'
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const wasm = readFileSync(join(root, 'dist/yki-core.wasm'))
const base = fixture()
const host = (request) => {
  if (request.op === 'read') return { hex: toHex(base) }
  throw new Error(`Unexpected media capability: ${request.op}`)
}
const core = await createCore(wasm, { host })
const build = (overrides) => core.build({ extends: 2, overrides })
test('portable WASM imports and independent instances', async () => {
  const module = await WebAssembly.compile(wasm)
  assert.deepEqual(WebAssembly.Module.imports(module), [
    { module: 'yki_host', name: 'rpc', kind: 'function' },
  ])
  const isolated = await createCore(wasm)
  assert.equal(isolated.inspect(base).version, 2)
  assert.throws(() => isolated.build({ extends: 2, overrides: [] }), /Host capability required/)
  assert.equal(core.inspect(base).sha256, createHash('sha256').update(base).digest('hex'))
})
test('lossless roundtrip and build with spoken version zero', () => {
  assert.deepEqual(Buffer.from(core.roundtrip(base)), base)
  assert.deepEqual(Buffer.from(build([]).data), base)
  const zero = Buffer.from(core.build({ extends: 2, version: 0, overrides: [] }).data)
  assert.equal(core.inspect(zero).version, 0)
  assert.deepEqual(
    [...zero.keys()].filter((i) => zero[i] !== base[i]),
    [46, (base.readUInt32LE(512) - 0x500800) * 2 + 46],
  )
})
test('all six local stock files roundtrip', (t) => {
  if (!existsSync(join(root, '../../yki/Ver2_U.yki'))) {
    t.skip('Stock files are local, not distributed')
    return
  }
  for (let version = 2; version <= 7; version++) {
    const data = readFileSync(join(root, `../../yki/Ver${version}_U.yki`))
    assert.deepEqual(Buffer.from(core.roundtrip(data)), data, `Ver${version}`)
  }
})
test('all ID forms, sound namespaces, ambiguity and strict confidence', () => {
  for (const id of [
    655,
    'B655',
    { medal: 655 },
    'E7BA',
    { bumpsHex: '0xE7BA' },
    ['1110', '0111', '1011', '1010'],
    { bumps: ['1110', '0111', '1011', '1010'] },
    '7ED5',
  ])
    assert.equal(core.resolve(base, id, true).resolution.row, 655)
  assert.equal(core.resolve(base, { sound: 117 }).resolution.row, 1)
  assert.equal(
    core.resolve(base, { sound: 4, namespace: 'resource', field: 'songSound', medal: 655 })
      .resolution.row,
    655,
  )
  assert.throws(() => core.resolve(base, 'F12A', true), /confidence/)
  assert.throws(() => core.resolve(base, '000A'), /no known/)
  assert.throws(() => core.resolve(base, 'E7B'), /four nibbles/)
})
test('copy-on-write retains sequence and audio; LED repeat excludes terminators', () => {
  const result = build([{ id: 655, songSound: { builtin: 107 }, led: { resource: 2, repeat: 3 } }])
  const data = Buffer.from(result.data)
  const sequence = resource(data, row(data, 655)[1][1])
  const newLed = resource(data, sequence.readUInt16LE(2))
  assert.deepEqual(
    newLed,
    Buffer.from('ffff010002000300010002000300010002000300ffffffffffff', 'hex'),
  )
  assert.equal(sequence.readUInt16LE(4), 0)
  assert.equal(sequence.readUInt16LE(6), 107)
  const originalSeq = result.manifest.handle_to_output_resource['3']
  assert.equal(resource(data, originalSeq).readUInt16LE(4), 1)
  assert.deepEqual(
    resource(data, result.manifest.handle_to_output_resource['4']).subarray(0, 72),
    resource(base, 4).subarray(0, 72),
  )
})
test('new medals, type conversions, sequential changes, clearing and explicit template', () => {
  const data = Buffer.from(
    build([
      { id: 900, type: 'song', template: 655, songSound: { resource: 4 } },
      {
        id: 901,
        type: 'normal',
        nameSound: { resource: 4 },
        summonSound: { builtin: 37 },
        led: { frames: [[1, 2, 3]] },
      },
    ]).data,
  )
  assert.deepEqual(row(data, 900)[0], [65534, 65534])
  assert.equal(row(data, 901)[0][0], 1)
  assert.throws(() => build([{ id: 900, nameSound: { resource: 4 } }]), /require type/)
  assert.throws(() => build([{ id: 900, type: 'song' }]), /requires? songSound/)
  assert.throws(() => build([{ id: 1, songSound: { resource: 4 } }]), /only valid/)
  assert.throws(() => build([{ id: 655, type: 'normal' }]), /type conversion requires/)
  const converted = Buffer.from(
    build([
      { id: 1, type: 'song', songSound: { resource: 4 } },
      { id: 1, introSound: null },
      { id: 1, songSound: { builtin: 107 } },
    ]).data,
  )
  assert.deepEqual(row(converted, 1)[0], [65534, 65534])
  assert.deepEqual(row(converted, 1)[5], [65535, 65535])
  const cleared = Buffer.from(build([{ id: 655, songSound: null }]).data)
  assert.deepEqual(row(cleared, 655)[1], [65535, 65535])
  assert.throws(() => build([{ id: 655, songSound: null, led: null }]), /null songSound/)
})
test('schema, reference kind errors, malformed files and recovery after failures', () => {
  for (const id of ['B661', 'b661', 'B900', '0xB661', { bumpsHex: 'B661' }, 'B61A', 'E83A']) {
    core.validateConfig({ extends: 2, overrides: [{ id }] })
  }
  for (const override of [
    { id: true },
    { id: 655, songSond: 'x' },
    { id: 655, led: { frames: [[256, 0, 0]] } },
    { id: 655, type: 'normal', songSound: 'x' },
    { id: 655, led: { resource: 2, repeat: 0 } },
  ])
    assert.throws(() => build([override]), /schema|configuration/)
  assert.throws(() => build([{ id: 655, songSound: { resource: 2 } }]), /not an AU/)
  assert.throws(() => build([{ id: 655, led: { resource: 4 } }]), /not an RGB/)
  const checksum = Buffer.from(base)
  checksum[1000] ^= 1
  assert.throws(() => core.inspect(checksum), /checksum/)
  const pointer = Buffer.from(base)
  pointer.writeUInt32LE(0x500800, 512)
  fixChecksum(pointer)
  assert.throws(() => core.inspect(pointer), /gap/)
  const led = Buffer.from(base)
  const offset = (led.readUInt32LE(520) - 0x500800) * 2
  led.writeUInt16LE(256, offset + 2)
  fixChecksum(led)
  assert.throws(() => core.inspect(led), /LED channel/)
  assert.equal(core.inspect(base).version, 2)
})
test('CLI stdin, relative bases and failure preserves existing output', () => {
  const directory = mkdtempSync(join(tmpdir(), 'yki-core-test-'))
  try {
    writeFileSync(join(directory, 'base.yki'), base)
    const target = join(directory, 'out.yki')
    const run = (config) =>
      spawnSync(
        process.execPath,
        [
          join(root, '../../apps/cli/dist/index.mjs'),
          'build',
          '-',
          '--base-dir',
          directory,
          '-o',
          target,
        ],
        { input: JSON.stringify(config), encoding: 'utf8' },
      )
    const good = run({ extends: 'base.yki', version: 0, overrides: [] })
    assert.equal(good.status, 0, good.stderr)
    const before = readFileSync(target)
    const manifest = readFileSync(join(directory, 'out.manifest.json'))
    const bad = run({ extends: 'base.yki', overrides: [{ id: '000A' }] })
    assert.notEqual(bad.status, 0)
    assert.match(bad.stderr, /no known/)
    assert.deepEqual(readFileSync(target), before)
    assert.deepEqual(readFileSync(join(directory, 'out.manifest.json')), manifest)
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
})

test('editing an aliased medal preserves the other medal and sound lookup rejects ambiguity', async () => {
  const shared = Buffer.from(base)
  const tableOffset = (shared.readUInt32LE(516) - 0x500800) * 2
  shared.copy(shared, tableOffset + 655 * 36, tableOffset + 654 * 36, tableOffset + 655 * 36)
  shared.writeUInt16LE(0, tableOffset + 36 + 16)
  shared.writeUInt16LE(117, tableOffset + 36 + 18)
  fixChecksum(shared)
  const instance = await createCore(wasm, { host: (request) => ({ hex: toHex(shared) }) })
  assert.throws(() => instance.resolve(shared, { sound: 117 }), /matches rows \[1, 2\]/)
  assert.equal(instance.resolve(shared, { sound: 117, medal: 2 }).resolution.row, 2)
  const data = Buffer.from(
    instance.build({ extends: 2, overrides: [{ id: 655, songSound: { builtin: 107 } }] }).data,
  )
  const changed = resource(data, row(data, 655)[1][1])
  const unchanged = resource(data, row(data, 656)[1][1])
  assert.equal(changed.readUInt16LE(4), 0)
  assert.equal(changed.readUInt16LE(6), 107)
  assert.equal(unchanged.readUInt16LE(4), 1)
})
test('external LED JSON has identical expansion and rejects invalid channels', async () => {
  let led = { frames: [[1, 2, 3]], repeat: 2 }
  const instance = await createCore(wasm, {
    host: (request) => ({
      hex: toHex(
        request.path === 'led.json' ? new TextEncoder().encode(JSON.stringify(led)) : base,
      ),
    }),
  })
  const actual = instance.build({ extends: 2, overrides: [{ id: 655, led: 'led.json' }] })
  const expected = build([{ id: 655, led }])
  assert.deepEqual(actual.data, expected.data)
  led = { frames: [[999, 2, 3]] }
  assert.throws(
    () => instance.build({ extends: 2, overrides: [{ id: 655, led: 'led.json' }] }),
    /channels/,
  )
})
test('CLI rejects output aliases pointing to the source', () => {
  const directory = mkdtempSync(join(tmpdir(), 'yki-core-symlink-'))
  try {
    const source = join(directory, 'base.yki')
    writeFileSync(source, base)
    const alias = join(directory, 'alias.yki')
    symlinkSync(source, alias)
    const result = spawnSync(
      process.execPath,
      [
        join(root, '../../apps/cli/dist/index.mjs'),
        'build',
        '-',
        '--base-dir',
        directory,
        '-o',
        alias,
      ],
      {
        input: JSON.stringify({ extends: 'base.yki', version: 0, overrides: [] }),
        encoding: 'utf8',
      },
    )
    assert.notEqual(result.status, 0)
    assert.match(result.stderr, /must not overwrite/)
    assert.deepEqual(readFileSync(source), base)
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
})
