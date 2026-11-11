import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Download, Plus, Search, Trash2, Upload } from 'lucide-react'
import type { Entry, Field, Glossary, GlossaryFormat, Policy, Preview } from '../../shared/api'
import { errorText } from '../format'
import { Highlight, policyLabel } from './Highlight'

const emptyEntry = (): Entry => ({
  id: crypto.randomUUID(), source: '', variants: [], target: '', category: 'term',
  match_mode: 'exact', regex: null, priority: 100, field: 'text', policy: 'correct', enabled: true,
})

export function GlossaryPanel({ glossaries, onChange, onError, onSaved }: {
  glossaries: Glossary[]
  onChange(): Promise<void>
  onError(message: string): void
  onSaved(message: string): void
}) {
  const [selected, setSelected] = useState('')
  const [newId, setNewId] = useState('')
  const [entries, setEntries] = useState<Entry[]>([])
  const [draft, setDraft] = useState<Entry | null>(null)
  const [variants, setVariants] = useState('')
  const [text, setText] = useState('')
  const [field, setField] = useState<Field>('text')
  const [preview, setPreview] = useState<Preview | null>(null)
  const [busy, setBusy] = useState(false)
  const [loaded, setLoaded] = useState('')
  const fileInput = useRef<HTMLInputElement>(null)
  const current = glossaries.some((item) => item.id === selected) ? selected : glossaries[0]?.id ?? ''

  useEffect(() => {
    let stale = false
    setLoaded('')
    setDraft(null)
    setPreview(null)
    if (current) {
      void window.api.readGlossary(current).then((result) => {
        if (!stale) { setEntries(result); setLoaded(current) }
      }).catch((error) => { if (!stale) onError(errorText(error)) })
    }
    return () => { stale = true }
  }, [current, onError])

  async function run(action: () => Promise<void>) {
    setBusy(true)
    try { await action() } catch (error) { onError(errorText(error)) } finally { setBusy(false) }
  }

  function editEntry(entry: Entry) {
    setDraft(entry)
    setVariants(entry.variants.join(' | '))
  }

  async function updateEntries(next: Entry[]) {
    const result = await window.api.saveGlossary(current, next)
    setEntries(await window.api.readGlossary(current))
    setDraft(null)
    setPreview(null)
    await onChange()
    onSaved(result.warnings.join('；') || '词表已保存。')
  }

  function saveEntry(event: FormEvent) {
    event.preventDefault()
    if (!draft) return
    const next = { ...draft, variants: variants.split('|').map((variant) => variant.trim()).filter(Boolean) }
    void run(() => updateEntries(entries.some((entry) => entry.id === next.id)
      ? entries.map((entry) => entry.id === next.id ? next : entry)
      : [...entries, next]))
  }

  async function createGlossary() {
    const id = newId.trim()
    if (!/^[a-z0-9_-]{1,64}$/i.test(id)) throw new Error('词表 ID 只能包含字母、数字、下划线和连字符。')
    if (glossaries.some((item) => item.id.toLowerCase() === id.toLowerCase())) throw new Error('该词表 ID 已存在。')
    await window.api.saveGlossary(id, [])
    await onChange()
    setSelected(id)
    setNewId('')
    onSaved('已创建词表。')
  }

  async function importGlossary(file: File) {
    const format = file.name.split('.').pop()?.toLowerCase()
    if (format !== 'csv' && format !== 'json') throw new Error('请选择 CSV 或 JSON 词表。')
    if (file.size > 5 * 1024 * 1024) throw new Error('词表文件超过 5 MB。')
    const id = newId.trim() || file.name.slice(0, -format.length - 1)
    if (!/^[a-z0-9_-]{1,64}$/i.test(id)) throw new Error('请先填写一个合法的词表 ID。')
    const existing = glossaries.find((item) => item.id.toLowerCase() === id.toLowerCase())
    if (existing && !window.confirm(`用导入内容覆盖「${existing.id}」？`)) return
    const target = existing?.id ?? id
    let content: string
    try { content = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer()) }
    catch { throw new Error('词表文件需要使用 UTF-8 编码。') }
    const result = await window.api.importGlossary(target, format, content)
    if (target === current) {
      setEntries(await window.api.readGlossary(target))
      setDraft(null)
      setPreview(null)
    }
    await onChange()
    setSelected(target)
    setNewId('')
    onSaved(`已导入 ${result.entry_count} 条词条。${result.warnings.join('；')}`)
  }

  async function exportGlossary(format: GlossaryFormat) {
    const path = await window.api.exportGlossary(current, format)
    if (path) onSaved(`词表已保存至 ${path}`)
  }

  return <div className="glossary-page">
    <header className="pane-heading"><h1>术语表</h1><p>维护常见误识别、专有名词和统一译名。</p></header>
    <div className="glossary-grid">
    <section className="glossary-library">
      <div className="pane-heading"><h2>词表管理</h2><p>精确匹配 · 别名与译名</p></div>
      <div className="glossary-create">
        <label>词表 ID<input value={newId} disabled={busy} onChange={(event) => setNewId(event.target.value)} placeholder="例如 demo" maxLength={64} /></label>
        <button aria-label="新建词表" onClick={() => void run(createGlossary)} disabled={busy || !newId.trim()}><Plus size={16} /> 新建</button>
        <button onClick={() => fileInput.current?.click()} disabled={busy}><Upload size={16} /> 导入 CSV / JSON</button>
        <input hidden ref={fileInput} type="file" aria-label="导入词表文件" accept=".csv,.json" onChange={(event) => {
          const file = event.target.files?.[0]
          event.target.value = ''
          if (file) void run(() => importGlossary(file))
        }} />
      </div>
      {current ? <>
        <div className="glossary-select">
          <label>当前词表<select value={current} disabled={busy} onChange={(event) => setSelected(event.target.value)}>
            {glossaries.map((item) => <option value={item.id} key={item.id}>{item.name}（{item.entry_count} 条）</option>)}
          </select></label>
          <button disabled={busy} onClick={() => void run(() => exportGlossary('csv'))}><Download size={15} /> CSV</button>
          <button disabled={busy} onClick={() => void run(() => exportGlossary('json'))}><Download size={15} /> JSON</button>
          <button className="icon-button danger" aria-label="删除词表" disabled={busy} onClick={() => {
            if (!window.confirm(`删除本地词表「${current}」？`)) return
            void run(async () => { await window.api.deleteGlossary(current); setSelected(''); await onChange(); onSaved('词表已删除。') })
          }}><Trash2 size={16} /></button>
        </div>
        <div className="section-heading"><h3>词条</h3><button disabled={busy || loaded !== current} onClick={() => editEntry(emptyEntry())}><Plus size={15} /> 添加词条</button></div>
        {loaded === current && entries.length > 0 ? <ul className="entries">{entries.map((entry) =>
          <li key={entry.id}>
            <button className="entry-button" disabled={busy} onClick={() => editEntry(entry)}>
              <strong>{entry.source}</strong><span>{entry.target || '仅高亮'}</span><small>{policyLabel[entry.policy]}{entry.enabled ? '' : ' · 已停用'}</small>
            </button>
            <button className="icon-button danger" aria-label={`删除词条 ${entry.source}`} disabled={busy} onClick={() => {
              if (window.confirm(`删除词条「${entry.source}」？`)) void run(() => updateEntries(entries.filter((item) => item.id !== entry.id)))
            }}><Trash2 size={15} /></button>
          </li>,
        )}</ul> : <p className="muted">{loaded === current ? '这个词表还没有词条。' : '正在读取词条…'}</p>}
        {draft && <form className="entry-form" onSubmit={saveEntry}>
          <div className="form-grid">
            <label>匹配词<input required value={draft.source} onChange={(event) => setDraft({ ...draft, source: event.target.value })} /></label>
            <label>替换为<input required={draft.policy !== 'keep'} value={draft.target} onChange={(event) => setDraft({ ...draft, target: event.target.value })} /></label>
            <label>别名（用 | 分隔）<input value={variants} onChange={(event) => setVariants(event.target.value)} /></label>
            <label>策略<select value={draft.policy} onChange={(event) => {
              const policy = event.target.value as Policy
              setDraft({ ...draft, policy, field: policy === 'translate' ? 'translation' : policy === 'correct' ? 'text' : draft.field })
            }}>{Object.entries(policyLabel).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>
            <label>作用字段<select value={draft.field} disabled={draft.policy !== 'keep'} onChange={(event) => setDraft({ ...draft, field: event.target.value as Field })}>
              <option value="text">日语原文</option><option value="translation">中文译文</option>
            </select></label>
            <label>优先级<input type="number" required value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: Number(event.target.value) })} /></label>
          </div>
          <div className="entry-actions">
            <label className="inline"><input type="checkbox" checked={draft.enabled} onChange={(event) => setDraft({ ...draft, enabled: event.target.checked })} />启用词条</label>
            <div className="button-row"><button type="button" onClick={() => setDraft(null)} disabled={busy}>取消</button><button className="primary" disabled={busy}>保存词条</button></div>
          </div>
        </form>}
      </> : <p className="muted">新建词表，或导入本地 CSV / JSON 文件。</p>}
    </section>
    <section className="glossary-preview">
      <div className="pane-heading"><h2>匹配预览</h2><p>检查命中与替换结果</p></div>
      <label>作用字段<select value={field} disabled={busy} onChange={(event) => { setField(event.target.value as Field); setPreview(null) }}>
        <option value="text">日语原文</option><option value="translation">中文译文</option>
      </select></label>
      <label>待检查文本<textarea value={text} disabled={busy} onChange={(event) => { setText(event.target.value); setPreview(null) }} rows={5} placeholder="输入要检查的字幕片段" /></label>
      <button className="primary" disabled={busy || !current || !text.trim()} onClick={() => void run(async () =>
        setPreview(await window.api.previewGlossary(current, field, text)),
      )}><Search size={16} /> 预览匹配</button>
      {preview && <div className="preview-result">
        <h3>命中 {preview.hits.length} 条</h3>
        <p><Highlight text={preview.text} hits={preview.hits} /></p>
        <h3>替换预览</h3><p>{preview.replaced_text}</p>
      </div>}
    </section>
    </div>
  </div>
}
