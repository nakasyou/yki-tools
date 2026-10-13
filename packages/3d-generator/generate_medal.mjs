#!/usr/bin/env node
// Host adapter only: bit validation, orientation and model generation run in MoonBit.
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  mkdtempSync,
  renameSync,
  rmSync,
  statSync,
} from 'node:fs'
import { dirname, extname, join, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'
import { createCore } from '../yki-core/js/index.mjs'

async function main() {
  const args = process.argv.slice(2)
  const bits = []
  const options = {}
  let output
  let openscad = 'openscad'
  let selectedMode = false
  let positional = false
  while (args.length) {
    const arg = args.shift()
    if (!positional && (arg === '--help' || arg === '-h')) {
      console.log(
        'Usage: pnpm medal <16 bits | four rows> [-o output.scad|output.stl] [--mode normal|classic|lite | --lite] [--orientation canonical|physical] [--mirror] [--openscad executable]',
      )
      return
    }
    if (!positional && arg === '--') {
      positional = true
      continue
    }
    if (!positional && ['-o', '--output', '--mode', '--orientation', '--openscad'].includes(arg)) {
      if (!args.length) throw new Error(`Missing value for ${arg}`)
      const value = args.shift()
      if (arg === '-o' || arg === '--output') output = value
      else if (arg === '--openscad') openscad = value
      else if (arg === '--orientation') options.orientation = value
      else {
        if (selectedMode) throw new Error('Specify only one of --mode or --lite')
        selectedMode = true
        options.mode = value
      }
    } else if (!positional && arg === '--lite') {
      if (selectedMode) throw new Error('Specify only one of --mode or --lite')
      selectedMode = true
      options.mode = 'lite'
    } else if (!positional && arg === '--mirror') options.mirror = true
    else if (!positional && arg.startsWith('-')) throw new Error(`Unknown argument: ${arg}`)
    else bits.push(arg)
  }
  const core = await createCore(
    readFileSync(new URL('../yki-core/dist/yki-core.wasm', import.meta.url)),
  )
  const medal = core.generateMedal(bits.join(' '), options)
  const target = resolve(output ?? medal.filename)
  const suffix = extname(target).toLowerCase()
  if (!['.scad', '.stl'].includes(suffix))
    throw new Error('出力ファイルの拡張子は.scadまたは.stlにしてください')
  mkdirSync(dirname(target), { recursive: true })
  const temp = mkdtempSync(join(dirname(target), '.medal-'))
  try {
    const source = join(temp, 'medal.scad')
    writeFileSync(source, medal.source, 'utf8')
    let staging = source
    if (suffix === '.stl') {
      staging = join(temp, 'medal.stl')
      const result = spawnSync(openscad, ['-o', staging, source], { stdio: 'inherit' })
      if (result.error) throw new Error(`STL出力にはOpenSCADが必要です: ${result.error.message}`)
      if (result.status !== 0)
        throw new Error(`OpenSCAD failed (${result.signal ?? result.status})`)
      if (statSync(staging).size === 0) throw new Error('OpenSCADがSTLを生成しませんでした')
    }
    renameSync(staging, target)
  } finally {
    rmSync(temp, { recursive: true, force: true })
  }
  console.log(`${target} (mode: ${medal.mode}, bits: ${medal.rows.join('/')})`)
}

main().catch((error) => {
  console.error(`error: ${error.message}`)
  process.exitCode = 1
})
