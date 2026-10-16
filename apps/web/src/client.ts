const worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' })
let nextId = 0
const pending = new Map<
  number,
  { resolve: (value: unknown) => void; reject: (reason: Error) => void }
>()
worker.onmessage = ({ data }) => {
  const task = pending.get(data.id)
  if (!task) return
  pending.delete(data.id)
  if (data.error) task.reject(new Error(data.error))
  else task.resolve(data.result)
}
worker.onerror = () => {
  for (const task of pending.values())
    task.reject(new Error('Unable to start the editing engine. Reload the page.'))
  pending.clear()
}
export function call<T>(op: string, data: Record<string, unknown> = {}): Promise<T> {
  const id = nextId++
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve: (value) => resolve(value as T), reject })
    worker.postMessage({ id, op, data })
  })
}
