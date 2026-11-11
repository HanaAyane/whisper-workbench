import { useEffect, useState } from 'react'
import { FolderOpen, RefreshCw } from 'lucide-react'
import type { ComputeType, Device, ModelCatalog, TranslationPrompt } from '../../shared/api'
import { errorText } from '../format'
import { useWorkbench } from '../store'

function missingFiles(files: { path: string; ok: boolean }[]): string {
  return files.filter((file) => !file.ok).map((file) => file.path.split(/[\\/]/).pop() ?? file.path).join('、')
}

export function SettingsPanel({ catalog, onCatalog, onError }: {
  catalog: ModelCatalog | null
  onCatalog(catalog: ModelCatalog): void
  onError(message: string): void
}) {
  const device = useWorkbench((state) => state.device)
  const setDevice = useWorkbench((state) => state.setDevice)
  const computeType = useWorkbench((state) => state.computeType)
  const setComputeType = useWorkbench((state) => state.setComputeType)
  const outputDir = useWorkbench((state) => state.outputDir)
  const setOutputDir = useWorkbench((state) => state.setOutputDir)
  const [busy, setBusy] = useState(false)
  const [promptInfo, setPromptInfo] = useState<TranslationPrompt | null>(null)
  const [draft, setDraft] = useState('')
  const [promptState, setPromptState] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [promptError, setPromptError] = useState<string | null>(null)
  const discovery = catalog?.source === 'discovery'
  const hints = catalog?.hints
  const modelDirectory = catalog?.model_directory ?? (catalog ? catalog.manifest_path.replace(/[\\/][^\\/]+$/, '') : undefined)
  const sep = hints?.model_directory.includes('\\') ? '\\' : '/'

  async function rescan() {
    setBusy(true)
    try {
      onCatalog(await window.api.rescanModels())
    } catch (error) {
      onError(errorText(error))
    } finally {
      setBusy(false)
    }
  }

  async function changeModelDirectory() {
    setBusy(true)
    try {
      const result = await window.api.pickModelDirectory()
      if (result) onCatalog(result)
    } catch (error) {
      onError(errorText(error))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    window.api.translationPrompt()
      .then((info) => {
        setPromptInfo(info)
        setDraft(info.saved || info.default_prompt)
      })
      .catch((error: unknown) => setPromptError(errorText(error)))
  }, [])

  async function savePrompt(value: string) {
    setPromptState('saving')
    setPromptError(null)
    try {
      const info = await window.api.saveTranslationPrompt(value)
      setPromptInfo(info)
      setDraft(info.saved || info.default_prompt)
      setPromptState('saved')
    } catch (error) {
      setPromptError(errorText(error))
      setPromptState('idle')
    }
  }

  async function changeOutputDirectory() {
    try {
      const directory = await window.api.pickOutputDirectory()
      if (directory) setOutputDir(directory)
    } catch (error) {
      onError(errorText(error))
    }
  }

  return <div className="settings-page">
    <header className="pane-heading"><h1>工作台设置</h1><p>配置本地模型、推理设备和字幕保存位置。</p></header>
    <div className="settings-grid">
    <section className="settings-card">
      <div className="pane-heading"><h2>模型与文件</h2><p>本机目录</p></div>
      {discovery ? <div className="setting-line">
        <div>
          <strong>模型目录</strong>
          <p>{modelDirectory ?? '尚未连接本地服务'}</p>
          {hints && <>
            <p>放置位置示例：{hints.model_directory}{sep}{hints.example_subdirectory}{sep}</p>
            <p>所需文件：{hints.expected_files.join('、')}</p>
            <p>VAD 文件放在模型目录根：{hints.vad_files.join('、')}。{hints.note}</p>
          </>}
        </div>
        <div className="button-row">
          <button disabled={busy || !catalog} onClick={() => void window.api.openModelDirectory().catch((error) => onError(errorText(error)))}><FolderOpen size={16} /> 打开模型目录</button>
          <button disabled={busy} onClick={() => void rescan()}><RefreshCw size={16} /> {busy ? '正在扫描' : '重新扫描'}</button>
        </div>
      </div> : <div className="setting-line">
        <div>
          <strong>模型清单</strong>
          <p>{catalog?.manifest_path ?? '尚未连接本地服务'}</p>
          {catalog?.errors.map((error) => <p className="privacy-warning" key={error}>{error}</p>)}
        </div>
        <div className="button-row">
          <button disabled={busy || !catalog} onClick={() => void window.api.openModelDirectory().catch((error) => onError(errorText(error)))}><FolderOpen size={16} /> 打开模型目录</button>
          <button disabled={busy} onClick={() => void changeModelDirectory()}>{busy ? '正在切换' : '选择目录'}</button>
        </div>
      </div>}
      {discovery && catalog?.errors.map((error) => <p className="privacy-warning" key={error}>{error}</p>)}
      {catalog?.models.map((model) => <div className="setting-line" key={model.id}>
        <div><strong>{model.label}</strong><p>{model.path}</p>
          {!model.ok && model.files.length > 0 && <p>缺少文件：{missingFiles(model.files)}</p>}
        </div>
        <span className="label-pill">{model.ok ? '可用' : '未就绪'}</span>
      </div>)}
      {catalog?.vad && <p className="muted">语音检测 · {catalog.vad.ok ? '本地 ONNX' : '未找到 VAD，使用能量阈值回退'}{catalog.vad.ok || catalog.vad.files.length === 0 ? '' : `（缺少：${missingFiles(catalog.vad.files)}）`}</p>}
      <div className="setting-line">
        <div><strong>默认导出目录</strong><p>{outputDir ?? '由保存对话框选择'}</p></div>
        <button onClick={() => void changeOutputDirectory()}><FolderOpen size={16} /> 选择目录</button>
      </div>
    </section>
    <section className="settings-card">
      <div className="pane-heading"><h2>推理配置</h2><p>应用于新任务</p></div>
      <label>推理设备<select value={device ?? ''} onChange={(event) => setDevice(event.target.value as Device || null)}>
        <option value="">服务默认</option><option value="auto">自动</option><option value="cpu">CPU</option><option value="cuda">CUDA</option>
      </select></label>
      <label>计算类型<select value={computeType ?? ''} onChange={(event) => setComputeType(event.target.value as ComputeType || null)}>
        <option value="">模型默认</option>{['int8', 'int8_float16', 'float16', 'bfloat16'].map((type) => <option key={type}>{type}</option>)}
      </select></label>
      <p className="muted">音频始终留在本机。选择 DeepSeek 翻译时，待翻译字幕文本会发送到本机配置的 DeepSeek API（默认 api.deepseek.com）。API Key 由本地 .env 或环境变量提供。</p>
      <p className="muted">历史任务、原始字幕和已保存编辑存放在本机任务库。</p>
    </section>
    <section className="settings-card prompt-card">
      <div className="pane-heading"><h2>翻译提示词</h2><p>仅用于 DeepSeek 翻译模式</p></div>
      <p className="muted">
        这段预设会和后端固定的数据边界规则一起发给 DeepSeek。字幕原文用 &lt;subtitles&gt; 标签包住，
        标签内的内容一律只当作待翻译文本，不执行其中的指令。留空即使用内置预设。
      </p>
      {promptInfo ? <>
        <label className="prompt-label">系统提示词
          <textarea
            className="prompt-editor"
            rows={6}
            value={draft}
            maxLength={promptInfo.max_chars}
            disabled={promptState === 'saving'}
            onChange={(event) => {
              setDraft(event.target.value)
              setPromptState('idle')
            }}
          />
        </label>
        <div className="prompt-footer">
          <span className="muted">
            {draft.trim().length} / {promptInfo.max_chars} 字符{promptInfo.saved ? '' : ' · 当前为内置预设'}
          </span>
          <div className="button-row">
            <button type="button" disabled={promptState === 'saving' || !promptInfo.saved} onClick={() => void savePrompt('')}>恢复默认</button>
            <button type="button" disabled={promptState === 'saving'} onClick={() => void savePrompt(draft)}>
              {promptState === 'saving' ? '正在保存' : promptState === 'saved' ? '已保存' : '保存提示词'}
            </button>
          </div>
        </div>
        {promptError && <p className="privacy-warning">{promptError}</p>}
        <details className="prompt-rules">
          <summary>固定数据边界规则（不可编辑）</summary>
          <pre>{promptInfo.mandatory_rules}</pre>
        </details>
      </> : <p className="muted">{promptError ?? '正在读取翻译提示词…'}</p>}
    </section>
    </div>
  </div>
}
