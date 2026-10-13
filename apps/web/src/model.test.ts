import { describe, it, expect } from 'vite-plus/test'
import { createCore, toHex } from '@nakasyou/yki-core'
import { readFileSync } from 'node:fs'
import {
  newProject,
  updateOverride,
  inheritSound,
  resetRow,
  audioPair,
  parseFrames,
  wav,
} from './model'
import type { Inspection } from './types'
// @ts-expect-error independent binary fixture
import { fixture } from '../../../packages/yki-core/tests/fixture.mjs'
const core = await createCore(
  readFileSync(new URL('../../../packages/yki-core/dist/yki-core.wasm', import.meta.url)),
)
const inspection = core.request({ op: 'describe', hex: toHex(fixture()) }) as unknown as Inspection
const project = { ...newProject(), inspection }
describe('editing a YKI project', () => {
  it('keeps sequential inherited settings while changing one field', () => {
    const original = {
      ...project,
      config: {
        ...project.config,
        overrides: [
          { id: 655, songSound: { builtin: 37 } },
          { id: 'B655', introSound: null },
        ],
      },
    }
    const edited = updateOverride(original, 655, { songSound: { builtin: 107 } })
    expect(edited.config.overrides).toEqual([
      { id: 655, songSound: { builtin: 107 }, introSound: null },
    ])
    expect(inheritSound(edited, 655, 'songSound').config.overrides).toEqual([
      { id: 655, introSound: null },
    ])
    expect(resetRow(edited, 655).config.overrides).toEqual([])
    expect(original.config.overrides.length).toBe(2)
  })
  it('initializes unused rows with an explicit type and resolves inherited sequence audio', () => {
    expect(
      updateOverride(project, 900, { nameSound: { builtin: 107 } }).config.overrides[0].type,
    ).toBe('normal')
    expect(audioPair(inspection.rows[654], inspection.resources, 'songSound')).toEqual([1, 4])
  })
  it('rejects invalid LED data and makes correct s16le WAV headers', () => {
    expect(parseFrames('[[255,0,1]]')).toEqual([[255, 0, 1]])
    expect(() => parseFrames('[[256,0,0]]')).toThrow()
    expect(() => parseFrames('[]')).toThrow()
    const result = wav(new Uint8Array(640))
    expect(new DataView(result).getUint32(40, true)).toBe(640)
    expect(result.byteLength).toBe(684)
  })
})
