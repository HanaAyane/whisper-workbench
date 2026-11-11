import { mkdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { app, BrowserWindow, ipcMain, session, type IpcMainInvokeEvent } from 'electron'
import { APP_NAME } from '../shared/api.js'
import type { Field, Glossary, GlossaryFormat } from '../shared/api.js'
import { Workbench } from './workbench.js'

const configuredPort = Number(process.env.JP_WORKBENCH_VITE_PORT)
const devPort = Number.isInteger(configuredPort) && configuredPort > 0 && configuredPort <= 65535 ? configuredPort : 5173
const DEV_URL = `http://127.0.0.1:${devPort}`
const dev = !app.isPackaged && process.env.JP_WORKBENCH_VITE === '1'
const smoke = !app.isPackaged && process.env.JP_WORKBENCH_SMOKE === '1'
app.setName(APP_NAME)
app.setAppUserModelId('io.github.hanaayane.whisperworkbench')
const profileOverride = (!app.isPackaged && process.env.JP_WORKBENCH_USER_DATA)
  || app.commandLine.getSwitchValue('user-data-dir')
// 保留开发版已经使用的内部目录，改名后仍可读取同一份本地历史。
const profile = profileOverride ? resolve(profileOverride) : join(app.getPath('appData'), 'jp-voice-workbench')
mkdirSync(profile, { recursive: true })
app.setPath('userData', profile)

const rendererDir = join(app.getAppPath(), 'dist')
const indexPath = join(rendererDir, 'index.html')
const rendererUrl = pathToFileURL(indexPath).href
const assetRoot = pathToFileURL(join(rendererDir, 'assets') + '/').href
const allowedPage = (url: string) => dev ? url === DEV_URL + '/' : url === rendererUrl
const root = app.isPackaged ? app.getPath('userData') : resolve(app.getAppPath(), '..', '..')
let window: BrowserWindow | null = null
const workbench = new Workbench(root, app.isPackaged, app.getPath('userData'), () => window)

function handle<Args extends unknown[], Result>(channel: string, run: (...args: Args) => Result) {
  ipcMain.handle(channel, (event: IpcMainInvokeEvent, ...args) => {
    const frame = event.senderFrame
    if (!window || event.sender !== window.webContents || !frame || frame.parent || !allowedPage(frame.url)) {
      throw new Error('未授权的工作台请求。')
    }
    return run(...args as Args)
  })
}

const request = async <T>(path: string, options?: { method?: string; body?: unknown; text?: boolean }) =>
  (await workbench.connect()).request<T>(path, options)

const glossaryPath = (id: string) => {
  if (typeof id !== 'string' || !/^[a-z0-9_-]{1,64}$/i.test(id)) throw new Error('词表 ID 格式无效。')
  return `/glossary/${id}`
}
const glossaryExport = (id: string, format: GlossaryFormat) => {
  if (format !== 'json' && format !== 'csv') throw new Error('词表格式无效。')
  return `${glossaryPath(id)}/export?format=${format}`
}

function installIpc() {
  handle('health', () => request('/health'))
  handle('models', () => request('/models'))
  handle('pick-audio', () => workbench.pickAudioFile())
  handle('pick-audio-files', () => workbench.pickAudioFiles())
  handle('register-audio', (path: string) => workbench.registerAudio(path))
  handle('register-audios', (paths: string[]) => workbench.registerAudios(paths))
  handle('create-job', workbench.createJob.bind(workbench))
  handle('list-jobs', () => workbench.listJobs())
  handle('cancel-job', workbench.cancelJob.bind(workbench))
  handle('update-segment', workbench.updateSegment.bind(workbench))
  handle('review-segment', workbench.reviewSegment.bind(workbench))
  handle('export-job', workbench.exportJob.bind(workbench))
  handle('export-job-dir', workbench.exportJobToDirectory.bind(workbench))
  handle('pick-model-directory', () => workbench.pickModelDirectory())
  handle('open-model-directory', () => workbench.openModelDirectory())
  handle('rescan-models', () => workbench.rescanModels())
  handle('pick-output-directory', () => workbench.pickOutputDirectory())
  handle('list-glossaries', async () => (await request<{ glossaries: Glossary[] }>('/glossary')).glossaries)
  handle('read-glossary', (id: string) => request(glossaryExport(id, 'json')))
  handle('save-glossary', (id: string, entries: unknown) => request(glossaryPath(id), { method: 'PUT', body: entries }))
  handle('delete-glossary', (id: string) => request(glossaryPath(id), { method: 'DELETE' }))
  handle('import-glossary', (id: string, format: GlossaryFormat, content: string) =>
    request('/glossary/import', { method: 'POST', body: { glossary_id: id, format, content } }))
  handle('export-glossary', async (id: string, format: GlossaryFormat) => {
    const content = await request<string>(glossaryExport(id, format), { text: true })
    return workbench.saveTextFile(`${id}.${format}`, content)
  })
  handle('preview-glossary', (id: string, field: Field, text: string) =>
    request('/glossary/preview', { method: 'POST', body: { glossary_id: id, field, text } }))
  handle('save-text-file', workbench.saveTextFile.bind(workbench))
  handle('translation-prompt', () => workbench.translationPrompt())
  handle('save-translation-prompt', (prompt: string) => workbench.saveTranslationPrompt(prompt))
}

function createWindow() {
  window = new BrowserWindow({
    width: 1320,
    height: 900,
    minWidth: 780,
    minHeight: 660,
    backgroundColor: '#e5eaf7',
    title: APP_NAME,
    show: !smoke,
    webPreferences: {
      preload: join(app.getAppPath(), 'dist-electron', 'preload', 'index.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      backgroundThrottling: !smoke,
    },
  })
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }))
  window.webContents.on('will-navigate', (event) => event.preventDefault())
  window.webContents.on('will-attach-webview', (event) => event.preventDefault())
  window.on('closed', () => { window = null })
  const loaded = dev ? window.loadURL(DEV_URL) : window.loadFile(indexPath)
  void loaded.catch(() => console.error('无法加载桌面界面，请检查前端构建或开发服务。'))
}

function restrictSession() {
  const local = session.defaultSession
  local.setPermissionCheckHandler((contents, permission, _origin, details) =>
    contents === window?.webContents && permission === 'media' && details.isMainFrame &&
    allowedPage(details.requestingUrl || contents.getURL()) && details.mediaType === 'audio')
  local.setPermissionRequestHandler((contents, permission, reply, details) => {
    reply(contents === window?.webContents && permission === 'media' && details.isMainFrame &&
      allowedPage(details.requestingUrl || contents.getURL()) &&
      'mediaTypes' in details && details.mediaTypes?.length === 1 && details.mediaTypes[0] === 'audio')
  })
  local.webRequest.onBeforeRequest((details, callback) => {
    const url = new URL(details.url)
    if (dev && (url.origin === DEV_URL || url.origin === DEV_URL.replace('http:', 'ws:'))) {
      callback({ cancel: false })
      return
    }
    const allowed = url.protocol === 'blob:' || url.protocol === 'data:' ||
      (!dev && url.protocol === 'file:' &&
        (url.href === rendererUrl || url.href.startsWith(assetRoot)))
    callback({ cancel: !allowed })
  })
}

if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  let stopped = false
  let stopping = false
  app.on('before-quit', (event) => {
    if (stopped) return
    event.preventDefault()
    if (stopping) return
    stopping = true
    void workbench.close().finally(() => { stopped = true; app.quit() })
  })
  app.on('second-instance', () => {
    if (window?.isMinimized()) window.restore()
    window?.focus()
  })
  app.on('window-all-closed', () => app.quit())
  void app.whenReady().then(async () => {
    await workbench.initialize(app.isPackaged && process.platform !== 'win32' ? join(process.resourcesPath, 'manifest.example.json') : undefined)
      .catch(() => console.warn('无法准备默认模型清单，请在设置中选择已有模型目录。'))
    if (stopping) return
    restrictSession()
    installIpc()
    createWindow()
  })
}
