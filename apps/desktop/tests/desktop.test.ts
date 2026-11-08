import { strict as assert } from 'node:assert'
import { test } from 'node:test'
import { formatSubtitles } from '../src/main/subtitles.ts'
import { highlightedParts } from '../src/renderer/format.ts'
import type { Segment, TermHit } from '../src/shared/api.ts'

test('导出读取编辑后的双语字幕，忽略空片段并连续编号', () => {
  const segment: Segment = {
    id: 3, start: 3612345, end: 3614260, raw_text: 'モデル原文', raw_translation: '模型译文',
    text: '編集済み', translation: '当前译文', hits: [],
  }
  assert.equal(
    formatSubtitles([{ ...segment, text: '', translation: ' ' }, segment], 'srt'),
    '1\n01:00:12,345 --> 01:00:14,260\n編集済み\n当前译文\n',
  )
  assert.equal(formatSubtitles([{ ...segment, text: '<タグ> & 文' }], 'vtt'),
    'WEBVTT\n\n01:00:12.345 --> 01:00:14.260\n&lt;タグ&gt; &amp; 文\n当前译文\n')
  assert.equal(formatSubtitles([segment], 'lrc'), '[60:12.34]編集済み\n[60:12.34]当前译文\n')
  assert.equal(formatSubtitles([segment], 'txt'), '編集済み\n当前译文\n')
  assert.equal(formatSubtitles([], 'srt'), '')
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
