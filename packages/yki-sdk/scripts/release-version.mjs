import { execFileSync } from 'node:child_process'
import { readFileSync, appendFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const cwd = fileURLToPath(new URL('..', import.meta.url))
const bump = process.env.BUMP
if (!['patch', 'minor', 'major'].includes(bump)) throw new Error('Invalid BUMP')
const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url)))
const registry = 'https://registry.npmjs.org'
const run = (command, args) => execFileSync(command, args, { cwd, encoding: 'utf8' }).trim()
let latest
try {
  latest = JSON.parse(run('npm', ['view', pkg.name, 'version', '--json', '--registry', registry]))
} catch (cause) {
  throw new Error(
    'Cannot read npm latest. Publish the initial version manually first; check registry connectivity and package access.',
    { cause },
  )
}
if (typeof latest !== 'string' || !/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(latest)) {
  throw new Error(`Expected a stable semantic version from npm, got ${JSON.stringify(latest)}`)
}
run('npm', ['version', latest, '--no-git-tag-version', '--allow-same-version', '--ignore-scripts'])
run('npm', ['version', bump, '--no-git-tag-version', '--ignore-scripts'])
const { version } = JSON.parse(readFileSync(new URL('../package.json', import.meta.url)))
const tag = `v${version}`
const response = await fetch(`${registry}/${encodeURIComponent(pkg.name)}/${version}`)
if (response.ok) throw new Error(`${pkg.name}@${version} already exists on npm`)
if (response.status !== 404)
  throw new Error(`Registry version check failed: HTTP ${response.status}`)
if (run('git', ['tag', '--list', tag])) throw new Error(`Git tag ${tag} already exists`)
if (!process.env.GITHUB_OUTPUT) throw new Error('GITHUB_OUTPUT is required')
appendFileSync(process.env.GITHUB_OUTPUT, `version=${version}\ntag=${tag}\n`)
console.log(`${pkg.name}: ${latest} -> ${version}`)
