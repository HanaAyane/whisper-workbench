import { useEffect, useRef, useState } from 'react'
import { CircleAlert, CircleCheck, FileAudio, Mic, Plus, Square, Trash2, Upload, X } from 'lucide-react'
import type { DesktopJob, Glossary, JobOptions, MediaCheck, ModelInfo } from '../../shared/api'
import { exportFormats, mediaExtensions, type ExportFormat } from '../../shared/api'
import { activeJob, byteLabel, errorText, sampleLabel, timeLabel } from '../format'
import { useWorkbench } from '../store'

interface Props {
  models: ModelInfo[]
  glossaries: Glossary[]
  connected: boolean
  onCreated(job: DesktopJob): void
  onError(message: string): void
}

interface BatchRow {
  file: MediaCheck
  jobId: string | null
  submitError: string | null
  autoExport: boolean
  format: ExportFormat
  directory: string | null
  export: 'idle' | 'running' | 'done' | 'failed'
  exportPath: string | null
  exportError: string | null
}

const jobStates = {
  queued: '排队中', running: '处理中', succeeded: '转录完成', failed: '转录失败', cancelled: '已取消',
} as const

export function RecorderPanel({ models, glossaries, connected, onCreated, onError }: Props) {
  const [rows, setRows] = useState<BatchRow[]>([])
  const [recording, setRecording] = useState<Blob | null>(null)
  const [status, setStatus] = useState<'idle' | 'opening' | 'recording' | 'stopping'>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [keep, setKeep] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [selectedModel, setModel] = useState('')
  const [glossary, setGlossary] = useState('')
  const [mode, setMode] = useState<JobOptions['mode']>('transcribe')
  const [batchFormat, setBatchFormat] = useState<ExportFormat>('srt')
  const recorder = useRef<MediaRecorder | null>(null)
  const mounted = useRef(true)
  const startTime = useRef(0)
  const exporting = useRef<Set<string>>(new Set())
  const device = useWorkbench((state) => state.device)
  const computeType = useWorkbench((state) => state.computeType)
  const outputDir = useWorkbench((state) => state.outputDir)
  const setOutputDir = useWorkbench((state) => state.setOutputDir)
  const jobs = useWorkbench((state) => state.jobs)
  const modelId = models.find((model) => model.id === selectedModel && model.ok)?.id
    ?? models.find((model) => model.ok)?.id ?? ''
  const busy = status !== 'idle' || submitting
  const pendingCount = rows.filter((row) => row.file.ok && !row.jobId).length
  const batchMode = rows.length > 1

  useEffect(() => () => {
    mounted.current = false
    recorder.current?.stream.getTracks().forEach((track) => track.stop())
  }, [])

  useEffect(() => {
    if (status !== 'recording') return
    const timer = window.setInterval(() => setElapsed(Date.now() - startTime.current), 250)
    return () => window.clearInterval(timer)
  }, [status])

  useEffect(() => {
    for (const row of rows) {
      if (!row.jobId || !row.autoExport || row.export !== 'idle') continue
      if (jobs[row.jobId]?.state === 'succeeded') void runExport(row)
    }
  })

  async function runExport(row: BatchRow) {
    if (!row.jobId || !row.directory || exporting.current.has(row.jobId)) return
    exporting.current.add(row.jobId)
    const jobId = row.jobId
    setRows((current) => current.map((item) => item.jobId === jobId ? { ...item, export: 'running', exportError: null } : item))
    try {
      const path = await window.api.exportJobToDirectory(jobId, row.format, row.directory, row.file.name)
      setRows((current) => current.map((item) => item.jobId === jobId ? { ...item, export: 'done', exportPath: path } : item))
    } catch (error) {
      setRows((current) => current.map((item) => item.jobId === jobId ? { ...item, export: 'failed', exportError: errorText(error) } : item))
    } finally {
      exporting.current.delete(jobId)
    }
  }

  function retry(row: BatchRow) {
    setRows((current) => current.map((item) => item.file.id === row.file.id ? { ...item, export: 'idle', exportError: null } : item))
    void runExport({ ...row, export: 'idle' })
  }

  async function startRecording() {
    setStatus('opening')
    let stream: MediaStream | undefined
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      if (!mounted.current) {
        stream.getTracks().forEach((track) => track.stop())
        return
      }
      const capture = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' })
      const chunks: Blob[] = []
      let size = 0
      let invalid = false
      recorder.current = capture
      capture.ondataavailable = (event) => {
        size += event.data.size
        if (size > 256 * 1024 * 1024) {
          invalid = true
          onError('录音超过 256 MB，请分段录制。')
          if (capture.state === 'recording') capture.stop()
        } else if (event.data.size) chunks.push(event.data)
      }
      capture.onerror = () => {
        invalid = true
        if (mounted.current) onError('麦克风录制失败，请重新录音。')
      }
      capture.onstop = () => {
        capture.stream.getTracks().forEach((track) => track.stop())
        recorder.current = null
        if (!mounted.current) return
        setElapsed(Date.now() - startTime.current)
        setStatus('idle')
        if (!invalid && chunks.length) setRecording(new Blob(chunks, { type: capture.mimeType }))
        else if (!invalid) onError('录音为空，请重新录音。')
      }
      capture.start(1000)
      startTime.current = Date.now()
      setElapsed(0)
      setRecording(null)
      setRows([])
      setStatus('recording')
    } catch {
      stream?.getTracks().forEach((track) => track.stop())
      setStatus('idle')
      onError('无法访问麦克风，请检查系统录音权限和输入设备。')
    }
  }

  function stopRecording() {
    if (recorder.current?.state !== 'recording') return
    setStatus('stopping')
    recorder.current.stop()
  }

  function addChecks(checks: MediaCheck[]) {
    setRows((current) => {
      const seen = new Set(current.map((row) => row.file.id))
      const added = checks.filter((check) => !seen.has(check.id)).map((file): BatchRow => ({
        file, jobId: null, submitError: null, autoExport: false, format: 'srt', directory: null,
        export: 'idle', exportPath: null, exportError: null,
      }))
      return [...current, ...added]
    })
    setRecording(null)
    setElapsed(0)
  }

  async function selectFiles(chosen: Promise<MediaCheck[] | null>) {
    try {
      const checks = await chosen
      if (checks) addChecks(checks)
    } catch (error) {
      onError(errorText(error))
    }
  }

  async function chooseOutputDirectory() {
    try {
      const directory = await window.api.pickOutputDirectory()
      if (directory) setOutputDir(directory)
    } catch (error) {
      onError(errorText(error))
    }
  }

  async function submit() {
    if (busy || !modelId) return
    const options: JobOptions = {
      asr_model_id: modelId, mode,
      glossary_id: glossaries.some((item) => item.id === glossary) ? glossary : null,
      device, compute_type: computeType,
    }
    setSubmitting(true)
    try {
      if (recording && rows.length === 0) {
        const job = await window.api.createJob({ kind: 'recording', data: await recording.arrayBuffer(), keep }, options)
        onCreated(job)
        setRecording(null)
        setElapsed(0)
        return
      }
      const targets = rows.filter((row) => row.file.ok && !row.jobId)
      if (targets.length === 0) { onError('没有可提交的媒体文件。'); return }
      const isBatch = rows.length > 1
      if (isBatch && !outputDir) { onError('批量转录请先选择字幕输出目录。'); return }
      for (const row of targets) {
        try {
          const job = await window.api.createJob({ kind: 'file', id: row.file.id }, options)
          onCreated(job)
          setRows((current) => current.map((item) => item.file.id === row.file.id ? {
            ...item, jobId: job.id, submitError: null, autoExport: isBatch,
            format: batchFormat, directory: isBatch ? outputDir : null, export: 'idle',
          } : item))
        } catch (error) {
          setRows((current) => current.map((item) => item.file.id === row.file.id ? { ...item, submitError: errorText(error) } : item))
        }
      }
    } catch (error) {
      onError(errorText(error))
    } finally {
      setSubmitting(false)
    }
  }

  function rowStatus(row: BatchRow): { kind: 'pending' | 'error' | 'success' | 'muted'; text: string } {
    if (!row.file.ok) return { kind: 'error', text: row.file.error ?? '文件无效' }
    if (row.submitError) return { kind: 'error', text: row.submitError }
    if (!row.jobId) return { kind: 'pending', text: '待提交' }
    const job = jobs[row.jobId]
    if (!job) return { kind: 'pending', text: '已提交' }
    if (job.state === 'failed') return { kind: 'error', text: `转录失败：${job.error ?? job.message}` }
    if (job.state === 'cancelled') return { kind: 'muted', text: '已取消' }
    if (job.state === 'succeeded') {
      if (row.export === 'running') return { kind: 'pending', text: '转录完成，正在写入字幕' }
      if (row.export === 'done') return { kind: 'success', text: `已保存：${row.exportPath}` }
      if (row.export === 'failed') return { kind: 'error', text: `字幕写入失败：${row.exportError}` }
      return { kind: 'success', text: '转录完成' }
    }
    return { kind: 'pending', text: `${jobStates[job.state]} · ${job.message}` }
  }

  return <section className="compose">
    <div className="compose-top">
      <div className={`mic-area ${status === 'recording' ? 'recording' : ''}`}>
        <button className="mic-button" type="button" aria-label={status === 'recording' ? '停止录音' : '开始录音'}
          disabled={status === 'opening' || status === 'stopping' || submitting}
          onClick={() => status === 'recording' ? stopRecording() : void startRecording()}>
          {status === 'recording' ? <Square size={18} fill="currentColor" /> : <Mic size={20} />}
        </button>
        <strong className="clock">{timeLabel(elapsed)}</strong>
        <span className="muted">{status === 'recording' ? '正在录音' : status === 'opening' ? '等待麦克风' : recording ? '录音已就绪' : '麦克风录音'}</span>
      </div>
      <button type="button" className={`drop-area ${dragging ? 'dragging' : ''}`} disabled={busy}
        onClick={() => void selectFiles(window.api.pickAudioFiles())}
        onDragOver={(event) => { event.preventDefault(); setDragging(!busy) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          if (busy) return
          if (event.dataTransfer.files.length === 0) { onError('请拖入至少一个媒体文件。'); return }
          void selectFiles(window.api.registerDroppedAudios(Array.from(event.dataTransfer.files)))
        }}>
        <Upload size={18} />
        <strong>拖入多个文件，或点击多选</strong>
        <span className="muted">{mediaExtensions.map((extension) => extension.toUpperCase()).join(' / ')}</span>
      </button>
    </div>

    <div className="file-stack">
    {recording && <div className="selected-media">
      <FileAudio size={15} /><span>麦克风录音.webm</span>
      <label className="inline"><input type="checkbox" checked={keep} disabled={busy} onChange={(event) => setKeep(event.target.checked)} />保留录音副本</label>
      <button className="icon-button" type="button" aria-label="移除录音" disabled={busy} onClick={() => { setRecording(null); setElapsed(0) }}><X size={15} /></button>
    </div>}

    <div className="file-pane">
      <table className="file-table">
        <thead><tr><th>名称</th><th>采样</th><th>体积</th><th>状态</th><th><span className="sr-only">操作</span></th></tr></thead>
        <tbody>
          {rows.length === 0 ? <tr><td className="empty-files" colSpan={5}>还没有待提交的文件。录音或拖入媒体后，会列在这里。</td></tr>
            : rows.map((row) => {
              const state = rowStatus(row)
              const job = row.jobId ? jobs[row.jobId] : undefined
              return <tr className={`batch-row ${state.kind}`} key={row.file.id}>
                <td className="batch-name"><FileAudio size={14} />{row.file.name}</td>
                <td>{sampleLabel(row.file)}</td>
                <td>{row.file.bytes === undefined ? '—' : byteLabel(row.file.bytes)}</td>
                <td>
                  <span className={`batch-status ${state.kind}`} role="status">
                    {state.kind === 'error' ? <CircleAlert size={13} /> : state.kind === 'success' ? <CircleCheck size={13} /> : null}
                    {state.text}
                  </span>
                  {job && activeJob(job) && <progress max={1} value={job.progress} aria-label="任务进度" />}
                  {row.export === 'failed' && <button type="button" className="mini" onClick={() => retry(row)}>重新导出</button>}
                </td>
                <td>
                  <button className="icon-button" type="button" aria-label={`移除 ${row.file.name}`}
                    disabled={busy || row.jobId !== null}
                    onClick={() => setRows((current) => current.filter((item) => item.file.id !== row.file.id))}><Trash2 size={14} /></button>
                </td>
              </tr>
            })}
        </tbody>
      </table>
    </div>
    </div>

    <div className="compose-bar">
      <div className="form-grid capture-form">
        <label>转录模型<select value={modelId} onChange={(event) => setModel(event.target.value)} disabled={submitting}>
          {!modelId && <option value="">暂无可用模型</option>}
          {models.map((model) => <option key={model.id} value={model.id} disabled={!model.ok}>{model.label}{model.ok ? '' : '（文件缺失）'}</option>)}
        </select></label>
        <label>处理模式<select value={mode} onChange={(event) => setMode(event.target.value as JobOptions['mode'])} disabled={submitting}>
          <option value="transcribe">仅日语转录</option><option value="translate">日语转录 + 中文翻译</option>
        </select></label>
        <label>应用词表<select value={glossaries.some((item) => item.id === glossary) ? glossary : ''} onChange={(event) => setGlossary(event.target.value)} disabled={submitting}>
          <option value="">不使用词表</option>{glossaries.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}
        </select></label>
      </div>
      {rows.length > 0 && <div className="form-grid capture-form">
        <label>批量输出格式<select value={batchFormat} onChange={(event) => setBatchFormat(event.target.value as ExportFormat)} disabled={submitting}>
          {exportFormats.map((item) => <option key={item} value={item}>{item.toUpperCase()}</option>)}
        </select></label>
        <label>字幕输出目录
          <div className="button-row">
            <span className="muted path-ellipsis">{outputDir ?? '未选择（批量转录前必选）'}</span>
            <button type="button" onClick={() => void chooseOutputDirectory()} disabled={submitting}>选择</button>
          </div>
        </label>
      </div>}
      <div className="capture-footer">
        <p className={mode === 'translate' ? 'privacy-warning' : 'muted'}>{mode === 'translate'
          ? '提交后，待翻译字幕文本会发送到本机配置的 DeepSeek API（默认 api.deepseek.com）。音频在本地处理。'
          : batchMode ? '按列表顺序进入单 worker 队列，成功后自动把已保存字幕写入所选目录。' : '音频仅在本机处理 · 默认使用本地转录'}</p>
        <div className="button-row">
          {rows.length > 0 && <button type="button" disabled={busy} onClick={() => setRows([])}>清空列表</button>}
          <button className="primary" disabled={busy || !connected || !modelId || (rows.length === 0 && !recording) || (batchMode && !outputDir)} onClick={() => void submit()}>
            <Plus size={16} /> {submitting ? '正在提交' : batchMode ? `开始批量处理（${pendingCount}）` : '开始处理'}
          </button>
        </div>
      </div>
    </div>
  </section>
}
