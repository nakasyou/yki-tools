import type { Config, Manifest } from '@nakasyou/yki-core'
export type Pair = [number, number]
export interface Medal {
  id: number
  type: 'normal' | 'song'
  active: boolean
  pairs: Pair[]
}
export interface Resource {
  id: number
  kind: 'root' | 'medal_table' | 'led' | 'sequence' | 'audio'
  bytes: number
  pairs: Pair[]
  frames?: number
  duration?: number
}
export interface Inspection {
  summary: { version: number; size: number; sha256: string; resources: Record<string, number> }
  rows: Medal[]
  resources: Resource[]
}
export interface Project {
  baseName: string
  inspection: Inspection | null
  config: Config
  files: Record<string, File>
  outputName: string
  manifest: Manifest | null
}
