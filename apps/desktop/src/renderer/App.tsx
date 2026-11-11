import { useCallback, useEffect, useState } from 'react'
import { AudioWaveform, BookOpen, CircleAlert, FolderOpen, Moon, Plus, RotateCw, Settings2, ShieldCheck, Sun, X } from 'lucide-react'
import { APP_NAME } from '../shared/api'
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

const primary = [
  { id: 'compose', label: '新建', icon: Plus },
  { id: 'workbench', label: '工作台', icon: AudioWaveform },
  { id: 'glossary', label: '术语表', icon: BookOpen },
] as const

type PageId = (typeof primary)[number]['id'] | 'settings'

export function App() {
  const [page, setPage] = useState<PageId>('compose')
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

  // 成功提示不长期停留，避免盖住下面的录音和提交按钮；错误提示保留到用户关闭。
  useEffect(() => {
    if (notice?.kind !== 'success') return
    const timer = window.setTimeout(() => setNotice(null), 6000)
    return () => window.clearTimeout(timer)
  }, [notice])

  const asrModels = catalog?.models.filter((model) => model.type === 'asr') ?? []
  const modelWarning = connection === 'online' && !asrModels.some((model) => model.ok)
  const showModelWarning = modelWarning && (page === 'compose' || page === 'workbench')

  return <div className="app-shell">
    <div className="scene" aria-hidden="true" />
    <Glass className="rail">
      <div className="mark"><AudioWaveform size={16} /><span>{APP_NAME}</span></div>
      <nav aria-label="主导航">
        {primary.map(({ id, label, icon: Icon }) => <button key={id} type="button" aria-current={page === id ? 'page' : undefined} onClick={() => setPage(id)}><Icon size={16} />{label}</button>)}
        <button type="button" className="rail-end" aria-current={page === 'settings' ? 'page' : undefined} onClick={() => setPage('settings')}><Settings2 size={16} />设置</button>
      </nav>
    </Glass>
    <div className="column">
      <Glass className="topbar">
        <span className={`connection ${connection}`} role="status"><i />{connection === 'online' ? '本地服务就绪' : connection === 'loading' ? '正在连接' : '本地服务离线'}</span>
        <span className="local-note"><ShieldCheck size={14} />本地处理音频</span>
        <div className="top-actions">
          <button type="button" className="icon-button" title="刷新本地服务" aria-label="刷新本地服务" disabled={connection === 'loading'} onClick={() => void refresh()}><RotateCw size={16} /></button>
          <button type="button" className="icon-button" aria-label={theme === 'light' ? '切换深色模式' : '切换浅色模式'} onClick={toggleTheme}>{theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}</button>
        </div>
      </Glass>
      <main className="workspace">
        {notice && <Glass className="toast">
          <div className={`notice ${notice.kind}`} role={notice.kind === 'error' ? 'alert' : 'status'}>
            {notice.kind === 'error' ? <CircleAlert size={16} /> : <ShieldCheck size={16} />}
            <span>{notice.message}</span>
            <button type="button" className="icon-button" aria-label="关闭消息" onClick={() => setNotice(null)}><X size={15} /></button>
          </div>
        </Glass>}
        <div className="page-sheet" hidden={page !== 'compose'}>
          {showModelWarning && page === 'compose' && <ModelWarning catalog={catalog} onError={onError} onSettings={() => setPage('settings')} />}
          <RecorderPanel models={asrModels} glossaries={glossaries} connected={connection === 'online'}
            onCreated={(created) => { putJob(created, true); setNotice(null) }} onError={onError} />
        </div>
        <div className="page-sheet" hidden={page !== 'workbench'}>
          {showModelWarning && page === 'workbench' && <ModelWarning catalog={catalog} onError={onError} onSettings={() => setPage('settings')} />}
          <div className="bench">
            <JobList onError={onError} />
            <div className="editor-pane">
              <TranscriptEditor job={job} onError={onError} />
              <ExportBar job={job} onError={onError} onSaved={onSaved} />
            </div>
          </div>
        </div>
        <div className="page-sheet" hidden={page !== 'glossary'}>
          <GlossaryPanel glossaries={glossaries} onChange={refreshGlossaries} onError={onError} onSaved={onSaved} />
        </div>
        <div className="page-sheet" hidden={page !== 'settings'}>
          <SettingsPanel catalog={catalog} onCatalog={setCatalog} onError={onError} />
        </div>
      </main>
    </div>
  </div>
}

function ModelWarning({ catalog, onError, onSettings }: { catalog: ModelCatalog | null; onError(message: string): void; onSettings(): void }) {
  return <div className="notice" role="status">
    <CircleAlert size={16} />
    <span>{catalog?.source === 'discovery'
      ? '未找到可用的日语转录模型。请把本地 CT2 模型放入安装目录的 model/ 子目录，再在设置页重新扫描。'
      : '未找到可用的日语转录模型。请放入本地 CT2 模型，或在设置中选择已有清单。'}</span>
    <button onClick={() => void window.api.openModelDirectory().catch((error) => onError(errorText(error)))}><FolderOpen size={15} /> 打开模型目录</button>
    <button onClick={onSettings}>检查模型路径</button>
  </div>
}
