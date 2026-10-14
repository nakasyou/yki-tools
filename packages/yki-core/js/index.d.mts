export type Json = null | boolean | number | string | Json[] | { [key: string]: Json }
export type MedalId =
  | number
  | string
  | string[]
  | { medal: number }
  | { bumpsHex: string }
  | { bumps: string[] }
  | { sound: number; namespace?: 'builtin' | 'resource'; field?: SoundField; medal?: number }
export type SoundField =
  | 'summonSound'
  | 'tribeSound'
  | 'nameSound'
  | 'introSound'
  | 'postSound'
  | 'callSound'
  | 'songSound'
export interface AudioOptions {
  frameAlignment?: 'trim' | 'pad' | 'error'
  volume?: 'preserve' | 'peak' | 'match'
  allowClipping?: boolean
  referenceResource?: number
}
export type Sound =
  | null
  | string
  | { builtin: number }
  | { resource: number }
  | ({ file: string } & AudioOptions)
export type Led =
  | null
  | string
  | { resource: number; repeat?: number }
  | { frames: [number, number, number][]; repeat?: number }
export type Override = {
  id: MedalId
  type?: 'normal' | 'song'
  template?: number | string
  led?: Led
} & Partial<Record<SoundField, Sound>>
export interface Config {
  $schema?: string
  extends: number | string
  version?: number
  output?: string
  mappingPolicy?: 'warn' | 'strict'
  audio?: AudioOptions
  overrides: Override[]
}
export interface Manifest {
  source: string
  source_sha256: string
  output_sha256: string
  size: number
  version: number
  version_spoken_id: number
  resource_count: number
  handle_to_output_resource: Record<string, number>
  warnings: string[]
  audio: Json[]
  overrides: Json[]
  resolutions: Json[]
  hardware_tested: false
  [key: string]: Json
}
export interface G7221Codec {
  encode(pcm: Uint8Array): Uint8Array
  decode(payload: Uint8Array): Uint8Array
}
export function createG7221(wasm: BufferSource | WebAssembly.Module): Promise<G7221Codec>
export interface Core {
  encodeG7221(pcm: Uint8Array): Uint8Array
  decodeG7221(payload: Uint8Array): Uint8Array
  request(value: Json): Json
  schema(): Json
  validateConfig(config: Config): { schema_valid: true }
  inspect(data: Uint8Array): {
    size: number
    sha256: string
    version: number
    resources: Record<string, number>
    [key: string]: Json
  }
  roundtrip(data: Uint8Array): Uint8Array
  resolve(
    data: Uint8Array,
    id: MedalId,
    strict?: boolean,
  ): { resolution: { row: number; confidence: string; [key: string]: Json }; warnings: string[] }
  validate(config: Config, strict?: boolean): Json
  build(config: Config, strict?: boolean): { data: Uint8Array; manifest: Manifest }
  decode(blob: Uint8Array): Uint8Array
}
export function createCore(
  wasm: BufferSource | WebAssembly.Module,
  options?: { host?: (request: Json) => Json },
): Promise<Core>
export function toHex(bytes: Uint8Array): string
export function fromHex(text: string): Uint8Array
