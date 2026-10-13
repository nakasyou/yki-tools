import { effect, track, untrack } from 'ripple'
import { binaryRegions, resourceOffsets } from './binary'
import type { BinaryRange, BinaryRegion } from './binary'
import type { Config, Led, Override, Sound, SoundField, Manifest } from '@nakasyou/yki-core'
import type { Inspection, Project } from './types'
import { call } from './client'
import {
  newProject,
  rowOverride,
  updateOverride,
  inheritSound,
  resetRow,
  soundFields,
  ledMode,
  ledResource,
  configJSON,
  parseFrames,
  download,
  wav,
  idRow,
  audioPair,
} from './model'

export function createEditor() {
  const project = track(newProject())
  const selected = track(655)
  const query = track('')
  const showEmpty = track(false)
  const tab = track('sound')
  const busy = track(false)
  const status = track('')
  let statusTimer: ReturnType<typeof setTimeout> | undefined
  const notify = (message: string, persistent = false) => {
    clearTimeout(statusTimer)
    status.value = message
    if (message && !persistent) {
      statusTimer = setTimeout(() => {
        status.value = ''
      }, 5000)
    }
  }
  const error = track('')
  const jsonDraft = track('')
  const framesDraft = track('[[255, 0, 0], [0, 255, 0], [0, 0, 255]]')
  const sourceRevision = track(0)
  const binaryFile = track<File | null>(null)
  const binaryUpdating = track(false)
  const binaryError = track('')
  const binaryOffsets = track<number[]>([])
  const binaryAreas = track<BinaryRegion[]>([])
  const binaryInspection = track<Inspection | null>(null)
  let binaryMapping: Record<string, number> = {}
  const binaryFocus = track<BinaryRange>({ offset: 0, length: 512, label: 'ヘッダー' })
  const detail = track<'header' | 'medal'>('medal')
  type FocusTarget =
    | { kind: 'header' }
    | { kind: 'version' }
    | { kind: 'medal'; row: number }
    | { kind: 'led'; row: number }
    | { kind: 'sound'; row: number; field: SoundField }
    | { kind: 'resource'; resource: number; label: string }
  let focusTarget: FocusTarget = { kind: 'header' }
  const refreshFocus = () => {
    const inspection = binaryInspection.value
    const target = focusTarget
    if (target.kind === 'header') {
      binaryFocus.value = { offset: 0, length: 512, label: 'ヘッダー' }
      return
    }
    if (target.kind === 'version') {
      binaryFocus.value = {
        offset: (binaryOffsets.value[0] ?? 0) + 44,
        length: 4,
        label: 'バージョン',
      }
      return
    }
    if (!inspection) return
    const resourceRange = (id: number | null, label: string) => {
      if (id === null || binaryOffsets.value[id] === undefined) return false
      binaryFocus.value = {
        offset: binaryOffsets.value[id],
        length: inspection.resources[id].bytes,
        label,
      }
      return true
    }
    if (target.kind === 'resource') {
      resourceRange(binaryMapping[String(target.resource)] ?? target.resource, target.label)
      return
    }
    const medal = inspection.rows[target.row - 1]
    const rowOffset = (binaryOffsets.value[1] ?? 0) + (target.row - 1) * 36
    if (target.kind === 'medal') {
      binaryFocus.value = { offset: rowOffset, length: 36, label: `B${target.row}` }
      return
    }
    if (target.kind === 'led') {
      if (!resourceRange(ledResource(medal, inspection.resources), 'LED パターン'))
        binaryFocus.value = { offset: rowOffset, length: 36, label: 'LED パターン' }
      return
    }
    const pair = audioPair(medal, inspection.resources, target.field)
    if (pair?.[0] === 1 && resourceRange(pair[1], target.field)) return
    const slot =
      target.field === 'songSound'
        ? 1
        : (soundFields.find((field) => field.key === target.field)?.slot ?? 0)
    const source = medal.pairs[slot]
    const sequence = source[0] === 1 && inspection.resources[source[1]]?.kind === 'sequence'
    binaryFocus.value = {
      offset: sequence ? binaryOffsets.value[source[1]] + 4 : rowOffset + slot * 4,
      length: 4,
      label: target.field,
    }
  }
  const focusHeader = () => {
    detail.value = 'header'
    focusTarget = { kind: 'header' }
    refreshFocus()
  }
  const focusMedal = (id = selected.value) => {
    detail.value = 'medal'
    focusTarget = { kind: 'medal', row: id }
    refreshFocus()
  }
  const focusResource = (resource: number | null, label: string) => {
    focusTarget =
      resource === null
        ? { kind: 'medal', row: selected.value }
        : { kind: 'resource', resource, label }
    refreshFocus()
  }
  const focusSound = (field: SoundField) => {
    focusTarget = { kind: 'sound', row: selected.value, field }
    refreshFocus()
  }
  const focusLED = () => {
    focusTarget = { kind: 'led', row: selected.value }
    refreshFocus()
  }
  const preview = track('')
  let previewURL = ''

  const fail = (cause: unknown) => {
    clearTimeout(statusTimer)
    status.value = ''
    error.value = cause instanceof Error ? cause.message : String(cause)
  }
  const focusVersion = () => {
    focusTarget = { kind: 'version' }
    refreshFocus()
  }
  const setVersion = (value: string) => {
    focusVersion()
    const config = { ...project.value.config }
    if (value === 'inherit') delete config.version
    else config.version = Number(value)
    project.value = { ...project.value, config, manifest: null }
  }
  type BinaryArtifact = {
    file: File
    inspection: Inspection
    offsets: number[]
    manifest: Manifest
  }
  const fileIds = new WeakMap<File, number>()
  let nextFileId = 0
  const currentInput = () => {
    const configJSON = JSON.stringify(project.value.config)
    const files = { ...project.value.files }
    const fileKey = Object.entries(files).map(([name, file]) => {
      if (!fileIds.has(file)) fileIds.set(file, ++nextFileId)
      return [name, fileIds.get(file)]
    })
    const source = sourceRevision.value
    return {
      source,
      config: JSON.parse(configJSON) as Config,
      files,
      key: JSON.stringify([source, configJSON, fileKey]),
    }
  }
  let cached: { key: string; artifact: BinaryArtifact } | null = null
  let running: Promise<BinaryArtifact> | null = null
  let baseline: { key: string; file: File; inspection: Inspection; offsets: number[] } | null = null
  const publish = (artifact: BinaryArtifact) => {
    binaryInspection.value = artifact.inspection
    binaryMapping = artifact.manifest.handle_to_output_resource
    binaryOffsets.value = artifact.offsets
    binaryAreas.value = binaryRegions(
      artifact.offsets,
      artifact.inspection.resources,
      artifact.file.size,
    )
    binaryFile.value = artifact.file
    binaryUpdating.value = false
    binaryError.value = ''
    refreshFocus()
  }
  const ensureBinary = async (): Promise<BinaryArtifact> => {
    for (;;) {
      const input = untrack(currentInput)
      if (cached?.key === input.key) {
        publish(cached.artifact)
        return cached.artifact
      }
      if (running) {
        await running.catch(() => {})
        continue
      }
      binaryUpdating.value = true
      running = (async () => {
        const result = await call<{
          data: Uint8Array<ArrayBuffer>
          inspection: Inspection
          manifest: Manifest
        }>('binary', { config: input.config, files: input.files })
        const file = new File([result.data], 'preview.yki', {
          type: 'application/octet-stream',
        })
        return {
          file,
          inspection: result.inspection,
          offsets: await resourceOffsets(file),
          manifest: result.manifest,
        }
      })()
      try {
        const artifact = await running
        if (input.key === untrack(currentInput).key) {
          cached = { key: input.key, artifact }
          publish(artifact)
          return artifact
        }
      } catch (cause) {
        if (input.key === untrack(currentInput).key) {
          binaryUpdating.value = false
          binaryError.value = cause instanceof Error ? cause.message : String(cause)
          throw cause
        }
      } finally {
        running = null
      }
    }
  }
  effect(() => {
    const input = currentInput()
    if (!project.value.inspection) return
    const unchanged = untrack(() => {
      binaryError.value = ''
      if (cached?.key === input.key) {
        binaryUpdating.value = false
        return true
      }
      if (baseline?.key === input.key) {
        binaryUpdating.value = false
        if (binaryFile.value !== baseline.file) {
          binaryInspection.value = baseline.inspection
          binaryMapping = {}
          binaryOffsets.value = baseline.offsets
          binaryAreas.value = binaryRegions(
            baseline.offsets,
            baseline.inspection.resources,
            baseline.file.size,
          )
          binaryFile.value = baseline.file
          refreshFocus()
        }
        return true
      }
      binaryUpdating.value = true
      return false
    })
    if (unchanged) return
    const timer = setTimeout(() => {
      void ensureBinary().catch(() => {})
    }, 300)
    return () => clearTimeout(timer)
  })
  const patch = (edit: Partial<Override>) => {
    project.value = updateOverride(project.value, selected.value, edit)
  }
  const selectedType = () =>
    rowOverride(project.value, selected.value).type ??
    project.value.inspection?.rows[selected.value - 1].type ??
    'song'
  const setSound = (field: SoundField, value: Sound | undefined) => {
    project.value =
      value === undefined
        ? inheritSound(project.value, selected.value, field)
        : updateOverride(project.value, selected.value, { [field]: value })
  }
  const addSound = (field: SoundField, file: File) => {
    const name = `media/B${selected.value}-${field}-${file.name}`
    project.value = {
      ...project.value,
      files: { ...project.value.files, [name]: file },
    }
    setSound(field, name)
  }
  const loadBase = async (file: File) => {
    busy.value = true
    error.value = ''
    notify('YKI のチェックサムとリソースを解析中…', true)
    try {
      const bytes = await file.arrayBuffer()
      const offsets = await resourceOffsets(file)
      const inspection = await call<Inspection>('load', { bytes })
      project.value = {
        ...newProject(),
        baseName: file.name,
        inspection,
        outputName: `${file.name.replace(/\.yki$/i, '')}_custom.yki`,
      }
      selected.value = inspection.rows[654].active
        ? 655
        : (inspection.rows.find((row) => row.active)?.id ?? 1)
      sourceRevision.value++
      cached = null
      binaryInspection.value = inspection
      binaryMapping = {}
      baseline = { key: untrack(currentInput).key, file, inspection, offsets }
      binaryFile.value = file
      binaryOffsets.value = offsets
      binaryAreas.value = binaryRegions(offsets, inspection.resources, file.size)
      focusMedal()
      notify(
        `${
          inspection.rows.filter((row) => row.active).length
        } 枚の登録済みメダルを読み込みました。`,
      )
    } catch (cause) {
      fail(cause)
    } finally {
      busy.value = false
    }
  }
  const previewSound = async (field: SoundField) => {
    error.value = ''
    const pair = audioPair(
      project.value.inspection!.rows[selected.value - 1],
      project.value.inspection!.resources,
      field,
    )
    if (!pair || pair[0] !== 1 || project.value.inspection!.resources[pair[1]]?.kind !== 'audio') {
      return
    }
    busy.value = true
    notify('元の音声をデコード中…', true)
    try {
      const pcm = await call<Uint8Array>('preview', { resource: pair[1] })
      if (previewURL) URL.revokeObjectURL(previewURL)
      previewURL = URL.createObjectURL(new Blob([wav(pcm)], { type: 'audio/wav' }))
      preview.value = previewURL
      notify('元の音声を試聴できます。')
    } catch (cause) {
      fail(cause)
    } finally {
      busy.value = false
    }
  }
  const applyJSON = async (value: string) => {
    error.value = ''
    busy.value = true
    try {
      const config = JSON.parse(value) as Config
      await call('validateConfig', { config })
      const edits: Override[] = []
      for (const edit of config.overrides) {
        const resolution = await call<{
          resolution: { row: number }
          warnings: string[]
        }>('resolve', { id: edit.id })
        if (config.mappingPolicy === 'strict' && resolution.warnings.length)
          throw new Error(resolution.warnings.join('\n'))
        edits.push({ ...edit, id: resolution.resolution.row })
      }
      project.value = {
        ...project.value,
        config: { ...config, extends: 'base.yki', overrides: edits },
        outputName: config.output ?? project.value.outputName,
        manifest: null,
      }
      if (edits[0]) selected.value = idRow(edits[0].id)!
      notify(`${edits.length} 件の編集を読み込みました。基底は現在の YKI を使用します。`)
      jsonDraft.value = configJSON(project.value)
    } catch (cause) {
      fail(cause)
    } finally {
      busy.value = false
    }
  }
  const build = async () => {
    busy.value = true
    error.value = ''
    notify('音声の変換・YKI の生成中… 初回は音声エンジンも読み込みます。', true)
    try {
      if (!project.value.outputName.toLowerCase().endsWith('.yki'))
        throw new Error('出力ファイル名は .yki にしてください。')
      const result = await ensureBinary()
      project.value = { ...project.value, manifest: result.manifest }
      download(await result.file.arrayBuffer(), project.value.outputName)
      notify('YKI を生成しました。元のファイルは変更されません。')
      return true
    } catch (cause) {
      fail(cause)
      return false
    } finally {
      busy.value = false
    }
  }
  const ledPatch = (value: Led | undefined) => {
    if (value !== undefined) patch({ led: value })
    else {
      const edit = rowOverride(project.value, selected.value)
      delete edit.led
      project.value = {
        ...project.value,
        config: {
          ...project.value.config,
          overrides: project.value.config.overrides
            .filter((value) => idRow(value.id) !== selected.value)
            .concat(Object.keys(edit).length > 1 ? [edit] : []),
        },
        manifest: null,
      }
    }
  }

  const applyFrames = () => {
    try {
      ledPatch({
        frames: parseFrames(framesDraft.value),
        repeat: (rowOverride(project.value, selected.value).led as { repeat?: number }).repeat ?? 1,
      })
      error.value = ''
      notify('LED フレームを反映しました。')
    } catch (cause) {
      fail(cause)
    }
  }
  return {
    project,
    selected,
    query,
    showEmpty,
    tab,
    busy,
    status,
    notify,
    error,
    jsonDraft,
    framesDraft,
    preview,
    binaryFile,
    binaryInspection,
    binaryUpdating,
    binaryError,
    focusHeader,
    focusLED,
    binaryAreas,
    setVersion,
    focusVersion,
    binaryFocus,
    detail,
    focusMedal,
    focusResource,
    focusSound,
    fail,
    patch,
    selectedType,
    setSound,
    addSound,
    loadBase,
    previewSound,
    applyJSON,
    build,
    ledPatch,
    applyFrames,
  }
}
