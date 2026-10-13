import type { Config, Led, Override, Sound, SoundField } from '@nakasyou/yki-core'
import type { Project, Medal, Resource, Pair } from './types'
export const soundFields: { key: SoundField; label: string; slot?: number }[] = [
  { key: 'songSound', label: 'うた / Song' },
  { key: 'summonSound', label: '召喚', slot: 0 },
  { key: 'nameSound', label: '名前', slot: 4 },
  { key: 'tribeSound', label: '種族', slot: 2 },
  { key: 'introSound', label: 'イントロ', slot: 5 },
  { key: 'postSound', label: '後奏', slot: 6 },
  { key: 'callSound', label: '呼びかけ', slot: 8 },
]
export function newProject(): Project {
  return {
    baseName: '',
    inspection: null,
    config: {
      extends: 'base.yki',
      overrides: [],
      audio: { frameAlignment: 'trim', volume: 'preserve' },
    },
    files: {},
    outputName: 'custom.yki',
    manifest: null,
  }
}
export function idRow(id: Override['id']): number | null {
  if (typeof id === 'number') return id
  if (typeof id === 'string' && /^[Bb]\d{1,3}$/.test(id)) return Number(id.slice(1))
  if (typeof id === 'object' && !Array.isArray(id) && 'medal' in id && !('sound' in id))
    return id.medal
  return null
}
export function rowOverride(project: Project, id: number): Override {
  return project.config.overrides
    .filter((edit) => idRow(edit.id) === id)
    .reduce<Override>((result, edit) => ({ ...result, ...edit }), { id })
}
export function updateOverride(project: Project, id: number, patch: Partial<Override>): Project {
  const previous = rowOverride(project, id)
  const edit = { ...previous, ...patch, id }
  if (project.inspection && !project.inspection.rows[id - 1].active && !edit.type)
    edit.type = project.inspection.rows[id - 1].type
  const overrides = project.config.overrides.filter((value) => idRow(value.id) !== id)
  overrides.push(edit)
  return { ...project, config: { ...project.config, overrides }, manifest: null }
}
export function inheritSound(project: Project, id: number, field: SoundField): Project {
  const edit = rowOverride(project, id)
  delete edit[field]
  return {
    ...project,
    config: {
      ...project.config,
      overrides: project.config.overrides
        .filter((value) => idRow(value.id) !== id)
        .concat(Object.keys(edit).length > 1 ? [edit] : []),
    },
    manifest: null,
  }
}
export function resetRow(project: Project, id: number): Project {
  return {
    ...project,
    config: {
      ...project.config,
      overrides: project.config.overrides.filter((edit) => idRow(edit.id) !== id),
    },
    manifest: null,
  }
}
export function audioPair(medal: Medal, resources: Resource[], field: SoundField): Pair | null {
  const slot = field === 'songSound' ? 1 : soundFields.find((value) => value.key === field)?.slot
  if (slot === undefined) return null
  const pair = medal.pairs[slot]
  if (pair[0] !== 1) return field === 'songSound' ? null : pair
  const asset = resources[pair[1]]
  if (asset?.kind === 'sequence') return asset.pairs[1]
  return field === 'songSound' ? null : pair
}
export function ledResource(medal: Medal, resources: Resource[]): number | null {
  const pair = medal.pairs[medal.type === 'song' ? 1 : 0]
  if (pair[0] !== 1 || resources[pair[1]]?.kind !== 'sequence') return null
  return resources[pair[1]].pairs[0][1]
}
export function inheritedLabel(medal: Medal, resources: Resource[], field: SoundField): string {
  const pair = audioPair(medal, resources, field)
  if (!pair || pair[0] === 65535 || pair[0] === 65534) return 'なし'
  if (pair[0] === 0) return `内蔵 #${pair[1]}`
  const resource = resources[pair[1]]
  return `音声 #${pair[1]}${resource?.duration !== undefined ? ` · ${resource.duration.toFixed(2)} 秒` : ''}`
}
export function soundMode(sound: Sound | undefined): string {
  if (sound === undefined) return 'inherit'
  if (sound === null) return 'none'
  if (typeof sound === 'string' || 'file' in sound) return 'file'
  return 'builtin' in sound ? 'builtin' : 'resource'
}
export function ledMode(led: Led | undefined): string {
  if (led === undefined) return 'inherit'
  if (led === null) return 'none'
  if (typeof led === 'string') return 'file'
  return 'resource' in led ? 'resource' : 'frames'
}
export function configJSON(project: Project): string {
  return JSON.stringify({ ...project.config, output: project.outputName }, null, 2)
}
export function parseFrames(value: string): [number, number, number][] {
  const frames: unknown = JSON.parse(value)
  if (
    !Array.isArray(frames) ||
    !frames.length ||
    frames.length > 100000 ||
    frames.some(
      (frame) =>
        !Array.isArray(frame) ||
        frame.length !== 3 ||
        frame.some((n) => !Number.isInteger(n) || n < 0 || n > 255),
    )
  )
    throw new Error('LED は [[r,g,b], …] の形式で、各色に 0〜255 を指定してください。')
  return frames as [number, number, number][]
}
export function download(data: BlobPart, name: string, type = 'application/octet-stream') {
  const url = URL.createObjectURL(new Blob([data], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
export function wav(pcm: Uint8Array): ArrayBuffer {
  const buffer = new ArrayBuffer(44 + pcm.byteLength)
  const view = new DataView(buffer)
  const bytes = new Uint8Array(buffer)
  const text = (offset: number, value: string) => bytes.set(new TextEncoder().encode(value), offset)
  text(0, 'RIFF')
  view.setUint32(4, buffer.byteLength - 8, true)
  text(8, 'WAVEfmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, 16000, true)
  view.setUint32(28, 32000, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  text(36, 'data')
  view.setUint32(40, pcm.length, true)
  bytes.set(pcm, 44)
  return buffer
}
