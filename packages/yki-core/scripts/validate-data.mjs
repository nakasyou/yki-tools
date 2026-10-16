import { readFileSync } from 'node:fs'

// moon tool embed copies text verbatim; reject malformed JSON before building WASM.
for (const file of ['schema', 'bump_confirmed_lookup', 'bump_lookup_evidence']) {
  JSON.parse(readFileSync(new URL(`../data/${file}.json`, import.meta.url), 'utf8'))
}
