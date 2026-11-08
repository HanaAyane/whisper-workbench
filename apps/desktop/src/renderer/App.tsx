import { useCallback, useEffect, useState } from 'react'
import { AudioWaveform, BookOpen, CircleAlert, Moon, RotateCw, Settings2, ShieldCheck, Sun, X } from 'lucide-react'
import type { Glossary, ModelCatalog } from '../shared/api'
import { ExportBar } from './components/ExportBar'
import { GlossaryPanel } from './components/GlossaryPanel'
import { JobList } from './components/JobList'
import { RecorderPanel } from './components/RecorderPanel'
import { SettingsPanel } from './components/SettingsPanel'
import { TranscriptEditor } from './components/TranscriptEditor'
import { errorText } from './format'
import { Glass } from './Glass'
import { useWorkbench } from './store'

const tabs = [
  { id: 'workbench', label: '工作台', icon: AudioWaveform },
  { id: 'glossary', label: '术语表', icon: BookOpen },
  { id: 'settings', label: '设置', icon: Settings2 },
] as const

export function App() {
  const [page, setPage] = useState<(typeof tabs)[number]['id']>('workbench')
  const [connection, setConnection] = useState<'loading' | 'online' | 'offline'>('loading')
  const [catalog, setCatalog] = useState<ModelCatalog | null>(null)
  const [glossaries, setGlossaries] = useState<Glossary[]>([])
  const [notice, setNotice] = useState<{ kind: 'error' | 'success'; message: string } | null>(null)
  const theme = useWorkbench((state) => state.theme)
  const toggleTheme = useWorkbench((state) => state.toggleTheme)
  const job = useWorkbench((state) => state.selectedJob ? state.jobs[state.selectedJob] : undefined)
  const putJob = useWorkbench((state) => state.putJob)
  const mergeJobs = useWorkbench((state) => state.mergeJobs)

  const onError = useCallback((message: string) => setNotice({ kind: 'error', message }), [])
  const onSaved = useCallback((message: string) => setNotice({ kind: 'success', message }), [])
  const refreshGlossaries = useCallback(async () => setGlossaries(await window.api.listGlossaries()), [])
  const refresh = useCallback(async () => {
    setConnection('loading')
    setNotice(null)
    try {
      const [, models, jobs] = await Promise.all([window.api.health(), window.api.models(), window.api.listJobs(), refreshGlossaries()])
      setCatalog(models)
      mergeJobs(jobs)
      setConnection('online')
    } catch (error) {
      setConnection('offline')
      onError(errorText(error))
    }
  }, [mergeJobs, onError, refreshGlossaries])

  useEffect(() => {
    const unsubscribe = window.api.onJobUpdate(putJob)
    void refresh()
    return unsubscribe
  }, [putJob, refresh])

  useEffect(() => { document.documentElement.dataset.theme = theme }, [theme])

  const asrModels = catalog?.models.filter((model) => model.type === 'asr') ?? []
  const title = page === 'glossary' ? '术语表' : page === 'settings' ? '工作台设置' : '日语语音工作台'
  const caption = page === 'glossary' ? '维护常见误识别、专有名词和统一译名。'
    : page === 'settings' ? '配置本地模型、推理设备和字幕保存位置。'
      : '从日语音频到可编辑的字幕。'

  return <div className="app-shell" onDragOver={(event) => event.preventDefault()} onDrop={(event) => event.preventDefault()}>
    <div className="wallpaper" aria-hidden="true">
      <svg viewBox="0 0 1440 900" preserveAspectRatio="xMidYMid slice">
        <defs><linearGradient id="wave" x2="1" y2="1"><stop stopColor="currentColor" stopOpacity=".36" /><stop offset="1" stopColor="currentColor" stopOpacity="0" /></linearGradient></defs>
        <g fill="none" stroke="url(#wave)" strokeWidth="1.2">
          {Array.from({ length: 11 }, (_, index) => <path key={index} transform={`translate(0 ${index * 10})`} d="M-140 300C180 50 319 580 684 412S1229 21 1570 224" />)}
        </g>
      </svg>
    </div>
    <div className="shell-content">
      <Glass className="topbar">
        <div className="wordmark"><span className="brand-mark"><AudioWaveform size={22} /></span><div><strong>语音工作台</strong><small>JP VOICE WORKBENCH</small></div></div>
        <nav aria-label="主导航">{tabs.map(({ id, label, icon: Icon }) => <button key={id} type="button" aria-current={page === id ? 'page' : undefined} onClick={() => setPage(id)}><Icon size={17} />{label}</button>)}</nav>
        <div className="top-actions">
          <span className={`connection ${connection}`} role="status"><i />{connection === 'online' ? '本地服务就绪' : connection === 'loading' ? '正在连接' : '本地服务离线'}</span>
          <button type="button" className="icon-button" title="刷新本地服务" aria-label="刷新本地服务" disabled={connection === 'loading'} onClick={() => void refresh()}><RotateCw size={17} /></button>
          <button type="button" className="icon-button" aria-label={theme === 'light' ? '切换深色模式' : '切换浅色模式'} onClick={toggleTheme}>{theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}</button>
        </div>
      </Glass>

      <main>
        <header className="page-heading">
          <div><p className="eyebrow">{page === 'workbench' ? '日本語  /  字幕制作' : page === 'glossary' ? 'GLOSSARY' : 'PREFERENCES'}</p><h1>{title}</h1><p>{caption}</p></div>
          <div className="local-badge"><ShieldCheck size={17} /><span>本地处理音频</span></div>
        </header>
        {notice && <div className={`notice ${notice.kind}`} role={notice.kind === 'error' ? 'alert' : 'status'}>
          {notice.kind === 'error' ? <CircleAlert size={18} /> : <ShieldCheck size={18} />}
          <span>{notice.message}</span><button type="button" className="icon-button" aria-label="关闭消息" onClick={() => setNotice(null)}><X size={16} /></button>
        </div>}
        {page === 'workbench' && connection === 'online' && !asrModels.some((model) => model.ok) && <div className="notice" role="status">
          <CircleAlert size={18} /><span>未找到可用的日语转录模型。</span><button onClick={() => setPage('settings')}>检查模型路径</button>
        </div>}
        <div className="workspace" hidden={page !== 'workbench'}>
          <RecorderPanel models={asrModels} glossaries={glossaries} connected={connection === 'online'}
            onCreated={(created) => { putJob(created, true); setNotice(null) }} onError={onError} />
          <JobList onError={onError} />
          <TranscriptEditor job={job} onError={onError} />
          <ExportBar job={job} onError={onError} onSaved={onSaved} />
        </div>
        <div hidden={page !== 'glossary'}>
          <GlossaryPanel glossaries={glossaries} onChange={refreshGlossaries} onError={onError} onSaved={onSaved} />
        </div>
        {page === 'settings' && <SettingsPanel catalog={catalog} onCatalog={setCatalog} onError={onError} />}
      </main>
    </div>
  </div>
}
