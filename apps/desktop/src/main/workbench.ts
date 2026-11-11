import { randomUUID } from 'node:crypto'
import { constants } from 'node:fs'
import { copyFile, lstat, mkdir, open, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises'
import { basename, dirname, extname, isAbsolute, join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { dialog, shell, type BrowserWindow } from 'electron'
import { exportFormats, mediaExtensions } from '../shared/api.js'
import type {
  DesktopJob, ExportFormat, JobInput, JobOptions, MediaCheck, ModelCatalog, OverwritePolicy, SegmentEdit, SegmentReview,
  TranslationPrompt,
} from '../shared/api.js'
import { Sidecar, SidecarResponseError, type SidecarConnection } from './sidecar.js'
import { writeExportFile, writeSubtitleWithUniqueName } from './export-file.js'
import { readMediaInfo } from './media-info.js'
import { readTranslationPrompt, writeTranslationPrompt } from './translation-prompt.js'

const MAX_RECORDING_BYTES = 256 * 1024 * 1024
const TEMP_RECORDING = /^recording-[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\.webm$/
const active = (job: DesktopJob) => job.state === 'running' || job.state === 'queued'

async function mediaFacts(path: string, bytes: number) {
  const handle = await open(path, 'r').catch(() => null)
  if (!handle) return { bytes }
  try {
    const head = Buffer.alloc(128)
    await handle.read(head, 0, head.length, 0)
    return { bytes, ...readMediaInfo(head) }
  } catch {
    return { bytes }
  } finally {
    await handle.close()
  }
}
const jobPath = (id: string) => {
  if (typeof id !== 'string' || !/^[A-Za-z0-9_-]{1,128}$/.test(id)) throw new Error('任务 ID 无效。')
  return `/jobs/${id}`
}
const segmentPath = (jobId: string, id: number) => {
  if (!Number.isSafeInteger(id) || id < 0) throw new Error('字幕片段 ID 无效。')
  return `${jobPath(jobId)}/segments/${id}`
}

export class Workbench {
  readonly sidecar: Sidecar
  private readonly files = new Map<string, string>()
  private readonly watching = new Set<string>()
  private readonly recordingWrites = new Set<Promise<void>>()
  private readonly modelSelectionPath: string
  private readonly translationPromptPath: string
  private readonly modelRoot?: string
  private modelsDir?: string
  private outputDir?: string
  private systemPrompt = ''
  private promptDefaults?: { default_prompt: string; mandatory_rules: string; max_chars: number }
  private submissions = 0
  private switchingModelDirectory = false
  private closing = false

  constructor(
    root: string,
    packaged: boolean,
    private readonly dataDir: string,
    private readonly getWindow: () => BrowserWindow | null,
  ) {
    this.sidecar = new Sidecar(root, packaged, dataDir)
    this.modelSelectionPath = join(dataDir, 'model-directory.json')
    this.translationPromptPath = join(dataDir, 'translation-prompt.json')
    // Windows 安装版把模型放在 <安装目录>/model，应用按安装位置定位并自动扫描。
    this.modelRoot = packaged && process.platform === 'win32' ? join(dirname(process.execPath), 'model') : undefined
  }

  async initialize(modelTemplate?: string) {
    this.systemPrompt = await readTranslationPrompt(this.translationPromptPath)
    const saved: unknown = await readFile(this.modelSelectionPath, 'utf8')
      .then((content) => JSON.parse(content)).catch(() => null)
    if (typeof saved === 'string' && isAbsolute(saved)) this.modelsDir = saved
    if (this.modelRoot) {
      // 首次启动时确保 model/ 存在，便于用户直接放入模型文件。
      await mkdir(this.modelRoot, { recursive: true }).catch(() => {
        console.warn('无法创建安装目录下的 model 目录，请在设置中查看模型目录并检查权限。')
      })
      return
    }
    if (!modelTemplate) return
    // 非 Windows 平台沿用清单模板，保持既有打包行为。
    const directory = join(this.dataDir, 'models')
    await mkdir(directory, { recursive: true })
    try {
      await copyFile(modelTemplate, join(directory, 'manifest.json'), constants.COPYFILE_EXCL)
    } catch (error) {
      if (!(error instanceof Error && 'code' in error && error.code === 'EEXIST')) throw error
    }
  }

  connect() {
    if (this.closing) throw new Error('工作台正在关闭。')
    if (this.switchingModelDirectory) throw new Error('正在切换模型目录，请稍后重试。')
    return this.sidecar.connect(this.modelsDir, this.modelsDir ? undefined : this.modelRoot)
  }

  async registerAudio(path: string) {
    if (typeof path !== 'string' || !mediaExtensions.includes(extname(path).slice(1).toLowerCase())) {
      throw new Error('请选择支持的音频或视频格式。')
    }
    if (!(await stat(path).catch(() => null))?.isFile()) throw new Error('无法读取该媒体文件。')
    this.files.clear()
    const id = randomUUID()
    this.files.set(id, path)
    return { id, name: basename(path) }
  }

  /** 逐个校验批量导入的媒体真实路径；无效项也返回稳定 id 供界面展示原因。 */
  async registerAudios(paths: string[]): Promise<MediaCheck[]> {
    if (!Array.isArray(paths)) throw new Error('媒体文件列表无效。')
    const checks: MediaCheck[] = []
    for (const path of paths) {
      const id = randomUUID()
      const name = typeof path === 'string' && path ? basename(path) : '未知文件'
      if (typeof path !== 'string' || !path || !mediaExtensions.includes(extname(path).slice(1).toLowerCase())) {
        checks.push({ id, name, ok: false, error: '不支持的音频或视频格式。' })
        continue
      }
      const file = await stat(path).catch(() => null)
      if (!file?.isFile()) {
        checks.push({ id, name, ok: false, error: '无法读取该媒体文件。' })
        continue
      }
      this.files.set(id, path)
      checks.push({ id, name, ok: true, ...await mediaFacts(path, file.size) })
    }
    return checks
  }

  async pickAudioFile() {
    const result = await dialog.showOpenDialog(this.window(), {
      title: '选择音频或视频',
      properties: ['openFile'],
      filters: [{ name: '音频和视频', extensions: mediaExtensions }],
    })
    return result.canceled ? null : this.registerAudio(result.filePaths[0])
  }

  async pickAudioFiles() {
    const result = await dialog.showOpenDialog(this.window(), {
      title: '选择音频或视频（可多选）',
      properties: ['openFile', 'multiSelections'],
      filters: [{ name: '音频和视频', extensions: mediaExtensions }],
    })
    return result.canceled ? null : this.registerAudios(result.filePaths)
  }

  async pickModelDirectory() {
    const chosen = await this.pickDirectory('选择含 manifest.json 的模型目录', this.modelsDir)
    if (!chosen) return null
    if (!(await stat(join(chosen, 'manifest.json')).catch(() => null))?.isFile()) {
      throw new Error('所选目录中没有 manifest.json。')
    }
    if (this.switchingModelDirectory || this.submissions) {
      throw new Error('任务处理期间无法切换模型目录。')
    }
    this.switchingModelDirectory = true
    try {
      const previous = await this.sidecar.connect(this.modelsDir)
      if ((await previous.request<DesktopJob[]>('/jobs')).some(active)) {
        throw new Error('任务处理期间无法切换模型目录。')
      }
    } catch (error) {
      this.switchingModelDirectory = false
      throw error
    }
    try {
      await this.sidecar.stop()
      if (this.closing) throw new Error('工作台正在关闭。')
      const catalog = await (await this.sidecar.connect(chosen)).request<ModelCatalog>('/models')
      if (catalog.errors.length) throw new Error(catalog.errors[0])
      await writeExportFile(this.modelSelectionPath, JSON.stringify(chosen), true)
      this.modelsDir = chosen
      return catalog
    } catch (error) {
      await this.sidecar.stop()
      throw error
    } finally {
      this.switchingModelDirectory = false
    }
  }

  async openModelDirectory() {
    const catalog = await (await this.connect()).request<ModelCatalog>('/models')
    const directory = catalog.model_directory ?? dirname(catalog.manifest_path)
    await mkdir(directory, { recursive: true })
    const error = await shell.openPath(directory)
    if (error) throw new Error('无法打开模型目录，请在文件管理器中访问设置页显示的路径。')
  }

  /** 重新扫描安装目录 model/：后端按目录实时扫描，无需重启本地服务。 */
  async rescanModels() {
    return (await this.connect()).request<ModelCatalog>('/models')
  }

  async pickOutputDirectory() {
    const chosen = await this.pickDirectory('选择默认字幕导出目录', this.outputDir)
    if (chosen) this.outputDir = chosen
    return chosen
  }

  /** 设置页读取：已保存的自定义提示词 + 后端内置预设与固定规则。 */
  async translationPrompt(): Promise<TranslationPrompt> {
    const defaults = await (await this.connect()).request<{
      system_prompt: string
      mandatory_rules: string
      max_chars: number
    }>('/translation/prompt')
    this.promptDefaults = {
      default_prompt: defaults.system_prompt,
      mandatory_rules: defaults.mandatory_rules,
      max_chars: defaults.max_chars,
    }
    return { saved: this.systemPrompt, ...this.promptDefaults }
  }

  /** 设置页保存：空内容恢复内置预设，内容仅用于 DeepSeek 翻译模式。 */
  async saveTranslationPrompt(prompt: string): Promise<TranslationPrompt> {
    this.systemPrompt = await writeTranslationPrompt(this.translationPromptPath, prompt)
    // 默认值已加载过就不再依赖本地服务，避免服务刚断开时把“已写入”误报成保存失败。
    return this.promptDefaults
      ? { saved: this.systemPrompt, ...this.promptDefaults }
      : this.translationPrompt()
  }

  async createJob(input: JobInput, options: JobOptions) {
    if (this.switchingModelDirectory) throw new Error('正在切换模型目录，请稍后重试。')
    if (!options || !['transcribe', 'translate'].includes(options.mode)) throw new Error('任务模式无效。')
    this.submissions++
    let recording: string | undefined
    let connection: SidecarConnection | undefined
    try {
      connection = await this.connect()
      const id = randomUUID()
      const { path, keep } = await this.prepareAudio(input, id)
      if (input.kind === 'recording' && !keep) recording = path
      if (this.closing) throw new Error('工作台正在关闭。')
      const name = input.kind === 'recording' ? `麦克风录音 · ${new Date().toLocaleTimeString('zh-CN')}` : basename(path)
      const status = await connection.request<DesktopJob>('/jobs', {
        method: 'POST',
        body: {
          input_path: path,
          name,
          recording: input.kind === 'recording' ? (keep ? 'retained' : 'temporary') : null,
          asr_model_id: options.asr_model_id,
          mode: options.mode,
          glossary_id: options.glossary_id,
          device: options.device,
          compute_type: options.compute_type,
          ...(options.mode === 'translate' && this.systemPrompt
            ? { translation: { system_prompt: this.systemPrompt } }
            : {}),
        },
      })
      console.info('已提交本地媒体任务。')
      if (active(status)) void this.watchJob(status.id)
      return status
    } catch (error) {
      const rejected = error instanceof SidecarResponseError && error.status >= 400 && error.status < 500
      if (recording && (rejected || connection?.ended || this.closing)) {
        await this.removeRecording(recording)
      }
      throw error
    } finally {
      this.submissions--
    }
  }

  async listJobs() {
    const jobs = await (await this.connect()).request<DesktopJob[]>('/jobs')
    for (const job of jobs) {
      if (active(job)) void this.watchJob(job.id)
    }
    return jobs
  }

  async cancelJob(id: string) {
    const job = await (await this.connect()).request<DesktopJob>(`${jobPath(id)}/cancel`, { method: 'POST' })
    this.publish(job)
  }

  async updateSegment(id: string, segmentId: number, edit: SegmentEdit) {
    const job = await (await this.connect()).request<DesktopJob>(segmentPath(id, segmentId), {
      method: 'PATCH', body: edit,
    })
    this.publish(job)
  }

  async reviewSegment(id: string, segmentId: number, decision: SegmentReview) {
    const job = await (await this.connect()).request<DesktopJob>(`${segmentPath(id, segmentId)}/review`, {
      method: 'POST', body: decision,
    })
    this.publish(job)
  }

  async exportJob(id: string, format: ExportFormat, policy: OverwritePolicy) {
    if (!exportFormats.includes(format)) throw new Error('字幕格式无效。')
    if (policy !== 'preserve' && policy !== 'replace') throw new Error('覆盖策略无效。')
    const connection = await this.connect()
    const path = jobPath(id)
    const value = await connection.request<DesktopJob>(path)
    if (value.state !== 'succeeded') throw new Error('任务完成后才能导出字幕。')
    const name = value.name.replace(/\.[^./\\]+$/, '').replace(/[<>:"/\\|?*]/g, '-') || '字幕'
    const selected = await this.chooseSavePath(`${name}.${format}`, '选择字幕保存位置')
    if (!selected) return null
    const target = extname(selected) ? selected : `${selected}.${format}`
    if (extname(target).toLowerCase() !== `.${format}`) throw new Error('文件扩展名必须和所选字幕格式一致。')
    const content = await connection.request<string>(`${path}/export`, {
      method: 'POST', body: { format }, text: true,
    })
    try {
      await writeExportFile(target, content, policy === 'replace')
    } catch (error) {
      if (error instanceof Error && 'code' in error && error.code === 'EEXIST') {
        throw new Error('同名文件已存在。请换一个文件名，或选择允许覆盖。', { cause: error })
      }
      throw new Error('无法保存字幕，请检查目录权限或磁盘空间。', { cause: error })
    }
    return target
  }

  /**
   * 批量自动导出：读取已保存字幕，写入整批选定的输出目录。
   * 与单任务导出共用后端 writer 与 `writeExportFile`，同名时自动追加序号。
   */
  async exportJobToDirectory(id: string, format: ExportFormat, directory: string, baseName: string) {
    if (!exportFormats.includes(format)) throw new Error('字幕格式无效。')
    if (typeof directory !== 'string' || !isAbsolute(directory)) throw new Error('输出目录无效。')
    if (!(await stat(directory).catch(() => null))?.isDirectory()) throw new Error('输出目录不存在或无法访问。')
    const connection = await this.connect()
    const path = jobPath(id)
    const value = await connection.request<DesktopJob>(path)
    if (value.state !== 'succeeded') throw new Error('任务完成后才能导出字幕。')
    const content = await connection.request<string>(`${path}/export`, {
      method: 'POST', body: { format }, text: true,
    })
    try {
      return await writeSubtitleWithUniqueName(directory, typeof baseName === 'string' && baseName ? baseName : value.name, format, content)
    } catch (error) {
      throw new Error('无法写入字幕文件，请检查输出目录权限或磁盘空间。', { cause: error })
    }
  }

  async saveTextFile(name: string, content: string) {
    if (typeof name !== 'string' || basename(name) !== name || typeof content !== 'string') {
      throw new Error('文件名或内容无效。')
    }
    const extension = extname(name).slice(1)
    if (!['srt', 'vtt', 'lrc', 'txt', 'csv', 'json'].includes(extension)) {
      throw new Error('不支持保存这种文件。')
    }
    const target = await this.chooseSavePath(name, '保存本地文件')
    if (!target) return null
    await writeFile(target, content, 'utf8').catch(() => { throw new Error('无法写入所选文件，请检查目录权限。') })
    return target
  }

  private async chooseSavePath(name: string, title: string) {
    const extension = extname(name).slice(1)
    const result = await dialog.showSaveDialog(this.window(), {
      title,
      defaultPath: this.outputDir ? join(this.outputDir, name) : name,
      filters: [{ name: extension.toUpperCase(), extensions: [extension] }],
    })
    return result.canceled ? null : result.filePath
  }

  async close() {
    this.closing = true
    await this.sidecar.stop()
    await Promise.allSettled(this.recordingWrites)
    const folder = join(this.dataDir, 'tmp-recordings')
    if (!(await lstat(folder).catch(() => null))?.isDirectory()) return
    const files = await readdir(folder, { withFileTypes: true }).catch(() => [])
    await Promise.all(files
      .filter((file) => file.isFile() && TEMP_RECORDING.test(file.name))
      .map((file) => this.removeRecording(join(folder, file.name))))
  }

  private window() {
    const current = this.getWindow()
    if (!current || current.isDestroyed()) throw new Error('工作台窗口已关闭。')
    return current
  }

  private async pickDirectory(title: string, defaultPath?: string) {
    const result = await dialog.showOpenDialog(this.window(), { title, defaultPath, properties: ['openDirectory'] })
    return result.canceled ? null : result.filePaths[0]
  }

  private async prepareAudio(input: JobInput, id: string) {
    if (input?.kind === 'file') {
      const path = this.files.get(input.id)
      if (!path) throw new Error('请重新选择要处理的媒体文件。')
      return { path, keep: false }
    }
    if (input?.kind !== 'recording' || !(input.data instanceof ArrayBuffer) ||
      !input.data.byteLength || input.data.byteLength > MAX_RECORDING_BYTES || typeof input.keep !== 'boolean') {
      throw new Error('录音内容无效或超过 256 MB。')
    }
    const folder = join(this.dataDir, input.keep ? 'recordings' : 'tmp-recordings')
    await mkdir(folder, { recursive: true })
    if (this.closing) throw new Error('工作台正在关闭。')
    const path = join(folder, `recording-${id}.webm`)
    const writing = writeFile(path, Buffer.from(input.data), { flag: 'wx' })
    this.recordingWrites.add(writing)
    try {
      await writing
    } catch {
      if (!input.keep) await this.removeRecording(path)
      throw new Error('无法保存本地录音。')
    } finally {
      this.recordingWrites.delete(writing)
    }
    return { path, keep: input.keep }
  }

  private publish(value: DesktopJob) {
    const window = this.getWindow()
    if (window && !window.isDestroyed()) window.webContents.send('job-update', value)
  }

  private async watchJob(id: string) {
    if (this.watching.has(id)) return
    this.watching.add(id)
    try {
      const path = jobPath(id)
      let terminal = false
      const update = (job: DesktopJob) => {
        this.publish(job)
        terminal = !active(job)
      }
      while (!this.closing && !terminal) {
        try {
          const connection = await this.connect()
          await connection.streamJob(id, update)
          // 断线或握手失败时补一次快照，再重连推送。
          if (!terminal && !this.closing) update(await connection.request<DesktopJob>(path))
        } catch (error) {
          if (error instanceof SidecarResponseError && error.status === 404) return
        }
        if (!terminal && !this.closing) await delay(800)
      }
    } finally {
      this.watching.delete(id)
    }
  }

  private async removeRecording(path: string) {
    try {
      await rm(path, { force: true })
    } catch {
      console.warn('临时录音暂时无法清理，下次启动时重试。')
    }
  }
}
