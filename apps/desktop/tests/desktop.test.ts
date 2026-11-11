import { strict as assert } from 'node:assert'
import { mkdtemp, readFile, readdir, rm, rmdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { writeExportFile, subtitleBaseName, writeSubtitleWithUniqueName } from '../src/main/export-file.ts'
import { readMediaInfo } from '../src/main/media-info.ts'
import { byteLabel, highlightedParts, sampleLabel } from '../src/renderer/format.ts'
import type { TermHit } from '../src/shared/api.ts'

test('字幕导出保护同名文件，并能按明确策略替换 UTF-8 文件', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'jp-workbench-export-'))
  const output = join(directory, '字幕.srt')
  try {
    await writeExportFile(output, '既存字幕', false)
    await assert.rejects(writeExportFile(output, '编辑済み', false), { code: 'EEXIST' })
    assert.equal(await readFile(output, 'utf8'), '既存字幕')
    await writeExportFile(output, '編集済み\n当前译文', true)
    assert.equal(await readFile(output, 'utf8'), '編集済み\n当前译文')
    assert.deepEqual(await readdir(directory), ['字幕.srt'])
  } finally {
    await rm(output, { force: true })
    await rmdir(directory)
  }
})

test('字幕主文件名去掉扩展名并替换非法字符，空名回退为字幕', () => {
  assert.equal(subtitleBaseName('第一期 录音.mp3'), '第一期 录音')
  assert.equal(subtitleBaseName('a<b>c?.wav'), 'a-b-c-')
  assert.equal(subtitleBaseName('.wav'), '字幕')
})

test('批量自动导出遇到同名文件时追加序号并用排他写入保护已有文件', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'jp-workbench-batch-'))
  try {
    const first = await writeSubtitleWithUniqueName(directory, 'clip.wav', 'srt', '第一份')
    assert.equal(first, join(directory, 'clip.srt'))
    const second = await writeSubtitleWithUniqueName(directory, 'clip.wav', 'srt', '第二份')
    assert.equal(second, join(directory, 'clip (1).srt'))
    const third = await writeSubtitleWithUniqueName(directory, 'clip.wav', 'vtt', '第三份')
    assert.equal(third, join(directory, 'clip.vtt'))
    assert.equal(await readFile(first, 'utf8'), '第一份')
    assert.equal(await readFile(second, 'utf8'), '第二份')
    assert.deepEqual((await readdir(directory)).sort(), ['clip (1).srt', 'clip.srt', 'clip.vtt'])
  } finally {
    await rm(directory, { recursive: true, force: true })
  }
})

test('命中高亮按 Python Unicode 字符位置切分，并跳过失效位置', () => {
  const hit: TermHit = {
    entry_id: 'term', field: 'text', start: 1, end: 3, matched_text: '田中',
    replacement: '田中太郎', policy: 'correct', confidence: 1,
  }
  assert.deepEqual(highlightedParts('🎙田中さん', [hit]), [
    { text: '🎙' }, { text: '田中', hit }, { text: 'さん' },
  ])
  assert.deepEqual(highlightedParts('🎙山田さん', [hit]), [{ text: '🎙山田さん' }])
})

test('WAV 和 FLAC 文件头给出采样率，其他容器不编造采样率', () => {
  const wav = new Uint8Array(44)
  wav.set([0x52, 0x49, 0x46, 0x46, 0, 0, 0, 0, 0x57, 0x41, 0x56, 0x45, 0x66, 0x6d, 0x74, 0x20])
  const view = new DataView(wav.buffer)
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, 16000, true)
  view.setUint16(34, 16, true)
  assert.deepEqual(readMediaInfo(wav), { sampleRate: 16000, channels: 1, bitDepth: 16 })

  const flac = new Uint8Array(42)
  flac.set([0x66, 0x4c, 0x61, 0x43, 0, 0, 0, 34])
  flac[18] = 0x0a
  flac[19] = 0xc4
  flac[20] = 0x42
  flac[21] = 0xf0
  assert.deepEqual(readMediaInfo(flac), { sampleRate: 44100, channels: 2, bitDepth: 16 })
  assert.deepEqual(readMediaInfo(new Uint8Array([0, 1, 2, 3])), {})
  assert.equal(sampleLabel({ name: 'clip.mp3' }), 'MP3')
  assert.equal(sampleLabel({ name: 'take.wav', sampleRate: 48000, channels: 2, bitDepth: 24 }), '48 kHz · 立体声 · 24 bit')
  assert.equal(byteLabel(1536), '1.5 KB')
})
