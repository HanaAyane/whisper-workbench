import { useState } from 'react'
import { Cpu, FolderOpen, HardDrive, ShieldCheck } from 'lucide-react'
import type { ComputeType, Device, ModelCatalog } from '../../shared/api'
import { errorText } from '../format'
import { useWorkbench } from '../store'

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

  async function changeOutputDirectory() {
    try {
      const directory = await window.api.pickOutputDirectory()
      if (directory) setOutputDir(directory)
    } catch (error) {
      onError(errorText(error))
    }
  }

  return <div className="settings-grid">
    <section className="solid settings-card">
      <div className="panel-heading"><div className="icon-tile"><HardDrive size={20} /></div><div><h2>模型与文件</h2><p>本机目录</p></div></div>
      <div className="setting-line">
        <div><strong>模型清单</strong><p>{catalog?.manifest_path ?? '尚未连接本地服务'}</p></div>
        <div className="button-row">
          <button disabled={busy || !catalog} onClick={() => void window.api.openModelDirectory().catch((error) => onError(errorText(error)))}><FolderOpen size={16} /> 打开模型目录</button>
          <button disabled={busy} onClick={() => void changeModelDirectory()}>{busy ? '正在切换' : '选择目录'}</button>
        </div>
      </div>
      {catalog?.errors.map((error) => <p className="privacy-warning" key={error}>{error}</p>)}
      {catalog?.models.map((model) => <div className="setting-line" key={model.id}>
        <div><strong>{model.label}</strong><p>{model.path}</p>{!model.ok && <p>缺少 {model.files.filter((file) => !file.ok).length} 个模型文件</p>}</div>
        <span className="label-pill">{model.ok ? '可用' : '缺失'}</span>
      </div>)}
      {catalog?.vad && <p className="muted">语音检测 · {catalog.vad.ok ? '本地 ONNX' : '使用能量检测'}</p>}
      <div className="setting-line">
        <div><strong>默认导出目录</strong><p>{outputDir ?? '由保存对话框选择'}</p></div>
        <button onClick={() => void changeOutputDirectory()}><FolderOpen size={16} /> 选择目录</button>
      </div>
    </section>
    <section className="solid settings-card">
      <div className="panel-heading"><div className="icon-tile"><Cpu size={20} /></div><div><h2>推理配置</h2><p>应用于新任务</p></div></div>
      <div className="form-grid">
        <label>推理设备<select value={device ?? ''} onChange={(event) => setDevice(event.target.value as Device || null)}>
          <option value="">服务默认</option><option value="auto">自动</option><option value="cpu">CPU</option><option value="cuda">CUDA</option>
        </select></label>
        <label>计算类型<select value={computeType ?? ''} onChange={(event) => setComputeType(event.target.value as ComputeType || null)}>
          <option value="">模型默认</option>{['int8', 'int8_float16', 'float16', 'bfloat16'].map((type) => <option key={type}>{type}</option>)}
        </select></label>
      </div>
      <div className="privacy-box"><ShieldCheck size={20} /><div><strong>本地转录</strong>
        <p>音频始终留在本机。选择 DeepSeek 翻译时，待翻译字幕文本会发送到本机配置的 DeepSeek API（默认 api.deepseek.com）。API Key 由本地 .env 或环境变量提供。</p>
        <p>历史任务、原始字幕和已保存编辑存放在本机任务库。</p>
      </div></div>
    </section>
  </div>
}
