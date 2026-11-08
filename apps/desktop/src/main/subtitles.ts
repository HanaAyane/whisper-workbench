import type { ExportFormat, Segment } from '../shared/api.js'

const pad = (value: number, length = 2) => String(value).padStart(length, '0')

export function timestamp(ms: number, separator = '.') {
  return `${pad(Math.floor(ms / 3600000))}:${pad(Math.floor(ms / 60000) % 60)}:${pad(Math.floor(ms / 1000) % 60)}${separator}${pad(ms % 1000, 3)}`
}

function lyricTime(ms: number) {
  return `[${pad(Math.floor(ms / 60000))}:${pad(Math.floor(ms / 1000) % 60)}.${pad(Math.floor(ms / 10) % 100)}]`
}

export function formatSubtitles(segments: Segment[], format: ExportFormat) {
  const cues = segments.map((segment) => ({
    segment,
    lines: [segment.text, segment.translation].flatMap(
      (text) => text?.trim().split(/\r?\n/).filter((line) => line.trim()) ?? [],
    ),
  })).filter(({ lines }) => lines.length)
  const blocks = cues.map(({ segment, lines }, index) => {
    const text = lines.join('\n')
    switch (format) {
      case 'txt': return text
      case 'lrc': return lines.map((line) => lyricTime(segment.start) + line).join('\n')
      case 'srt': return `${index + 1}\n${timestamp(segment.start, ',')} --> ${timestamp(segment.end, ',')}\n${text}`
      case 'vtt': {
        const escaped = text.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
        return `${timestamp(segment.start)} --> ${timestamp(segment.end)}\n${escaped}`
      }
    }
  })
  const separator = format === 'lrc' ? '\n' : '\n\n'
  const body = blocks.length ? blocks.join(separator) + '\n' : ''
  return format === 'vtt' ? 'WEBVTT\n\n' + body : body
}
