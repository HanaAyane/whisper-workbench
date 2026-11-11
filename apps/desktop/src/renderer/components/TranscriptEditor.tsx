import { useState } from 'react'
import { Check, Clock3, Pencil, Undo2 } from 'lucide-react'
import type { DesktopJob, ReviewHit, Segment, SegmentEdit } from '../../shared/api'
import { errorText, timeLabel } from '../format'
import { Highlight, policyLabel } from './Highlight'

function TranscriptRow({ jobId, segment, onError }: { jobId: string; segment: Segment; onError(message: string): void }) {
  const [draft, setDraft] = useState<SegmentEdit | null>(null)
  const [saving, setSaving] = useState(false)
  async function change(action: () => Promise<void>) {
    setSaving(true)
    try {
      await action()
      setDraft(null)
    } catch (error) {
      onError(errorText(error))
    } finally {
      setSaving(false)
    }
  }

  function decide(action: 'accept' | 'reject', hit: ReviewHit) {
    const { entry_id, field, start, end } = hit
    void change(() => window.api.reviewSegment(jobId, segment.id, {
      action, revision: segment.revision, hit: { entry_id, field, start, end },
    }))
  }

  return <article className="segment-row">
    <div className="segment-heading">
      <span className="timecode"><Clock3 size={14} /> {timeLabel(segment.start, true)} — {timeLabel(segment.end, true)}</span>
      {draft ? <div className="button-row">
        <button disabled={saving} onClick={() => setDraft(null)}>取消编辑</button>
        <button className="primary small" disabled={saving} onClick={() => void change(() => window.api.updateSegment(jobId, segment.id, draft))}><Check size={14} /> 保存</button>
      </div> : <div className="button-row">
        {segment.hits.some((hit) => hit.decision === 'accepted') && <button disabled={saving}
          onClick={() => void change(() => window.api.reviewSegment(jobId, segment.id, { action: 'undo', revision: segment.revision }))}>
          <Undo2 size={14} /> 撤销上次替换
        </button>}
        <button disabled={saving} onClick={() => setDraft({ text: segment.text, translation: segment.translation, revision: segment.revision })}><Pencil size={14} /> 编辑</button>
      </div>}
    </div>
    <div className="segment-columns">
      <div className="segment-content">
        <small>模型原始输出</small>
        <p lang="ja">{segment.raw_text}</p>
        {segment.raw_translation !== null && <p>{segment.raw_translation}</p>}
      </div>
      <div className="segment-content">
        <small>当前字幕</small>
        {draft ? <div className="stack">
          <textarea lang="ja" aria-label="编辑日语原文" rows={2} disabled={saving} value={draft.text} onChange={(event) => setDraft({ ...draft, text: event.target.value })} />
          {draft.translation !== null && <textarea aria-label="编辑中文译文" rows={2} disabled={saving} value={draft.translation} onChange={(event) => setDraft({ ...draft, translation: event.target.value })} />}
        </div> : <>
          <p lang="ja"><Highlight text={segment.text || '（空）'} hits={segment.hits.filter((hit) => hit.field === 'text')} /></p>
          {segment.translation !== null && <p><Highlight text={segment.translation || '（空）'} hits={segment.hits.filter((hit) => hit.field === 'translation')} /></p>}
        </>}
      </div>
    </div>
    {segment.hits.length > 0 && <ul className="hit-list" aria-label="术语建议">{segment.hits.map((hit) => {
      const canReplace = hit.replacement !== null && hit.matched_text !== hit.replacement
      const label = hit.decision === 'accepted' ? '已接受' : hit.decision === 'rejected' ? '已拒绝' : null
      return <li key={`${hit.field}-${hit.start}-${hit.entry_id}`}>
        <span><strong>{policyLabel[hit.policy]}</strong> {hit.original_text ?? hit.matched_text}
          {(canReplace || hit.decision === 'accepted') && ` → ${hit.replacement}`}
          {label && <small className={`review-label ${hit.decision}`}>{label}</small>}
        </span>
        {!label && canReplace && <div className="button-row">
          <button type="button" disabled={saving || !!draft} onClick={() => decide('accept', hit)}>接受</button>
          <button type="button" disabled={saving || !!draft} onClick={() => decide('reject', hit)}>拒绝</button>
        </div>}
      </li>
    })}</ul>}
  </article>
}

export function TranscriptEditor({ job, onError }: { job?: DesktopJob; onError(message: string): void }) {
  const empty = !job || job.segments.length === 0
  const note = !job ? '提交音频后，分段字幕会显示在此处。'
    : job.state === 'succeeded' ? '没有检测到可转录的语音。'
      : job.error ?? job.message

  return <section className="transcript">
    <div className="section-heading">
      <div className="pane-heading"><h2>字幕复核</h2><p>{job ? `${job.name} · ${job.segments.length} 段` : '查看并编辑转录结果'}</p></div>
      {job && <span className="label-pill">{job.mode === 'translate' ? '日语 / 中文' : '日语'}</span>}
    </div>
    {job?.recorded_path && <p className="saved-path">录音副本 · {job.recorded_path}</p>}
    {empty ? <div className="empty-transcript"><p>{note}</p></div>
      : <div className="segments">{job.segments.map((segment) =>
        <TranscriptRow key={`${job.id}-${segment.id}`} jobId={job.id} segment={segment} onError={onError} />,
      )}</div>}
  </section>
}
