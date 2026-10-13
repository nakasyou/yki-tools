import { effect, track, tick, untrack } from 'ripple'
import { binaryKinds, hexOffset, regionAt } from './binary'
import type { BinaryKind, BinaryRange, BinaryRegion } from './binary'

type Props = {
  file: { value: File | null };
  focus: { value: BinaryRange };
  updating: { value: boolean };
  error: { value: string };
  regions: { value: BinaryRegion[] };
}
export function HexViewer(props: Props) @{
  const start = track(0)
  const bytes = track(new Uint8Array())
  const readError = track('')
  const jump = track('')
  const rowHeight = 24
  const visibleRows = 28
  const rows = () => Math.ceil((props.file.value?.size ?? 0) / 16)
  const height = () => Math.min(rows() * rowHeight, 1000000)
  const maxStart = () => Math.max(0, rows() - visibleRows)
  const top = () => maxStart()
    ? start.value / maxStart() * Math.max(0, height() - visibleRows * rowHeight)
    : 0
  let generation = 0
  const area = (offset: number) => regionAt(props.regions.value, offset)
  const byteClass = (offset: number) => {
    const kind = area(offset)?.kind
    const selected =
      offset >= props.focus.value.offset &&
        offset < props.focus.value.offset + props.focus.value.length
    return `hex-byte ${kind ? `hex-${kind}` : ''} ${
      selected ? 'hex-selected' : ''
    }`
  }
  const byteTitle = (offset: number) => {
    const region = area(offset)
    const label =
      region?.kind === 'medal_table'
        ? `メダル情報 · B${Math.floor((offset - region.offset) / 36) + 1}`
        : region?.label ?? '未分類'
    return `${label} · 0x${hexOffset(offset)}`
  }
  effect(() => {
    const file = props.file.value
    const offset = start.value * 16
    const current = ++generation
    bytes.value = new Uint8Array()
    readError.value = ''
    if (file) void file.slice(
      offset,
      offset + visibleRows * 16,
    ).arrayBuffer().then((buffer) => {
      if (current === generation) bytes.value = new Uint8Array(buffer)
    }).catch(() => {
      if (current === generation) readError.value =
        'バイナリを読み込めませんでした。'
    })
    return () => {
      generation++
    }
  })
  let moveRevision = 0
  let moving = false
  const move = async (offset: number) => {
    const revision = ++moveRevision
    moving = true
    const next = Math.min(maxStart(), Math.max(0, Math.floor(offset / 16)))
    start.value = next
    await tick()
    const viewport = document.getElementById('hex-viewport')
    if (viewport) viewport.scrollTop = untrack(top)
    requestAnimationFrame(() => {
      if (revision === moveRevision) moving = false
    })
  }
  effect(() => {
    const file = props.file.value
    const range = props.focus.value
    if (file) void untrack(() => move(range.offset))
  })
  <section class="panel min-w-0 overflow-hidden" aria-label="バイナリ">
    <div class="border-b border-[#e9ebdf] p-4">
      <h2 class="text-xs font-bold">
        バイナリ
        <span class="font-normal text-[#8a927e]">READ ONLY</span>
      </h2>
      <p
        class="mono mt-2 break-all text-[11px]"
      >{`${props.focus.value.label} · 0x${hexOffset(
        props.focus.value.offset,
      )}`}</p>
      @if (props.updating.value) {
        <p class="mt-2 text-xs text-[#8a927e]" role="status">
          編集内容を反映中…
        </p>
      }
      @if (props.error.value) {
        <p
          class="mt-2 text-xs text-[#ab5c44]"
          role="alert"
        >{`編集内容は未反映: ${props.error.value}`}</p>
      }
      <form
        class="mt-3 flex gap-2"
        onSubmit={(event: Event) => {
          event.preventDefault()
          const offset = Number.parseInt(jump.value.replace(/^0x/i, ''), 16)
          if (Number.isFinite(offset)) void move(offset)
        }}
      >
        <input
          class="field mono min-w-0"
          aria-label="16進オフセット"
          placeholder="00000000"
          value={jump.value}
          disabled={!props.file.value}
          onInput={(event: Event) => {
            jump.value = (event.target as HTMLInputElement).value
          }}
        />
        <button
          class="btn shrink-0 whitespace-nowrap"
          disabled={!props.file.value}
        >移動</button>
      </form>
      <div
        class="mt-3 flex flex-wrap gap-2 text-[10px]"
        aria-label="バイナリの色分け凡例"
      >
        @for (const kind of Object.keys(binaryKinds) as BinaryKind[]) {
          <span class={`hex-legend hex-${kind}`}>{binaryKinds[kind]}</span>
        }
        <span class="hex-legend hex-selected">選択範囲</span>
      </div>
    </div>
    @if (props.file.value) {
      <>
        <div class="overflow-x-auto">
          <div
            class="mono whitespace-pre border-b border-[#e9ebdf] px-3 py-2 text-[10px] text-[#8a927e]"
          >{'OFFSET    00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F'}</div>
          <div
            id="hex-viewport"
            class="relative overflow-y-auto"
            style="height: 672px; min-width: 440px"
            tabindex="0"
            aria-label="読み取り専用16進ビュー"
            onKeyDown={(event: KeyboardEvent) => {
              if (event.key === 'End' || event.key === 'Home') {
                event.preventDefault()
                void move(event.key === 'End' ? maxStart() * 16 : 0)
              }
            }}
            onScroll={(event: Event) => {
              const element = event.currentTarget as HTMLElement
              if (moving && Math.abs(element.scrollTop - top()) <= 1) return
              moving = false
              moveRevision++
              const available = Math.max(0, height() - visibleRows * rowHeight)
              const next =
                available
                  ? Math.round(element.scrollTop / available * maxStart())
                  : 0
              if (Math.abs(element.scrollTop - top()) > 1) start.value = next
            }}
          >
            <div style={`height: ${height()}px; position: relative`}>
              <div
                style={`position: absolute; top: ${top()}px; left: 0; right: 0`}
              >
                @for (const index of Array.from(
                  { length: Math.ceil(bytes.value.length / 16) },
                  (_, i) => i,
                )) {
                  <div
                    class="mono flex items-center px-3 text-[10px]"
                    style="height: 24px"
                  >
                    <span class="mr-3 text-[#8a927e]">{hexOffset(
                      (start.value + index) * 16,
                    )}</span>
                    @for (const column of Array.from(
                      { length: Math.min(16, bytes.value.length - index * 16) },
                      (_, i) => i,
                    )) {
                      <span
                        data-offset={(start.value + index) * 16 + column}
                        class={byteClass((start.value + index) * 16 + column)}
                        title={byteTitle((start.value + index) * 16 + column)}
                        data-kind={area(
                          (start.value + index) * 16 + column,
                        )?.kind}
                        style="display: inline-block; width: 24px; text-align: center"
                      >{bytes.value[index * 16 + column].toString(
                        16,
                      ).toUpperCase().padStart(2, '0')}</span>
                    }
                  </div>
                }
              </div>
            </div>
          </div>
        </div>
        @if (readError.value) {
          <p role="alert" class="p-3 text-xs">{readError.value}</p>
        }
        <p
          class="mono border-t border-[#e9ebdf] p-3 text-[10px] text-[#8a927e]"
        >{`${props.file.value.size.toLocaleString()} bytes · READ ONLY`}</p>
      </>
    } @else {
      <p class="p-6 text-xs text-[#8a927e]">YKI を開くと表示されます。</p>
    }
  </section>
}
