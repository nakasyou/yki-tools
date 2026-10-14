import type { Project } from './types'
import type { Sound, SoundField } from '@nakasyou/yki-core'
import { audioPair, inheritedLabel, rowOverride, soundMode } from './model'

type Props = {
  project: { value: Project };
  row: { value: number };
  field: SoundField;
  label: string;
  disabled: { value: boolean };
  onChange: (sound: Sound | undefined) => void;
  onFile: (file: File) => void;
  onPreview: (field: SoundField) => void;
  onFocus: () => void;
}
export function SoundControl(props: Props) @{
  const canPreview = () => {
    const inspection = props.project.value.inspection
    if (!inspection) return false
    const pair = audioPair(
      inspection.rows[props.row.value - 1],
      inspection.resources,
      props.field,
    )
    return pair !== null && pair[0] === 1 &&
      inspection.resources[pair[1]]?.kind === 'audio'
  }

  <section
    class="rounded-xl border border-[#e6e8de] p-4"
    onFocusIn={() => props.onFocus()}
    onClick={() => props.onFocus()}
  >
    <div class="mb-3 flex items-center justify-between">
      <h3 class="text-sm font-semibold">{props.label}</h3>
      <button
        class="text-[11px] text-[#707763] hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
        disabled={props.disabled.value || !canPreview()}
        onClick={() => props.onPreview(props.field)}
        aria-label={`${props.label} inherited sound preview`}
      >
        {canPreview() ? '▷ Original sound' : 'original sound is empty'}
      </button>
    </div>
    <select
      class="field"
      value={soundMode(
        rowOverride(props.project.value, props.row.value)[props.field],
      )}
      disabled={props.disabled.value}
      onChange={(event: Event) => {
        const mode = (event.target as HTMLSelectElement).value
        props.onChange(
          mode === 'inherit'
            ? undefined
            : mode === 'none'
              ? null
              : mode === 'builtin'
                ? { builtin: 107 }
                : mode === 'resource'
                  ? {
                      resource: props.project.value.inspection!.resources.find(
                        (r) => r.kind === 'audio',
                      )!.id,
                    }
                  : '',
        )
      }}
      aria-label={`${props.label} source`}
    >
      <option value="inherit">Inherit original settings</option>
      <option value="file">Audio file</option>
      <option value="builtin">Built-in sound</option>
      <option value="resource">Existing audio resource</option>
      <option value="none">None / clear</option>
    </select>
    @if (
      soundMode(
        rowOverride(props.project.value, props.row.value)[props.field],
      ) ===
        'file'
    ) {
      <div class="mt-3">
        <input
          type="file"
          accept="audio/*"
          class="block w-full text-xs file:mr-3 file:rounded-md file:border-0 file:bg-[#eef3e5] file:px-3 file:py-2"
          disabled={props.disabled.value}
          aria-label={`${props.label} audio file`}
          onChange={(event: Event) => {
            const file = (event.target as HTMLInputElement).files?.[0]
            if (file) props.onFile(file)
          }}
        />
        <p class="mt-2 break-all text-[11px] text-[#6e7565]">
          {typeof rowOverride(
            props.project.value,
            props.row.value,
          )[props.field] ===
          'string'
            ? String(
              rowOverride(props.project.value, props.row.value)[props.field],
            ) ||
              'Choose a file'
            : 'Use an audio file'}
        </p>
      </div>
    }
    @if (
      soundMode(
        rowOverride(props.project.value, props.row.value)[props.field],
      ) ===
        'builtin'
    ) {
      <label class="mt-3 block">
        <span class="label">Built-in sound ID</span>
        <input
          class="field mono"
          type="number"
          min="0"
          max="65533"
          disabled={props.disabled.value}
          value={(rowOverride(
            props.project.value,
            props.row.value,
          )[props.field] as {
            builtin: number;
          }).builtin}
          onInput={(event: Event) => props.onChange({
            builtin: Number((event.target as HTMLInputElement).value),
          })}
        />
      </label>
    }
    @if (
      soundMode(
        rowOverride(props.project.value, props.row.value)[props.field],
      ) ===
        'resource'
    ) {
      <label class="mt-3 block">
        <span class="label">Audio resource</span>
        <select
          class="field mono"
          disabled={props.disabled.value}
          value={(rowOverride(
            props.project.value,
            props.row.value,
          )[props.field] as {
            resource: number;
          }).resource}
          onChange={(event: Event) => props.onChange({
            resource: Number((event.target as HTMLSelectElement).value),
          })}
        >
          @for (const resource of props.project.value.inspection!.resources.filter(
            (r) => r.kind === 'audio',
          )) {
            <option
              value={resource.id}
            >{`#${resource.id} · ${resource.duration!.toFixed(2)} s`}</option>
          }
        </select>
      </label>
    }
    <p class="mt-3 text-[10px] text-[#858b7b]">{`Inherited: ${inheritedLabel(
      props.project.value.inspection!.rows[props.row.value - 1],
      props.project.value.inspection!.resources,
      props.field,
    )}`}</p>
  </section>
}
