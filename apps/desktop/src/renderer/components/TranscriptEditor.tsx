import { useState } from 'react'
import { Captions, Check, Clock3, Pencil } from 'lucide-react'
import type { DesktopJob, Segment, SegmentEdit } from '../../shared/api'
import { errorText, timeLabel } from '../format'
import { Highlight, policyLabel } from './Highlight'

function TranscriptRow({ jobId, segment, onError }: { jobId: string; segment: Segment; onError(message: string): void }) {
  const [draft, setDraft] = useState<SegmentEdit | null>(null)
  const [saving, setSaving] = useState(false)
  async function save(edit: SegmentEdit) {
    setSaving(true)
    try {
      await window.api.updateSegment(jobId, segment.id, edit)
      setDraft(null)
    } catch (error) {
      onError(errorText(error))
    } finally {
      setSaving(false)
    }
  }

  return <article className="segment-row">
    <div className="segment-heading">
      <span className="timecode"><Clock3 size={14} /> {timeLabel(segment.start, true)} — {timeLabel(segment.end, true)}</span>
      {draft ? <div className="button-row">
        <button disabled={saving} onClick={() => setDraft(null)}>取消编辑</button>
        <button className="primary small" disabled={saving} onClick={() => void save(draft)}><Check size={14} /> 保存</button>
      </div> : <button onClick={() => setDraft({ text: segment.text, translation: segment.translation })}><Pencil size={14} /> 编辑</button>}
    </div>
    <div className="segment-columns">
      <div className="segment-content">
        <small>模型原始输出</small>
        <p lang="ja"><Highlight text={segment.raw_text} hits={segment.hits.filter((hit) => hit.field === 'text')} /></p>
        {segment.raw_translation !== null && <p><Highlight text={segment.raw_translation} hits={segment.hits.filter((hit) => hit.field === 'translation')} /></p>}
      </div>
      <div className="segment-content">
        <small>当前字幕</small>
        {draft ? <div className="stack">
          <textarea lang="ja" aria-label="编辑日语原文" rows={2} disabled={saving} value={draft.text} onChange={(event) => setDraft({ ...draft, text: event.target.value })} />
          {draft.translation !== null && <textarea aria-label="编辑中文译文" rows={2} disabled={saving} value={draft.translation} onChange={(event) => setDraft({ ...draft, translation: event.target.value })} />}
        </div> : <>
          <p lang="ja">{segment.text || '（空）'}</p>
          {segment.translation !== null && <p>{segment.translation || '（空）'}</p>}
        </>}
      </div>
    </div>
    {segment.hits.length > 0 && <ul className="hit-list">{segment.hits.map((hit) =>
      <li key={`${hit.field}-${hit.start}-${hit.entry_id}`}><strong>{policyLabel[hit.policy]}</strong> {hit.matched_text}{hit.replacement && ` → ${hit.replacement}`}</li>
    )}</ul>}
  </article>
}

export function TranscriptEditor({ job, onError }: { job?: DesktopJob; onError(message: string): void }) {
  const empty = !job || job.segments.length === 0
  const note = !job ? '提交音频后，分段字幕会显示在此处。'
    : job.state === 'succeeded' ? '没有检测到可转录的语音。'
      : job.error ?? job.message

  return <section className="solid transcript">
    <div className="section-heading">
      <div className="panel-heading"><div className="icon-tile"><Captions size={21} /></div>
        <div><h2>字幕复核</h2><p>{job ? `${job.name} · ${job.segments.length} 段` : '查看并编辑转录结果'}</p></div>
      </div>
      {job && <span className="label-pill">{job.mode === 'translate' ? '日语 / 中文' : '日语'}</span>}
    </div>
    {job?.recorded_path && <p className="saved-path">录音副本 · {job.recorded_path}</p>}
    {empty ? <div className="empty-transcript"><Captions size={30} /><p>{note}</p></div>
      : <div className="segments">{job.segments.map((segment) =>
        <TranscriptRow key={`${job.id}-${segment.id}`} jobId={job.id} segment={segment} onError={onError} />,
      )}</div>}
  </section>
}
