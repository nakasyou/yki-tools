#!/usr/bin/env node
import {
  readFileSync,
  writeFileSync,
  mkdirSync,
  renameSync,
  rmSync,
  mkdtempSync,
  realpathSync,
  existsSync,
} from 'node:fs'
import { dirname, resolve, extname, basename, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createCore } from '@nakasyou/yki-core'
import { createNodeHost } from '@nakasyou/yki-core/node-host'

function canonical(path: string): string {
  const absolute = resolve(path)
  if (existsSync(absolute)) return realpathSync(absolute)
  const parent = dirname(absolute)
  return parent === absolute ? absolute : join(canonical(parent), basename(absolute))
}
function atomicWrite(path: string, data: string | Uint8Array) {
  mkdirSync(dirname(path), { recursive: true })
  const directory = mkdtempSync(join(dirname(path), '.yki-core-'))
  try {
    const staging = join(directory, 'output')
    writeFileSync(staging, data)
    renameSync(staging, path)
  } finally {
    rmSync(directory, { recursive: true, force: true })
  }
}
async function main() {
  const args = process.argv.slice(2)
  const command = args.shift()
  if (!command || command === '--help' || command === '-h') {
    console.log(
      'Usage: yki-core <build|validate|inspect|schema> [file|-] [-o output.yki] [--base-dir directory] [--strict-mapping]',
    )
    return
  }
  let file: string | undefined,
    output: string | undefined,
    baseDir: string | undefined,
    strict = false
  while (args.length) {
    const arg = args.shift()!
    if (arg === '-o' || arg === '--output') {
      if (!args.length) throw new Error('Missing output')
      output = args.shift()
    } else if (arg === '--base-dir') {
      if (!args.length) throw new Error('Missing base directory')
      baseDir = args.shift()
    } else if (arg === '--strict-mapping') strict = true
    else if (arg.startsWith('-') && arg !== '-') throw new Error(`Unknown argument: ${arg}`)
    else if (file === undefined) file = arg
    else throw new Error('Too many files')
  }
  if (command !== 'schema' && !file) throw new Error('Input file required')
  const configPath = file === '-' ? canonical('stdin.json') : file ? canonical(file) : undefined
  const directory = baseDir ? canonical(baseDir) : configPath ? dirname(configPath) : process.cwd()
  const adapter = createNodeHost({
    baseDir: directory,
    ffmpeg: process.env.FFMPEG ?? 'ffmpeg',
  })
  try {
    const core = await createCore(
      readFileSync(fileURLToPath(import.meta.resolve('@nakasyou/yki-core/wasm'))),
      { host: adapter.host },
    )
    if (command === 'schema') {
      console.log(JSON.stringify(core.schema(), null, 2))
      return
    }
    if (command === 'inspect') {
      console.log(
        JSON.stringify({ ...core.inspect(readFileSync(configPath!)), file: configPath }, null, 2),
      )
      return
    }
    if (!['validate', 'build'].includes(command)) throw new Error(`Unknown command: ${command}`)
    const config = JSON.parse(readFileSync(file === '-' ? 0 : configPath!, 'utf8'))
    if (command === 'validate') {
      const result = core.validate(config, strict) as { warnings: string[] }
      for (const warning of result.warnings) console.error(`warning: ${warning}`)
      console.log(JSON.stringify(result, null, 2))
      return
    }
    if (file === '-' && !output && !config.output)
      throw new Error('Standard input requires --output or the JSON output field')
    const target = canonical(
      output
        ? output
        : config.output
          ? resolve(directory, config.output)
          : configPath!.slice(0, configPath!.length - extname(configPath!).length) + '.yki',
    )
    if (extname(target).toLowerCase() !== '.yki')
      throw new Error('Output must have the .yki extension')
    const manifestPath = target.slice(0, -4) + '.manifest.json'
    const source = canonical(
      adapter.resolvePath(
        Number.isInteger(config.extends) ? `@stock/Ver${config.extends}_U.yki` : config.extends,
      ),
    )
    if ([target, manifestPath].some((p) => p === source || p === configPath))
      throw new Error('Output must not overwrite input YKI or JSON config')
    const result = core.build(config, strict)
    const manifest = {
      ...result.manifest,
      source,
      output: target,
      config: file === '-' ? '<stdin>' : configPath,
      path_base: directory,
    }
    for (const warning of manifest.warnings) console.error(`warning: ${warning}`)
    const encoded = JSON.stringify(manifest, null, 2) + '\n'
    atomicWrite(target, result.data)
    atomicWrite(manifestPath, encoded)
    console.log(target)
    console.log(`manifest: ${manifestPath}`)
  } finally {
    adapter.close()
  }
}
main().catch((error) => {
  console.error(`error: ${error.message}`)
  process.exitCode = 1
})
