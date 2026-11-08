import { useEffect, useRef, useState } from 'react'
import { AudioLines, FileAudio, Mic, Plus, Square, Upload, X } from 'lucide-react'
import type { AudioFile, DesktopJob, Glossary, JobInput, JobOptions, ModelInfo } from '../../shared/api'
import { mediaExtensions } from '../../shared/api'
import { errorText, timeLabel } from '../format'
import { Glass } from '../Glass'
import { useWorkbench } from '../store'

interface Props {
  models: ModelInfo[]
  glossaries: Glossary[]
  connected: boolean
  onCreated(job: DesktopJob): void
  onError(message: string): void
}

export function RecorderPanel({ models, glossaries, connected, onCreated, onError }: Props) {
  const [file, setFile] = useState<AudioFile | null>(null)
  const [recording, setRecording] = useState<Blob | null>(null)
  const [status, setStatus] = useState<'idle' | 'opening' | 'recording' | 'stopping'>('idle')
  const [elapsed, setElapsed] = useState(0)
  const [keep, setKeep] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [selectedModel, setModel] = useState('')
  const [glossary, setGlossary] = useState('')
  const [mode, setMode] = useState<JobOptions['mode']>('transcribe')
  const recorder = useRef<MediaRecorder | null>(null)
  const mounted = useRef(true)
  const startTime = useRef(0)
  const device = useWorkbench((state) => state.device)
  const computeType = useWorkbench((state) => state.computeType)
  const modelId = models.find((model) => model.id === selectedModel && model.ok)?.id
    ?? models.find((model) => model.ok)?.id ?? ''
  const busy = status !== 'idle' || submitting

  useEffect(() => () => {
    mounted.current = false
    recorder.current?.stream.getTracks().forEach((track) => track.stop())
  }, [])

  useEffect(() => {
    if (status !== 'recording') return
    const timer = window.setInterval(() => setElapsed(Date.now() - startTime.current), 250)
    return () => window.clearInterval(timer)
  }, [status])

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
      setFile(null)
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

  async function selectFile(chosen: Promise<AudioFile | null>) {
    try {
      const picked = await chosen
      if (picked) {
        setFile(picked)
        setRecording(null)
        setElapsed(0)
      }
    } catch (error) {
      onError(errorText(error))
    }
  }

  async function submit() {
    if (busy || !modelId || (!file && !recording)) return
    setSubmitting(true)
    try {
      const input: JobInput = recording
        ? { kind: 'recording', data: await recording.arrayBuffer(), keep }
        : { kind: 'file', id: file!.id }
      const job = await window.api.createJob(input, {
        asr_model_id: modelId, mode, glossary_id: glossaries.some((item) => item.id === glossary) ? glossary : null,
        device, compute_type: computeType,
      })
      onCreated(job)
      setFile(null)
      setRecording(null)
      setElapsed(0)
    } catch (error) {
      onError(errorText(error))
    } finally {
      setSubmitting(false)
    }
  }

  return <Glass className="capture">
    <div className="panel-heading">
      <div className="icon-tile"><AudioLines size={20} /></div>
      <div><h2>新建转录</h2><p>录制日语语音，或导入已有媒体</p></div>
    </div>
    <div className="capture-options">
      <div className={`mic-area ${status === 'recording' ? 'recording' : ''}`}>
        <button className="mic-button" type="button" aria-label={status === 'recording' ? '停止录音' : '开始录音'}
          disabled={status === 'opening' || status === 'stopping' || submitting}
          onClick={() => status === 'recording' ? stopRecording() : void startRecording()}>
          {status === 'recording' ? <Square size={21} fill="currentColor" /> : <Mic size={25} />}
        </button>
        <strong className="clock">{timeLabel(elapsed)}</strong>
        <span className="muted">{status === 'recording' ? '正在录音' : status === 'opening' ? '等待麦克风' : recording ? '录音已就绪' : '麦克风录音'}</span>
      </div>
      <button type="button" className={`drop-area ${dragging ? 'dragging' : ''}`} disabled={busy}
        onClick={() => void selectFile(window.api.pickAudioFile())}
        onDragOver={(event) => { event.preventDefault(); setDragging(!busy) }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          if (busy) return
          if (event.dataTransfer.files.length !== 1) { onError('每次请选择一个媒体文件。'); return }
          void selectFile(window.api.registerDroppedAudio(event.dataTransfer.files[0]))
        }}>
        <Upload size={22} />
        <strong>拖入文件，或点击选择</strong>
        <span className="muted">{mediaExtensions.map((extension) => extension.toUpperCase()).join(' / ')}</span>
      </button>
    </div>
    {(file || recording) && <div className="selected-media">
      <FileAudio size={16} /><span>{file?.name ?? '麦克风录音.webm'}</span>
      {recording && <label className="inline"><input type="checkbox" checked={keep} disabled={busy} onChange={(event) => setKeep(event.target.checked)} />保留录音副本</label>}
      <button className="icon-button" type="button" aria-label="移除媒体" disabled={busy} onClick={() => { setFile(null); setRecording(null); setElapsed(0) }}><X size={16} /></button>
    </div>}
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
    <div className="capture-footer">
      <p className={mode === 'translate' ? 'privacy-warning' : 'muted'}>{mode === 'translate'
        ? '提交后，待翻译字幕文本会发送到本机配置的 DeepSeek API（默认 api.deepseek.com）。音频在本地处理。'
        : '音频仅在本机处理 · 默认使用本地转录'}</p>
      <button className="primary" disabled={busy || !connected || !modelId || (!file && !recording)} onClick={() => void submit()}>
        <Plus size={17} /> {submitting ? '正在提交' : '开始处理'}
      </button>
    </div>
  </Glass>
}
