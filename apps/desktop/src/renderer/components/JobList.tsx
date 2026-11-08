import { useState } from 'react'
import { AudioLines, Check, CircleAlert, Hourglass, ListChecks, X } from 'lucide-react'
import { activeJob, errorText } from '../format'
import { Glass } from '../Glass'
import { useWorkbench } from '../store'

const states = { queued: '排队中', running: '处理中', succeeded: '已完成', failed: '失败', cancelled: '已取消' }
const icons = { queued: Hourglass, running: AudioLines, succeeded: Check, failed: CircleAlert, cancelled: X }

export function JobList({ onError }: { onError(message: string): void }) {
  const jobs = useWorkbench((state) => state.jobs)
  const selected = useWorkbench((state) => state.selectedJob)
  const select = useWorkbench((state) => state.selectJob)
  const [cancelled, setCancelled] = useState<Set<string>>(new Set())
  const rows = Object.values(jobs).reverse()

  async function cancel(id: string) {
    setCancelled((ids) => new Set(ids).add(id))
    try {
      await window.api.cancelJob(id)
    } catch (error) {
      setCancelled((ids) => new Set([...ids].filter((item) => item !== id)))
      onError(errorText(error))
    }
  }

  return <Glass className="jobs-panel">
    <div className="panel-heading">
      <div className="icon-tile"><ListChecks size={20} /></div>
      <div><h2>任务列表</h2><p>当前会话 · {rows.length} 个任务</p></div>
    </div>
    {rows.length === 0 ? <div className="empty-jobs"><Hourglass size={23} /><strong>暂时没有任务</strong><p>开始处理后，进度会显示在这里。</p></div>
      : <ul className="job-items">{rows.map((job) => {
        const Icon = icons[job.state]
        return <li className={selected === job.id ? 'job-row selected' : 'job-row'} key={job.id}>
          <button type="button" className="job-select" onClick={() => select(job.id)} aria-pressed={selected === job.id}>
            <Icon size={18} className={`state-icon ${job.state}`} />
            <span><strong>{job.name}</strong><small>{states[job.state]} · {job.message}</small></span>
          </button>
          {activeJob(job) && <button className="icon-button" title="取消任务" aria-label="取消任务" disabled={cancelled.has(job.id)} onClick={() => void cancel(job.id)}><X size={17} /></button>}
          {activeJob(job) && <progress max={1} value={job.progress} aria-label="任务进度" />}
        </li>
      })}</ul>}
  </Glass>
}
