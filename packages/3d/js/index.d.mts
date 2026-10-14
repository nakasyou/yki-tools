export type Json = null | boolean | number | string | Json[] | { [key: string]: Json }
export interface MedalOptions {
  mode?: 'normal' | 'classic' | 'lite'
  orientation?: 'canonical' | 'physical'
  mirror?: boolean
}
export interface GeneratedMedal {
  source: string
  rows: [string, string, string, string]
  mode: 'normal' | 'classic' | 'lite'
  filename: string
}
export interface ThreeD {
  request(value: Json): Json
  generateMedal(bits: string, options?: MedalOptions): GeneratedMedal
}
export function create3D(wasm: BufferSource | WebAssembly.Module): Promise<ThreeD>
