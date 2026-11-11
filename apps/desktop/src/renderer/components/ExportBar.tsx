import { useState } from 'react'
import { Download } from 'lucide-react'
import { exportFormats, type DesktopJob, type ExportFormat, type OverwritePolicy } from '../../shared/api'
import { errorText } from '../format'

export function ExportBar({ job, onError, onSaved }: { job?: DesktopJob; onError(message: string): void; onSaved(message: string): void }) {
  const [format, setFormat] = useState<ExportFormat>('srt')
  const [policy, setPolicy] = useState<OverwritePolicy>('preserve')
  const [saving, setSaving] = useState(false)
  async function save() {
    if (!job) return
    setSaving(true)
    try {
      const path = await window.api.exportJob(job.id, format, policy)
      if (path) onSaved(`字幕已保存至 ${path}`)
    } catch (error) {
      onError(errorText(error))
    } finally {
      setSaving(false)
    }
  }
  return <div className="export-bar">
    <div className="export-label"><Download size={18} /><div><strong>导出字幕</strong><p className="muted">{job?.state === 'succeeded' ? '使用已保存的当前字幕 · UTF-8' : '任务完成后可导出'}</p></div></div>
    <div className="button-row">
      <select aria-label="字幕格式" value={format} onChange={(event) => setFormat(event.target.value as ExportFormat)}>
        {exportFormats.map((item) => <option key={item} value={item}>{item.toUpperCase()}</option>)}
      </select>
      <select aria-label="覆盖策略" value={policy} onChange={(event) => setPolicy(event.target.value as OverwritePolicy)}>
        <option value="preserve">保留已有文件</option>
        <option value="replace">允许覆盖同名文件</option>
      </select>
      <button className="primary" disabled={saving || job?.state !== 'succeeded'} onClick={() => void save()}>{saving ? '正在保存' : '选择位置并保存'}</button>
    </div>
  </div>
}
