import type { DesktopJob, TermHit } from '../shared/api'

export function errorText(error: unknown) {
  return error instanceof Error
    ? error.message.replace(/^Error invoking remote method '[^']+': (?:Error: )?/, '')
    : '操作失败，请重试。'
}

export function timeLabel(ms: number, milliseconds = false) {
  const minutes = String(Math.floor(ms / 60000)).padStart(2, '0')
  const seconds = String(Math.floor(ms / 1000) % 60).padStart(2, '0')
  return `${minutes}:${seconds}${milliseconds ? '.' + String(ms % 1000).padStart(3, '0') : ''}`
}

export function activeJob(job: DesktopJob) {
  return job.state === 'queued' || job.state === 'running'
}

export function highlightedParts(text: string, hits: TermHit[]) {
  const letters = Array.from(text)
  let cursor = 0
  const parts: { text: string; hit?: TermHit }[] = []
  for (const hit of [...hits].sort((a, b) => a.start - b.start)) {
    const matched = letters.slice(hit.start, hit.end).join('')
    if (hit.start < cursor || hit.end > letters.length || matched !== hit.matched_text) continue
    parts.push({ text: letters.slice(cursor, hit.start).join('') }, { text: matched, hit })
    cursor = hit.end
  }
  parts.push({ text: letters.slice(cursor).join('') })
  return parts
}
