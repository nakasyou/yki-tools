import type { Json } from '@nakasyou/yki-core'
export interface NodeHostOptions {
  baseDir?: string
  stockDir?: string
  ffmpeg?: string
}
export function createNodeHost(options?: NodeHostOptions): {
  host(request: Json): Json
  resolvePath(path: string): string
  close(): void
}
