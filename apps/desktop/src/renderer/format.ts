import type { DesktopJob, MediaCheck, TermHit } from '../shared/api'

export function errorText(error: unknown) {
  return error instanceof Error
    ? error.message.replace(/^Error invoking remote method '[^']+': (?:Error: )?/, '')
    : '操作失败，请重试。'
}

export function byteLabel(bytes: number) {
  if (!Number.isFinite(bytes) || bytes < 0) return '—'
  if (bytes < 1024) return `${Math.round(bytes)} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(bytes < 10240 ? 1 : 0)} KB`
  const megabytes = bytes / (1024 * 1024)
  return `${megabytes.toFixed(megabytes < 10 ? 1 : 0)} MB`
}

export function sampleLabel(file: Pick<MediaCheck, 'name' | 'sampleRate' | 'channels' | 'bitDepth'>) {
  if (file.sampleRate) {
    const rate = file.sampleRate % 1000 === 0
      ? `${file.sampleRate / 1000} kHz`
      : file.sampleRate >= 1000 ? `${(file.sampleRate / 1000).toFixed(1)} kHz` : `${file.sampleRate} Hz`
    const channels = file.channels === 1 ? '单声道' : file.channels === 2 ? '立体声' : file.channels ? `${file.channels} 声道` : ''
    const depth = file.bitDepth ? `${file.bitDepth} bit` : ''
    return [rate, channels, depth].filter(Boolean).join(' · ')
  }
  const extension = file.name.split('.').pop()?.toLowerCase()
  const containers: Record<string, string> = { mp3: 'MP3', m4a: 'M4A', mp4: 'MP4', mkv: 'MKV', webm: 'WebM', wav: 'WAV', flac: 'FLAC' }
  return (extension && containers[extension]) || '未读取'
}

export function manuscriptSpan(job: DesktopJob) {
  if (job.segments.length === 0) return null
  return Math.max(...job.segments.map((segment) => segment.end))
}

export function timeLabel(ms: number, milliseconds = false) {
  const minutes = String(Math.floor(ms / 60000)).padStart(2, '0')
  const seconds = String(Math.floor(ms / 1000) % 60).padStart(2, '0')
  return `${minutes}:${seconds}${milliseconds ? '.' + String(ms % 1000).padStart(3, '0') : ''}`
}

export function activeJob(job: DesktopJob) {
  return job.state === 'queued' || job.state === 'running'
}

/** 删除任务后维护当前选中项：被删任务仍选中时回退到剩余任务中最近创建的一条。 */
export function selectionAfterRemoval(
  remaining: Record<string, DesktopJob>, selected: string | null, removed: string,
) {
  if (selected !== removed) return selected
  return Object.values(remaining).sort((a, b) => b.created_at.localeCompare(a.created_at))[0]?.id ?? null
}

export function highlightedParts<Hit extends TermHit>(text: string, hits: Hit[]) {
  const letters = Array.from(text)
  let cursor = 0
  const parts: { text: string; hit?: Hit }[] = []
  for (const hit of [...hits].sort((a, b) => a.start - b.start)) {
    const matched = letters.slice(hit.start, hit.end).join('')
    if (hit.start < cursor || hit.end > letters.length || matched !== hit.matched_text) continue
    parts.push({ text: letters.slice(cursor, hit.start).join('') }, { text: matched, hit })
    cursor = hit.end
  }
  parts.push({ text: letters.slice(cursor).join('') })
  return parts
}
