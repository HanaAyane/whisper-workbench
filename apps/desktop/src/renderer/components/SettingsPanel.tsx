import { useEffect, useState } from 'react'
import { FolderOpen, RefreshCw } from 'lucide-react'
import type {
  ComputeType, DeepSeekModel, DeepSeekSettings, DeepSeekSettingsInput, DeepSeekThinking,
  Device, ModelCatalog, TranslationPrompt,
} from '../../shared/api'
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
  const [deepseek, setDeepseek] = useState<DeepSeekSettings | null>(null)
  const [keyDraft, setKeyDraft] = useState('')
  const [modelDraft, setModelDraft] = useState('')
  const [thinkingDraft, setThinkingDraft] = useState<DeepSeekThinking>('disabled')
  const [deepseekModels, setDeepseekModels] = useState<DeepSeekModel[]>([])
  const [deepseekState, setDeepseekState] = useState<'idle' | 'saving' | 'saved'>('idle')
  const [deepseekError, setDeepseekError] = useState<string | null>(null)
  const discovery = catalog?.source === 'discovery'
  const hints = catalog?.hints
  const modelDirectory = catalog?.model_directory ?? (catalog ? catalog.manifest_path.replace(/[\\/][^\\/]+$/, '') : undefined)
  const sep = hints?.model_directory.includes('\\') ? '\\' : '/'
  const modelOptions = [...new Set([
    ...deepseekModels.map((item) => item.id),
    modelDraft,
    deepseek?.env.model,
    'deepseek-flash',
    'deepseek-v4-pro',
  ].filter((item): item is string => Boolean(item)))]

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
    window.api.deepSeekSettings()
      .then((info) => {
        setDeepseek(info)
        setModelDraft(info.model)
        setThinkingDraft(info.thinking)
        if (info.api_key_saved || info.env.api_key_configured) void refreshDeepSeekModels()
      })
      .catch((error: unknown) => setDeepseekError(errorText(error)))
  }, [])

  useEffect(() => {
    window.api.translationPrompt()
      .then((info) => {
        setPromptInfo(info)
        setDraft(info.saved || info.default_prompt)
      })
      .catch((error: unknown) => setPromptError(errorText(error)))
  }, [])

  async function refreshDeepSeekModels() {
    try {
      const info = await window.api.deepSeekModels()
      setDeepseek(info)
      setDeepseekModels(info.models)
      setDeepseekError(null)
    } catch (error) {
      setDeepseekError(errorText(error))
    }
  }

  async function saveDeepSeek(input: DeepSeekSettingsInput) {
    setDeepseekState('saving')
    setDeepseekError(null)
    try {
      const info = await window.api.saveDeepSeekSettings(input)
      setDeepseek(info)
      setKeyDraft('')
      setModelDraft(info.model)
      setThinkingDraft(info.thinking)
      setDeepseekState('saved')
      if (info.api_key_saved || info.env.api_key_configured) void refreshDeepSeekModels()
    } catch (error) {
      setDeepseekError(errorText(error))
      setDeepseekState('idle')
    }
  }

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
    <section className="settings-card wide-card">
      <div className="pane-heading"><h2>DeepSeek 服务</h2><p>仅翻译模式使用</p></div>
      <div className="setting-line">
        <div>
          <strong>API Key 状态</strong>
          <p>{deepseek
            ? deepseek.api_key_saved
              ? `已保存 ${deepseek.api_key_hint}`
              : deepseek.env.api_key_configured
                ? '使用 .env / 环境变量里的 Key'
                : '未配置：翻译任务需要先填写 Key'
            : deepseekError ?? '正在读取…'}</p>
          <p>基础地址 {deepseek?.env.base_url ?? '—'}</p>
          {deepseek?.api_key_broken && <p className="privacy-warning">已保存的 Key 无法用当前系统账户解密，请重新填写。</p>}
        </div>
      </div>
      <label>API Key
        <input
          type="password"
          value={keyDraft}
          autoComplete="off"
          spellCheck={false}
          placeholder={deepseek?.api_key_saved ? '输入新 Key 以替换已保存的 Key' : 'sk-…'}
          onChange={(event) => {
            setKeyDraft(event.target.value)
            setDeepseekState('idle')
          }}
        />
      </label>
      <div className="button-row">
        <button type="button" disabled={deepseekState === 'saving' || !keyDraft.trim()} onClick={() => void saveDeepSeek({ api_key: keyDraft })}>保存 Key</button>
        <button type="button" disabled={deepseekState === 'saving' || !deepseek?.api_key_saved} onClick={() => void saveDeepSeek({ api_key: null })}>清除已存 Key</button>
      </div>
      <div className="form-grid">
        <label>模型
          <select value={modelDraft} onChange={(event) => { setModelDraft(event.target.value); setDeepseekState('idle') }}>
            {modelOptions.map((id) => <option key={id} value={id}>{id}</option>)}
          </select>
        </label>
        <label>思考强度
          <select value={thinkingDraft} onChange={(event) => { setThinkingDraft(event.target.value as DeepSeekThinking); setDeepseekState('idle') }}>
            <option value="disabled">关闭（推荐，输出更稳定）</option>
            <option value="low">低</option>
            <option value="high">高</option>
            <option value="max">最高</option>
          </select>
        </label>
      </div>
      <div className="button-row">
        <button type="button" disabled={deepseekState === 'saving'} onClick={() => void refreshDeepSeekModels()}>刷新模型列表</button>
        <button type="button" disabled={deepseekState === 'saving'} onClick={() => void saveDeepSeek({ model: null, thinking: null })}>恢复默认</button>
        <button type="button" disabled={deepseekState === 'saving'} onClick={() => void saveDeepSeek({ model: modelDraft, thinking: thinkingDraft })}>
          {deepseekState === 'saving' ? '正在保存' : deepseekState === 'saved' ? '已保存' : '保存模型设置'}
        </button>
      </div>
      {deepseekModels.length > 0 && <p className="muted">可用模型：{deepseekModels.map((item) => item.name ? `${item.id}（${item.name}）` : item.id).join('、')}</p>}
      {deepseekError && <p className="privacy-warning">{deepseekError}</p>}
      <p className="muted">Key 由系统安全存储（Windows DPAPI / macOS Keychain）加密后保存，磁盘上只有密文。</p>
      <p className="muted">打开思考后按 reasoning_effort 发送，temperature 不再生效；翻译默认关闭以保持 JSON 输出稳定。</p>
    </section>
    <section className="settings-card wide-card">
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
