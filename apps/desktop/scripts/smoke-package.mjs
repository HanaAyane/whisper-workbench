import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdir, mkdtemp, readFile, rm, writeFile } from 'node:fs/promises'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { _electron } from 'playwright'

const root = fileURLToPath(new URL('../../../', import.meta.url))
const executable = resolve(process.argv.slice(2).find((arg) => !arg.startsWith('--'))
  ?? join(root, 'apps/desktop/release/win-unpacked/Whisper工作台.exe'))
const evidence = process.argv.includes('--screenshots') ? join(root, 'docs/images') : null
const scratch = join(root, 'data/desktop-smoke')
await mkdir(scratch, { recursive: true })
const run = await mkdtemp(join(scratch, 'packaged-'))
const profile = join(run, 'profile')
const modelDirectory = process.env.JP_WORKBENCH_PACKAGE_SMOKE_MODELS || join(run, 'external-models')
const audio = process.env.JP_WORKBENCH_PACKAGE_SMOKE_AUDIO
const env = { ...process.env, JP_WORKBENCH_PYTHON: join(run, 'missing-python.exe') }
// ELECTRON_RUN_AS_NODE 会让 Electron 以 Node 模式启动，导致打包版无法出现窗口。
for (const key of ['JP_WORKBENCH_ROOT', 'JP_WORKBENCH_MODELS_DIR', 'JP_WORKBENCH_MANIFEST',
  'JP_WORKBENCH_GLOSSARY_DIR', 'JP_WORKBENCH_TEMP_DIR', 'JP_WORKBENCH_USER_DATA',
  'ELECTRON_RUN_AS_NODE']) delete env[key]
const launch = () => _electron.launch({ executablePath: executable, args: [`--user-data-dir=${profile}`], env })
let app
let completed
try {
  if (!process.env.JP_WORKBENCH_PACKAGE_SMOKE_MODELS) {
    await mkdir(modelDirectory, { recursive: true })
    await writeFile(join(modelDirectory, 'manifest.json'), await readFile(join(root, 'examples/manifest.packaged.json')))
  }
  app = await launch()
  const page = await app.firstWindow()
  await page.getByText('本地服务就绪', { exact: true }).waitFor()
  assert.deepEqual(await app.evaluate(({ app }) => ({ name: app.getName(), packaged: app.isPackaged })), {
    name: 'Whisper工作台', packaged: true,
  })
  assert.equal(await page.title(), 'Whisper工作台')
  await page.getByText(/未找到可用的日语转录模型/).waitFor()
  await capture(page, 'first-launch.png')
  const manifest = JSON.parse(await readFile(join(profile, 'models', 'manifest.json'), 'utf8'))
  assert.equal(manifest.models[0].id, 'whisper-ja-1.5B')
  await app.evaluate(({ shell }) => {
    globalThis.openedModelPath = new Promise((done) => {
      shell.openPath = async (path) => { done(path); return '' }
    })
  })
  await page.getByRole('button', { name: '打开模型目录', exact: true }).click()
  assert.equal(await app.evaluate(() => globalThis.openedModelPath), join(profile, 'models'))

  await page.getByRole('button', { name: '设置', exact: true }).click()
  await page.getByText('模型清单', { exact: true }).waitFor()
  await capture(page, 'model-settings.png', [
    page.getByText(join(profile, 'models', 'manifest.json'), { exact: true }),
    page.getByText(join(profile, 'models', 'whisper-ja-1.5B'), { exact: true }),
  ])
  await app.evaluate(({ dialog }, path) => {
    dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [path] })
  }, modelDirectory)
  await page.getByRole('button', { name: '选择目录', exact: true }).first().click()
  await page.getByText(join(modelDirectory, 'manifest.json'), { exact: true }).waitFor()

  await page.getByRole('button', { name: '术语表', exact: true }).click()
  await page.getByLabel('词表 ID', { exact: true }).fill('demo')
  await page.getByLabel('导入词表文件').setInputFiles(join(root, 'examples/glossary.demo.json'))
  await page.getByText(/已导入 \d+ 条词条/).waitFor()
  await page.getByRole('button', { name: '关闭消息' }).click()
  await page.getByLabel('待检查文本').fill('田中さんと渋谷で会いました')
  await page.getByRole('button', { name: '预览匹配' }).click()
  await page.locator('.preview-result mark').first().waitFor()
  await capture(page, 'glossary-preview.png')
  console.log('通过：打包版启动、首启模型提示、打开模型目录 IPC、模型选择及词表预览。')

  if (audio) {
    const clip = join(run, 'clip.wav')
    execFileSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-i', audio, '-t', '30',
      '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', clip], { stdio: 'pipe', windowsHide: true })
    await app.evaluate(({ dialog }, path) => {
      dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [path] })
    }, clip)
    await page.getByRole('button', { name: '工作台', exact: true }).click()
    await page.getByRole('button', { name: /拖入文件，或点击选择/ }).click()
    await page.getByRole('button', { name: '开始处理', exact: true }).click()
    const deadline = Date.now() + 120000
    while (Date.now() < deadline) {
      const [job] = await page.evaluate(() => window.api.listJobs())
      if (job?.state === 'failed') throw new Error(job.error)
      if (job?.state === 'succeeded') { completed = job; break }
      await new Promise((done) => setTimeout(done, 300))
    }
    assert.ok(completed?.segments.length, '冻结的 sidecar 应返回非空字幕')
    await page.waitForFunction(() => document.querySelector('.job-row.selected')?.textContent.includes('已完成'))
    const output = join(run, 'clip.srt')
    await app.evaluate(({ dialog }, path) => {
      dialog.showSaveDialog = async () => ({ canceled: false, filePath: path })
    }, output)
    await page.getByRole('button', { name: '选择位置并保存' }).click()
    await page.getByText(/字幕已保存至/).waitFor()
    assert.match(await readFile(output, 'utf8'), /\d\d:\d\d:\d\d,\d{3} --> /)
    console.log(`通过：打包版执行 30 秒本地 ASR，生成 ${completed.segments.length} 段并保存 SRT。`)
  }

  await app.close()
  app = await launch()
  const reopened = await app.firstWindow()
  await reopened.getByText('本地服务就绪', { exact: true }).waitFor()
  const state = await reopened.evaluate(async () => ({
    catalog: await window.api.models(), jobs: await window.api.listJobs(),
  }))
  assert.equal(state.catalog.manifest_path, join(modelDirectory, 'manifest.json'))
  if (completed) assert.equal(state.jobs[0].id, completed.id)
  console.log('通过：应用重启后保留模型目录与历史。')
} finally {
  if (app) await app.close()
  const name = relative(scratch, run)
  if (dirname(run) === scratch && name.startsWith('packaged-') && !name.includes(sep)) {
    await rm(run, { recursive: true, force: true, maxRetries: 4, retryDelay: 300 })
  }
}

async function capture(page, name, mask = []) {
  if (!evidence) return
  await mkdir(evidence, { recursive: true })
  await page.screenshot({ path: join(evidence, name), animations: 'disabled', mask, maskColor: '#a6afc5' })
}
