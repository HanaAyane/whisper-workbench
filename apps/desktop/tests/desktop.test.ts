import { strict as assert } from 'node:assert'
import { mkdtemp, readFile, readdir, rm, rmdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { writeExportFile, subtitleBaseName, writeSubtitleWithUniqueName } from '../src/main/export-file.ts'
import { highlightedParts } from '../src/renderer/format.ts'
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
