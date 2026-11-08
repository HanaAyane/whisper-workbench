import { randomUUID } from 'node:crypto'
import { mkdir, rm, stat, writeFile } from 'node:fs/promises'
import { basename, extname, join } from 'node:path'
import { setTimeout as delay } from 'node:timers/promises'
import { dialog, type BrowserWindow } from 'electron'
import { exportFormats, mediaExtensions } from '../shared/api.js'
import type {
  DesktopJob, ExportFormat, JobInput, JobOptions, JobStatus, ModelCatalog, SegmentEdit,
} from '../shared/api.js'
import { Sidecar, SidecarResponseError, type SidecarConnection } from './sidecar.js'
import { formatSubtitles } from './subtitles.js'

const MAX_RECORDING_BYTES = 256 * 1024 * 1024
const active = (job: JobStatus) => job.state === 'running' || job.state === 'queued'

export class Workbench {
  readonly sidecar: Sidecar
  private readonly files = new Map<string, string>()
  private readonly jobs = new Map<string, { value: DesktopJob; backendId: string; connection: SidecarConnection }>()
  private readonly temporary = new Set<string>()
  private modelsDir?: string
  private outputDir?: string
  private submissions = 0
  private switchingModelDirectory = false
  private closing = false

  constructor(
    root: string,
    packaged: boolean,
    private readonly dataDir: string,
    private readonly getWindow: () => BrowserWindow | null,
  ) {
    this.sidecar = new Sidecar(root, packaged)
  }

  connect() {
    if (this.closing) throw new Error('工作台正在关闭。')
    if (this.switchingModelDirectory) throw new Error('正在切换模型目录，请稍后重试。')
    return this.sidecar.connect(this.modelsDir)
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

  async pickAudioFile() {
    const result = await dialog.showOpenDialog(this.window(), {
      title: '选择音频或视频',
      properties: ['openFile'],
      filters: [{ name: '音频和视频', extensions: mediaExtensions }],
    })
    return result.canceled ? null : this.registerAudio(result.filePaths[0])
  }

  async pickModelDirectory() {
    const chosen = await this.pickDirectory('选择含 manifest.json 的模型目录', this.modelsDir)
    if (!chosen) return null
    if (!(await stat(join(chosen, 'manifest.json')).catch(() => null))?.isFile()) {
      throw new Error('所选目录中没有 manifest.json。')
    }
    if (this.switchingModelDirectory || this.submissions || this.listJobs().some(active)) {
      throw new Error('任务处理期间无法切换模型目录。')
    }
    this.switchingModelDirectory = true
    try {
      await this.sidecar.stop()
      if (this.closing) throw new Error('工作台正在关闭。')
      const catalog = await (await this.sidecar.connect(chosen)).request<ModelCatalog>('/models')
      if (catalog.errors.length) throw new Error(catalog.errors[0])
      this.modelsDir = chosen
      return catalog
    } catch (error) {
      await this.sidecar.stop()
      throw error
    } finally {
      this.switchingModelDirectory = false
    }
  }

  async pickOutputDirectory() {
    const chosen = await this.pickDirectory('选择默认字幕导出目录', this.outputDir)
    if (chosen) this.outputDir = chosen
    return chosen
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
      const status = await connection.request<JobStatus>('/jobs', {
        method: 'POST',
        body: {
          input_path: path,
          asr_model_id: options.asr_model_id,
          mode: options.mode,
          glossary_id: options.glossary_id,
          device: options.device,
          compute_type: options.compute_type,
        },
      })
      const name = input.kind === 'recording' ? `麦克风录音 · ${new Date().toLocaleTimeString('zh-CN')}` : basename(path)
      const value: DesktopJob = { ...status, id, name, mode: options.mode, recordedPath: keep ? path : undefined }
      this.jobs.set(id, { value, backendId: status.id, connection })
      console.info('已提交本地媒体任务。')
      if (active(value)) void this.watchJob(id, recording)
      else if (recording) await this.removeRecording(recording)
      return value
    } catch (error) {
      if (recording && (error instanceof SidecarResponseError || connection?.ended || this.closing)) {
        await this.removeRecording(recording)
      }
      throw error
    } finally {
      this.submissions--
    }
  }

  listJobs() {
    return [...this.jobs.values()].map(({ value }) => value).reverse()
  }

  async cancelJob(id: string) {
    const { backendId, connection, value } = this.getJob(id)
    if (active(value)) await connection.request(`/jobs/${backendId}/cancel`, { method: 'POST' })
  }

  updateSegment(id: string, segmentId: number, edit: SegmentEdit) {
    const { value } = this.getJob(id)
    const segment = value.segments.find((item) => item.id === segmentId)
    if (value.state !== 'succeeded' || !segment) throw new Error('找不到可编辑的字幕片段。')
    if (!edit || typeof edit.text !== 'string' ||
      (segment.raw_translation === null ? edit.translation !== null : typeof edit.translation !== 'string')) {
      throw new Error('字幕内容无效。')
    }
    segment.text = edit.text
    segment.translation = edit.translation
    this.publish(value)
  }

  async exportJob(id: string, format: ExportFormat) {
    if (!exportFormats.includes(format)) throw new Error('字幕格式无效。')
    const { value } = this.getJob(id)
    if (value.state !== 'succeeded') throw new Error('任务完成后才能导出字幕。')
    const name = value.name.replace(/\.[^./\\]+$/, '').replace(/[<>:"/\\|?*]/g, '-')
    const content = formatSubtitles(value.segments, format)
    return this.saveTextFile(`${name}.${format}`, content)
  }

  async saveTextFile(name: string, content: string) {
    if (typeof name !== 'string' || basename(name) !== name || typeof content !== 'string') {
      throw new Error('文件名或内容无效。')
    }
    const extension = extname(name).slice(1)
    if (!['srt', 'vtt', 'lrc', 'txt', 'csv', 'json'].includes(extension)) {
      throw new Error('不支持保存这种文件。')
    }
    const result = await dialog.showSaveDialog(this.window(), {
      title: '保存本地文件',
      defaultPath: this.outputDir ? join(this.outputDir, name) : name,
      filters: [{ name: extension.toUpperCase(), extensions: [extension] }],
    })
    if (result.canceled || !result.filePath) return null
    const target = result.filePath
    await writeFile(target, content, 'utf8').catch(() => { throw new Error('无法写入所选文件，请检查目录权限。') })
    return target
  }

  async close() {
    this.closing = true
    await this.sidecar.stop()
    await Promise.all([...this.temporary].map((path) => this.removeRecording(path)))
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
    if (!input.keep) this.temporary.add(path)
    try {
      await writeFile(path, Buffer.from(input.data), { flag: 'wx' })
    } catch {
      if (!input.keep) await this.removeRecording(path)
      throw new Error('无法保存本地录音。')
    }
    return { path, keep: input.keep }
  }

  private getJob(id: string) {
    const job = this.jobs.get(id)
    if (!job) throw new Error('找不到当前会话中的任务。')
    return job
  }

  private publish(value: DesktopJob) {
    const window = this.getWindow()
    if (window && !window.isDestroyed()) window.webContents.send('job-update', value)
  }

  private async watchJob(id: string, recording?: string) {
    const job = this.getJob(id)
    while (!this.closing && active(job.value)) {
      await delay(450)
      if (this.closing) break
      try {
        const status = await job.connection.request<JobStatus>(`/jobs/${job.backendId}`)
        job.value = { ...job.value, ...status, id }
      } catch (error) {
        if (job.connection.ended || error instanceof SidecarResponseError) {
          job.value = { ...job.value, state: 'failed', message: '任务连接已结束', error: '请重新提交任务。' }
        } else {
          job.value = { ...job.value, message: '连接暂时中断，正在重新查询任务' }
        }
      }
      this.publish(job.value)
    }
    if (recording && !this.closing) await this.removeRecording(recording)
  }

  private async removeRecording(path: string) {
    try {
      await rm(path, { force: true })
      this.temporary.delete(path)
    } catch {
      console.warn('临时录音清理失败，将在关闭工作台时重试。')
    }
  }
}
