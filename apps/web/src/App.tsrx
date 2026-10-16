import type {
  Config,
  Led,
  Override,
  Sound,
  SoundField,
  Manifest,
} from '@nakasyou/yki-core'
import type { Inspection, Project } from './types'
import { HexViewer } from './HexViewer.tsrx'
import { SoundControl } from './SoundControl.tsrx'
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

import { createEditor } from './editor-state'

export function App() @{
  const {
    project,
    selected,
    query,
    showEmpty,
    tab,
    busy,
    status,
    notify,
    error,
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
  } = createEditor()

  <div class="min-h-screen bg-canvas">
    <main class="mx-auto max-w-[1900px] px-5 py-7 sm:px-8">
      <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
        <h1 class="mono text-sm font-semibold">yki-editor (experimental)</h1>
        @if (project.value.inspection) {
          <div class="flex flex-wrap gap-2">
            <label class="btn cursor-pointer">
              <span>Import</span>
              <input
                class="sr-only"
                type="file"
                accept=".yki"
                disabled={busy.value}
                aria-label="Import YKI"
                onChange={(event: Event) => {
                  const input = event.target as HTMLInputElement
                  const file = input.files?.[0]
                  if (file) void loadBase(file)
                  input.value = ''
                }}
              />
            </label>
            <button
              class="btn btn-primary"
              disabled={busy.value || !project.value.inspection}
              onClick={() => {
                error.value = ''
                const dialog = document.getElementById(
                  'export-dialog',
                ) as HTMLDialogElement
                dialog.showModal()
              }}
            >Export</button>
            <label class="btn cursor-pointer">
              <span>Load configuration</span>
              <input
                class="sr-only"
                type="file"
                accept=".json"
                disabled={busy.value || !project.value.inspection}
                aria-label="Load JSON configuration"
                onChange={async (event: Event) => {
                  const input = event.target as HTMLInputElement
                  const file = input.files?.[0]
                  if (file) {
                    const contents = await file.text()
                    await applyJSON(contents)
                  }

                  input.value = ''
                }}
              />
            </label>
          </div>
        }
      </div>
      @if (!project.value.inspection) {
        <section
          class="flex min-h-[calc(100dvh-140px)] items-center justify-center"
          aria-label="YKI loading"
        >
          <div class="text-center">
            <h2 class="mb-3 text-lg font-semibold">Load a YKI file</h2>
            <p class="mb-6 text-xs text-[#8a927e]">Ver.2 – Ver.7 / .yki</p>
            <label class="btn btn-primary cursor-pointer">
              {busy.value ? 'Loading…' : 'Choose a YKI file'}
              <input
                class="sr-only"
                type="file"
                accept=".yki"
                aria-label="Import YKI"
                disabled={busy.value}
                onChange={(event: Event) => {
                  const input = event.target as HTMLInputElement
                  const file = input.files?.[0]
                  if (file) void loadBase(file)
                  input.value = ''
                }}
              />
            </label>
          </div>
        </section>
      } @else {
        <div
          class="grid items-start gap-5 lg:grid-cols-[minmax(0,0.9fr)_210px_minmax(0,1fr)] xl:grid-cols-[minmax(440px,0.9fr)_230px_minmax(0,1fr)]"
        >
          <HexViewer
            file={binaryFile}
            focus={binaryFocus}
            updating={binaryUpdating}
            error={binaryError}
            regions={binaryAreas}
          />
          <aside class="panel overflow-hidden" aria-label="Menu">
            <div class="border-b border-[#e9ebdf] p-4">
              <div class="mb-4 flex items-center justify-between">
                <h3 class="text-xs font-bold">Project</h3>
              </div>
              <button
                class={`mb-3 w-full rounded-lg px-3 py-3 text-left text-xs font-semibold ${
                  detail.value === 'header' ? 'bg-acid/45' : 'bg-[#f3f5ed]'
                }`}
                disabled={busy.value || !project.value.inspection}
                aria-pressed={detail.value === 'header'}
                onClick={() => focusHeader()}
              >Header</button>
              <div class="rounded-lg bg-[#f3f5ed] p-3">
                <p
                  class="truncate text-xs font-semibold"
                  title={project.value.baseName}
                >
                  {project.value.baseName || 'Choose the original YKI'}
                </p>
                <p class="mono mt-1 text-[10px] text-[#8a927e]">
                  {project.value.inspection
                    ? `Ver.${project.value.inspection.summary.version} · ${(project.value.inspection.summary.size /
                        1024 /
                        1024).toFixed(2)} MB`
                    : 'Ver.2 – Ver.7 / .yki'}
                </p>
              </div>
            </div>
            <div class="p-4">
              <div class="mb-3 flex justify-between">
                <h3 class="text-xs font-bold">Medals</h3>
                <span class="mono text-[10px] text-[#8b947e]">
                  {project.value.inspection ? '988 ROWS' : '—'}
                </span>
              </div>
              <input
                class="field"
                type="search"
                placeholder="Search by B number…"
                aria-label="Search medals"
                value={query.value}
                onInput={(event: Event) => (query.value =
                  (event.target as HTMLInputElement).value)}
              />
              <label
                class="mt-3 flex items-center gap-2 text-[11px] text-[#7e8672]"
              >
                <input
                  type="checkbox"
                  checked={showEmpty.value}
                  onChange={(event: Event) => (showEmpty.value =
                    (event.target as HTMLInputElement).checked)}
                />
                Show unregistered medals
              </label>
            </div>
            <div
              class="max-h-[480px] overflow-y-auto border-t border-[#eceee5] p-2"
            >
              @if (project.value.inspection) {
                @for (const medal of project.value.inspection.rows.filter(
                  (row) =>
                    (showEmpty.value || row.active) &&
                      `B${row.id}`.toLowerCase().includes(
                        query.value.toLowerCase(),
                      ),
                )) {
                  <button
                    class={`mb-1 flex w-full items-center justify-between rounded-lg px-3 py-3 text-left ${
                      detail.value === 'medal' && selected.value === medal.id
                        ? 'bg-acid/45'
                        : 'hover:bg-[#f3f5ed]'
                    }`}
                    disabled={busy.value}
                    onClick={() => {
                      selected.value = medal.id
                      error.value = ''
                      focusMedal(medal.id)
                    }}
                    aria-pressed={detail.value === 'medal' &&
                      selected.value === medal.id}
                  >
                    <div>
                      <span class="mono text-xs font-bold">{`B${String(
                        medal.id,
                      ).padStart(3, '0')}`}</span>
                      <span class="ml-2 text-[10px] text-[#89917d]">
                        {medal.active
                          ? medal.type === 'song'
                            ? 'Song'
                            : 'Normal'
                          : 'Unregistered'}
                      </span>
                    </div>
                    <span
                      class="h-1.5 w-1.5 rounded-full bg-[#6f883e]"
                      hidden={!project.value.config.overrides.some(
                        (edit) => idRow(edit.id) === medal.id,
                      )}
                    ></span>
                  </button>
                }
              } @else {
                <p class="px-3 py-8 text-center text-xs text-[#949c88]">
                  Open a YKI file to view this.
                </p>
              }
            </div>
          </aside>
          <section class="panel min-w-0 overflow-hidden" aria-label="Details">
            @if (detail.value === 'header') {
              <div class="p-5 sm:p-6">
                <h2 class="mb-5 text-lg font-bold">Header</h2>
                <dl
                  class="grid grid-cols-[auto_minmax(0,1fr)] gap-x-5 gap-y-4 text-xs"
                >
                  <dt>Filename</dt>
                  <dd class="break-all">{project.value.baseName}</dd>
                  <dt>Magic</dt>
                  <dd class="mono break-all">
                    BandaiYokai3rd******************
                  </dd>
                  <dt>Version</dt>
                  <dd>
                    <select
                      class="field"
                      aria-label="Version"
                      disabled={busy.value}
                      onFocus={() => focusVersion()}
                      value={project.value.config.version === undefined
                        ? 'inherit'
                        : String(project.value.config.version)}
                      onChange={(event: Event) => void setVersion(
                        (event.target as HTMLSelectElement).value,
                      )}
                    >
                      <option
                        value="inherit"
                      >{`Inherit the original version (Ver.${project.value.inspection.summary.version})`}</option>
                      @for (const version of [
                        0,
                        1,
                        2,
                        3,
                        4,
                        5,
                        6,
                        7,
                        8,
                        9,
                        10,
                      ]) {
                        <option
                          value={String(version)}
                        >{`Ver.${version}`}</option>
                      }
                    </select>
                  </dd>
                  <dt>File size</dt>
                  <dd>{`${binaryInspection.value!.summary.size.toLocaleString()} bytes`}</dd>
                  <dt>Resource count</dt>
                  <dd>{binaryInspection.value!.resources.length}</dd>
                  <dt>Registered medals</dt>
                  <dd>{binaryInspection.value!.rows.filter(
                    (row) => row.active,
                  ).length}</dd>
                  <dt>SHA-256</dt>
                  <dd
                    class="mono break-all"
                  >{binaryInspection.value!.summary.sha256}</dd>
                </dl>
              </div>
            } @else {
              <>
                <div
                  class="border-b border-[#e7eadf] p-5 sm:p-6"
                  onFocusIn={() => focusMedal()}
                  onClick={() => focusMedal()}
                >
                  <div class="flex items-center justify-between">
                    <div>
                      <h3 class="mono text-2xl font-bold">{`B${String(
                        selected.value,
                      ).padStart(3, '0')}`}</h3>
                    </div>
                    <button
                      class="btn text-[11px]"
                      disabled={busy.value}
                      onClick={() => {
                        project.value = resetRow(project.value, selected.value)
                        notify('Edits to this medal have been reset.')
                      }}
                    >
                      Reset edits
                    </button>
                  </div>
                  <div class="mt-5 grid grid-cols-2 gap-3">
                    <label>
                      <span class="label">Medal type</span>
                      <select
                        class="field"
                        value={selectedType()}
                        disabled={busy.value}
                        onChange={(event: Event) => patch({
                          type: (event.target as HTMLSelectElement).value as 'normal' | 'song',
                        })}
                      >
                        <option value="normal">Normal</option>
                        <option value="song">Song medal</option>
                      </select>
                    </label>
                    <label>
                      <span class="label">Template (optional)</span>
                      <input
                        class="field mono"
                        type="number"
                        min="1"
                        max="988"
                        placeholder="Inherit the original medal"
                        disabled={busy.value}
                        value={rowOverride(
                          project.value,
                          selected.value,
                        ).template ??
                          ''}
                        onChange={(event: Event) => {
                          const value = (event.target as HTMLInputElement).value
                          if (value) patch({ template: Number(value) })
                          else {
                            const edit = rowOverride(
                              project.value,
                              selected.value,
                            )
                            delete edit.template
                            project.value = {
                              ...project.value,
                              config: {
                                ...project.value.config,
                                overrides: project.value.config.overrides.filter(
                                  (value) => idRow(value.id) !== selected.value,
                                ).concat(edit),
                              },
                              manifest: null,
                            }
                          }
                        }}
                      />
                    </label>
                  </div>
                  @if (
                    !project.value.inspection.rows[selected.value - 1].active
                  ) {
                    <p
                      class="mt-3 rounded-lg bg-[#fff8dc] p-3 text-[11px] text-[#8b7131]"
                    >
                      New medals require a type and primary sound. Verify peg
                      pattern recognition on the device separately.
                    </p>
                  }
                </div>
                <div
                  class="flex gap-6 border-b border-[#e7eadf] px-5"
                  role="tablist"
                  aria-label="Editing category"
                >
                  @for (const item of [
                    { id: 'sound', label: 'Audio' },
                    { id: 'led', label: 'LED pattern' },
                  ]) {
                    <button
                      class={`border-b-2 py-4 text-xs font-semibold ${
                        tab.value === item.id
                          ? 'border-[#91a855] text-ink'
                          : 'border-transparent text-[#949b89]'
                      }`}
                      role="tab"
                      aria-selected={tab.value === item.id}
                      disabled={busy.value}
                      onClick={() => {
                        tab.value = item.id
                        if (item.id === 'led') focusLED()
                        else focusMedal()
                      }}
                    >{item.label}</button>
                  }
                </div>
                <div class="p-5 sm:p-6" role="tabpanel">
                  @if (tab.value === 'sound') {
                    <div>
                      <div class="mb-4 flex items-center justify-between">
                        <p class="text-[11px] text-[#808a73]">
                          Unchanged sounds retain their original settings.
                        </p>
                        <span
                          class="mono hidden text-[9px] text-[#939d86] sm:block"
                        >
                          16 kHz / MONO
                        </span>
                      </div>
                      <div class="grid gap-3 2xl:grid-cols-2">
                        @for (const field of soundFields.filter(
                          (field) => selectedType() === 'song'
                            ? !['summonSound', 'nameSound'].includes(field.key)
                            : field.key !== 'songSound',
                        )) {
                          <SoundControl
                            project={project}
                            row={selected}
                            field={field.key}
                            label={field.label}
                            disabled={busy}
                            onFocus={() => focusSound(field.key)}
                            onChange={(sound: Sound | undefined) => setSound(
                              field.key,
                              sound,
                            )}
                            onFile={(file: File) => addSound(field.key, file)}
                            onPreview={async (key: SoundField) => {
                              preview.value = ''
                              await previewSound(key)
                              if (preview.value) {
                                (document.getElementById(
                                  'sound-preview-dialog',
                                ) as HTMLDialogElement).showModal()
                              }
                            }}
                          />
                        }
                      </div>
                      <div class="mt-6 border-t border-[#e5e9dc] pt-5">
                        <h4 class="mb-4 text-xs font-bold">
                          Audio conversion settings
                        </h4>
                        <div class="grid grid-cols-2 gap-3">
                          <label>
                            <span class="label">Volume</span>
                            <select
                              class="field"
                              disabled={busy.value}
                              value={project.value.config.audio?.volume ??
                                'preserve'}
                              onChange={(event: Event) => {
                                project.value = {
                                  ...project.value,
                                  config: {
                                    ...project.value.config,
                                    audio: {
                                      ...project.value.config.audio,
                                      volume: (event.target as HTMLSelectElement).value as 'preserve' | 'peak' | 'match',
                                    },
                                  },
                                  manifest: null,
                                }
                              }}
                            >
                              <option value="preserve">
                                Preserve original volume
                              </option>
                              <option value="peak">Match peak level</option>
                              <option value="match">Match LUFS</option>
                            </select>
                          </label>
                          <label>
                            <span class="label">20 ms frame alignment</span>
                            <select
                              class="field"
                              disabled={busy.value}
                              value={project.value.config.audio?.frameAlignment ??
                                'trim'}
                              onChange={(event: Event) => {
                                project.value = {
                                  ...project.value,
                                  config: {
                                    ...project.value.config,
                                    audio: {
                                      ...project.value.config.audio,
                                      frameAlignment: (event.target as HTMLSelectElement).value as 'trim' | 'pad' | 'error',
                                    },
                                  },
                                  manifest: null,
                                }
                              }}
                            >
                              <option value="trim">Trim the end</option>
                              <option value="pad">Pad with silence</option>
                              <option value="error">
                                Reject misaligned audio
                              </option>
                            </select>
                          </label>
                        </div>
                        <label
                          class="mt-3 flex items-center gap-2 text-[11px] text-[#7d856e]"
                        >
                          <input
                            type="checkbox"
                            disabled={busy.value}
                            checked={project.value.config.audio?.allowClipping ??
                              false}
                            onChange={(event: Event) => {
                              project.value = {
                                ...project.value,
                                config: {
                                  ...project.value.config,
                                  audio: {
                                    ...project.value.config.audio,
                                    allowClipping: (event.target as HTMLInputElement).checked,
                                  },
                                },
                                manifest: null,
                              }
                            }}
                          />
                          Allow clipping during volume adjustment
                        </label>
                      </div>
                    </div>
                  }
                  @if (tab.value === 'led') {
                    <div
                      onFocusIn={() => focusLED()}
                      onClick={() => focusLED()}
                    >
                      <div
                        class="mb-5 flex h-28 items-center justify-center gap-5 rounded-xl bg-[#292f24]"
                      >
                        <span
                          class="h-9 w-9 rounded-full bg-[#ee6b63] shadow-[0_0_25px_#ee6b6377]"
                        ></span>
                        <span
                          class="h-9 w-9 rounded-full bg-[#a5ce63] shadow-[0_0_25px_#a5ce6377]"
                        ></span>
                        <span
                          class="h-9 w-9 rounded-full bg-[#79a8e3] shadow-[0_0_25px_#79a8e377]"
                        ></span>
                      </div>
                      <label>
                        <span class="label">LED settings</span>
                        <select
                          class="field"
                          disabled={busy.value}
                          value={ledMode(
                            rowOverride(project.value, selected.value).led,
                          )}
                          onChange={(event: Event) => {
                            const mode = (event.target as HTMLSelectElement).value
                            ledPatch(
                              mode === 'inherit'
                                ? undefined
                                : mode === 'none'
                                  ? null
                                  : mode === 'resource'
                                    ? {
                                        resource: ledResource(
                                          project.value.inspection!.rows[selected.value -
                                            1],
                                          project.value.inspection!.resources,
                                        ) ??
                                          project.value.inspection!.resources.find(
                                            (r) => r.kind === 'led',
                                          )!.id,
                                        repeat: 1,
                                      }
                                    : mode === 'file'
                                      ? ''
                                      : {
                                          frames: [
                                            [255, 0, 0],
                                            [0, 255, 0],
                                            [0, 0, 255],
                                          ],
                                          repeat: 1,
                                        },
                            )
                          }}
                        >
                          <option value="inherit">
                            Inherit the original pattern
                          </option>
                          <option value="resource">
                            Repeat an existing pattern
                          </option>
                          <option value="frames">Create RGB frames</option>
                          <option value="file">LED JSON file</option>
                          <option value="none">Clear / black frame</option>
                        </select>
                      </label>
                      @if (
                        ledMode(
                          rowOverride(project.value, selected.value).led,
                        ) ===
                          'resource'
                      ) {
                        <>
                          <div class="mt-4 grid grid-cols-2 gap-3">
                            <label>
                              <span class="label">LED resource</span>
                              <select
                                class="field mono"
                                disabled={busy.value}
                                value={(rowOverride(
                                  project.value,
                                  selected.value,
                                ).led as { resource: number }).resource}
                                onChange={(event: Event) => ledPatch({
                                  ...rowOverride(
                                    project.value,
                                    selected.value,
                                  ).led as {
                                    resource: number;
                                    repeat?: number;
                                  },
                                  resource: Number(
                                    (event.target as HTMLSelectElement).value,
                                  ),
                                })}
                              >
                                @for (const resource of project.value.inspection.resources.filter(
                                  (r) => r.kind === 'led',
                                )) {
                                  <option
                                    value={resource.id}
                                  >{`#${resource.id} · ${resource.frames} frames`}</option>
                                }
                              </select>
                            </label>
                            <label>
                              <span class="label">Repeat count</span>
                              <input
                                class="field mono"
                                type="number"
                                min="1"
                                max="1024"
                                disabled={busy.value}
                                value={(rowOverride(
                                  project.value,
                                  selected.value,
                                ).led as { repeat?: number }).repeat ??
                                  1}
                                onChange={(event: Event) => ledPatch({
                                  ...rowOverride(
                                    project.value,
                                    selected.value,
                                  ).led as { resource: number },
                                  repeat: Number(
                                    (event.target as HTMLInputElement).value,
                                  ),
                                })}
                              />
                            </label>
                          </div>
                        </>
                      }
                      @if (
                        ledMode(
                          rowOverride(project.value, selected.value).led,
                        ) ===
                          'frames'
                      ) {
                        <>
                          <label class="mt-4 block">
                            <span class="label">
                              RGB frames / [[r, g, b], …]
                            </span>
                            <textarea
                              class="field mono min-h-36 resize-y"
                              disabled={busy.value}
                              value={framesDraft.value}
                              onInput={(event: Event) => (framesDraft.value =
                                (event.target as HTMLTextAreaElement).value)}
                            />
                          </label>
                          <div class="mt-3 flex gap-2">
                            <button
                              class="btn"
                              disabled={busy.value}
                              onClick={applyFrames}
                            >
                              Apply frames
                            </button>
                            <label
                              class="flex items-center gap-2 text-[11px] text-[#7d856e]"
                            >
                              Repeat
                              <input
                                class="field mono w-20"
                                type="number"
                                min="1"
                                max="1024"
                                disabled={busy.value}
                                value={(rowOverride(
                                  project.value,
                                  selected.value,
                                ).led as { repeat?: number }).repeat ??
                                  1}
                                onChange={(event: Event) => ledPatch({
                                  ...rowOverride(
                                    project.value,
                                    selected.value,
                                  ).led as {
                                    frames: [number, number, number][];
                                  },
                                  repeat: Number(
                                    (event.target as HTMLInputElement).value,
                                  ),
                                })}
                              />
                            </label>
                          </div>
                        </>
                      }
                      @if (
                        ledMode(
                          rowOverride(project.value, selected.value).led,
                        ) ===
                          'file'
                      ) {
                        <input
                          type="file"
                          class="field mt-4"
                          accept=".json"
                          disabled={busy.value}
                          aria-label="LED JSON file"
                          onChange={(event: Event) => {
                            const file = (event.target as HTMLInputElement).files?.[0]
                            if (file) {
                              const name = `led/B${selected.value}-${file.name}`
                              project.value = {
                                ...project.value,
                                files: { ...project.value.files, [name]: file },
                              }
                              ledPatch(name)
                            }
                          }}
                        />
                      }
                      <p
                        class="mt-6 rounded-lg bg-[#f2f5ec] p-3 text-[11px] leading-5 text-[#808c70]"
                      >
                        Each channel ranges from 0 to 255. The physical RGB
                        order and timing are unverified, so there is no fps
                        setting. Repeats are limited to 1,024 and one million
                        total frames.
                      </p>
                    </div>
                  }
                </div>
              </>
            }
          </section>
        </div>
      }
      @if (project.value.manifest?.warnings.length) {
        <section class="rounded-xl border border-[#e6d7a5] bg-[#fff9e8] p-4">
          <h4 class="mb-2 text-xs font-semibold">Build warnings</h4>
          @for (const warning of project.value.manifest.warnings) {
            <p
              class="mb-2 break-words text-[10px] leading-5 text-[#8a7746]"
            >{warning}</p>
          }
        </section>
      }

      <dialog
        id="sound-preview-dialog"
        class="m-auto w-[calc(100%-2.5rem)] max-w-md rounded-xl border border-[#e6e8de] bg-white p-5 shadow-xl backdrop:bg-black/40"
        aria-labelledby="sound-preview-title"
        onClick={(event: MouseEvent) => {
          const dialog = event.currentTarget as HTMLDialogElement
          if (event.target !== dialog) return
          const bounds = dialog.getBoundingClientRect()
          if (
            event.clientX < bounds.left || event.clientX > bounds.right ||
              event.clientY < bounds.top ||
              event.clientY > bounds.bottom
          ) dialog.close()
        }}
        onClose={() => {
          (document.getElementById(
            'sound-preview-player',
          ) as HTMLAudioElement | null)?.pause()
        }}
      >
        <div class="mb-4 flex items-center justify-between gap-4">
          <h2 id="sound-preview-title" class="text-sm font-semibold">
            Original sound preview
          </h2>
          <form method="dialog">
            <button class="btn" aria-label="Close sound preview">
              Close
            </button>
          </form>
        </div>
        @if (preview.value) {
          <audio
            id="sound-preview-player"
            controls
            src={preview.value}
            class="h-9 w-full"
          />
        }
      </dialog>
      <dialog
        id="export-dialog"
        aria-labelledby="export-title"
        onCancel={(event: Event) => {
          if (busy.value) event.preventDefault()
        }}
      >
        <div class="p-5">
          <h2 id="export-title" class="mb-5 text-sm font-bold">Export</h2>
          <label class="block">
            <span class="label">Output filename</span>
            <input
              class="field mono"
              value={project.value.outputName}
              disabled={busy.value}
              onInput={(event: Event) => {
                project.value = {
                  ...project.value,
                  outputName: (event.target as HTMLInputElement).value,
                }
              }}
            />
          </label>
          <label class="mt-4 block">
            <span class="label">Spoken version</span>
            <select
              class="field"
              disabled={busy.value || !project.value.inspection}
              value={project.value.config.version === undefined
                ? 'inherit'
                : String(project.value.config.version)}
              onChange={(event: Event) => void setVersion(
                (event.target as HTMLSelectElement).value,
              )}
            >
              <option value="inherit">Inherit the original version</option>
              @for (const version of [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) {
                <option value={String(version)}>{`Ver.${version}`}</option>
              }
            </select>
          </label>
          <div
            class="my-5 grid grid-cols-2 gap-3 border-y border-[#e9ecdf] py-4"
          >
            <div>
              <p class="text-[10px] text-[#869078]">Edited medals</p>
              <p
                class="mono mt-1 text-xl font-bold"
              >{new Set(project.value.config.overrides.map(
                (edit) => idRow(edit.id),
              )).size}</p>
            </div>
            <div>
              <p class="text-[10px] text-[#869078]">Additional files</p>
              <p class="mono mt-1 text-xl font-bold">{Object.keys(
                project.value.files,
              ).length}</p>
            </div>
          </div>
          @if (error.value || busy.value) {
            <p class="my-4 break-words text-xs" aria-live="polite">
              {error.value || status.value}
            </p>
          }
          <button
            class="btn btn-primary w-full py-3"
            disabled={busy.value || !project.value.inspection}
            onClick={async () => {
              const dialog = document.getElementById(
                'export-dialog',
              ) as HTMLDialogElement
              const success = await build()
              if (success) dialog.close()
            }}
          >
            {busy.value ? 'Processing…' : 'Export YKI'}
          </button>
          <button
            class="btn mt-2 w-full"
            disabled={busy.value || !project.value.inspection}
            onClick={() => download(
              configJSON(project.value),
              project.value.outputName.replace(/\.yki$/i, '.json'),
              'application/json',
            )}
          >
            Save JSON configuration
          </button>
          @if (project.value.manifest) {
            <button
              class="btn mt-2 w-full"
              onClick={() => download(
                JSON.stringify(project.value.manifest, null, 2),
                project.value.outputName.replace(/\.yki$/i, '.manifest.json'),
                'application/json',
              )}
            >
              Save manifest
            </button>
          }

          <button
            class="btn mt-2 w-full"
            disabled={busy.value}
            onClick={() => {
              const dialog = document.getElementById(
                'export-dialog',
              ) as HTMLDialogElement
              dialog.close()
            }}
          >Cancel</button>
        </div>
      </dialog>
      @if (error.value || status.value) {
        <div
          class={`fixed bottom-5 right-5 z-50 flex w-[calc(100%-2.5rem)] max-w-md items-start gap-3 rounded-lg border px-4 py-3 text-xs shadow-lg ${
            error.value
              ? 'border-[#e6c6bb] bg-[#fff1ed] text-[#ab5c44]'
              : 'border-[#e0e4d5] bg-white text-[#788568]'
          }`}
          role={error.value ? 'alert' : 'status'}
          aria-live="polite"
        >
          <span>
            {error.value
              ? '!'
              : busy.value
                ? '◌'
                : '●'}
          </span>
          <p class="min-w-0 break-words leading-5">
            {error.value || status.value}
          </p>
          <button
            class="ml-auto shrink-0 px-1 text-base leading-5"
            aria-label="Dismiss notification"
            onClick={() => {
              error.value = ''
              notify('')
            }}
          >×</button>
        </div>
      }
    </main>
  </div>
}
