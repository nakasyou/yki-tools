import type { Resource } from './types'

export interface BinaryRange {
  offset: number
  length: number
  label: string
}
export const binaryKinds = {
  header: 'Header',
  pointers: 'Resource index',
  root: 'Basic information',
  version: 'Version',
  medal_table: 'Medal table',
  audio: 'Audio',
  led: 'LED',
  sequence: 'Playback sequence',
  padding: 'Padding',
} as const
export type BinaryKind = keyof typeof binaryKinds
export interface BinaryRegion extends BinaryRange {
  kind: BinaryKind
}
export function binaryRegions(
  offsets: number[],
  resources: Resource[],
  size: number,
): BinaryRegion[] {
  const regions: BinaryRegion[] = [
    { offset: 0, length: 512, kind: 'header', label: binaryKinds.header },
    { offset: 512, length: offsets.length * 4, kind: 'pointers', label: binaryKinds.pointers },
  ]
  for (const resource of resources) {
    const offset = offsets[resource.id]
    if (offset === undefined) continue
    const label = `${binaryKinds[resource.kind]} · #${resource.id}`
    if (resource.kind === 'root') {
      regions.push(
        { offset, length: 44, kind: 'root', label },
        { offset: offset + 44, length: 4, kind: 'version', label: binaryKinds.version },
        { offset: offset + 48, length: resource.bytes - 48, kind: 'root', label },
      )
    } else regions.push({ offset, length: resource.bytes, kind: resource.kind, label })
  }
  const end = Math.max(...regions.map((region) => region.offset + region.length))
  if (end < size)
    regions.push({ offset: end, length: size - end, kind: 'padding', label: binaryKinds.padding })
  return regions.sort((a, b) => a.offset - b.offset)
}
export function regionAt(regions: BinaryRegion[], offset: number): BinaryRegion | undefined {
  let low = 0
  let high = regions.length - 1
  while (low <= high) {
    const middle = (low + high) >>> 1
    const region = regions[middle]
    if (offset < region.offset) high = middle - 1
    else if (offset >= region.offset + region.length) low = middle + 1
    else return region
  }
}
export async function resourceOffsets(file: File): Promise<number[]> {
  const header = new DataView(await file.slice(0, 512).arrayBuffer())
  const count = header.getUint16(42, true)
  const base = header.getUint32(34, true)
  const pointers = new DataView(await file.slice(512, 512 + count * 4).arrayBuffer())
  return Array.from({ length: count }, (_, i) => (pointers.getUint32(i * 4, true) - base) * 2)
}
export function hexOffset(offset: number): string {
  return offset.toString(16).toUpperCase().padStart(8, '0')
}
