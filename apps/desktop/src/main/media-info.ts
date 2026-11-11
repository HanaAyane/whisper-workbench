export interface MediaSample {
  sampleRate?: number
  channels?: number
  bitDepth?: number
}

export function readMediaInfo(bytes: Uint8Array): MediaSample {
  return readWave(bytes) ?? readFlac(bytes) ?? {}
}

function readWave(bytes: Uint8Array): MediaSample | null {
  if (bytes.length < 44 || ascii(bytes, 0, 4) !== 'RIFF' || ascii(bytes, 8, 12) !== 'WAVE') return null
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  let offset = 12
  while (offset + 8 <= bytes.length) {
    const id = ascii(bytes, offset, offset + 4)
    const size = view.getUint32(offset + 4, true)
    if (id === 'fmt ' && offset + 24 <= bytes.length) {
      const channels = view.getUint16(offset + 10, true)
      const sampleRate = view.getUint32(offset + 12, true)
      const bitDepth = view.getUint16(offset + 22, true)
      if (sampleRate > 0 && sampleRate < 384000 && channels > 0 && channels <= 16) {
        return { sampleRate, channels, bitDepth: bitDepth > 0 && bitDepth <= 64 ? bitDepth : undefined }
      }
    }
    const step = 8 + size + (size % 2)
    if (step <= 8) break
    offset += step
  }
  return null
}

function readFlac(bytes: Uint8Array): MediaSample | null {
  if (bytes.length < 42 || ascii(bytes, 0, 4) !== 'fLaC' || (bytes[4] & 0x7f) !== 0) return null
  const sampleRate = (bytes[18] << 12) | (bytes[19] << 4) | (bytes[20] >> 4)
  const channels = ((bytes[20] & 0x0e) >> 1) + 1
  const bitDepth = (((bytes[20] & 1) << 4) | (bytes[21] >> 4)) + 1
  if (sampleRate <= 0 || sampleRate >= 384000 || channels > 16 || bitDepth > 64) return null
  return { sampleRate, channels, bitDepth }
}

function ascii(bytes: Uint8Array, start: number, end: number) {
  let text = ''
  for (let index = start; index < end; index++) text += String.fromCharCode(bytes[index])
  return text
}
