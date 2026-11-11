import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { copyFile, link, mkdir, mkdtemp, readFile, rm, rmdir, symlink } from 'node:fs/promises'
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
// 安装版按安装位置扫描 <exe 所在目录>/model。
const installDir = dirname(executable)
const modelDir = join(installDir, 'model')
// 可选：真实模型目录（内含 model.bin 等五个文件）与 VAD 目录，用目录联接注入，避免复制大文件。
const modelSource = process.env.JP_WORKBENCH_PACKAGE_SMOKE_MODEL
const vadSource = process.env.JP_WORKBENCH_PACKAGE_SMOKE_VAD
const audio = process.env.JP_WORKBENCH_PACKAGE_SMOKE_AUDIO
const env = { ...process.env, JP_WORKBENCH_PYTHON: join(run, 'missing-python.exe') }
// ELECTRON_RUN_AS_NODE 会让 Electron 以 Node 模式启动，导致打包版无法出现窗口。
// 同时清理模型相关环境变量，确保走安装目录 model/ 的自动发现而不是外部清单。
for (const key of ['JP_WORKBENCH_ROOT', 'JP_WORKBENCH_MODELS_DIR', 'JP_WORKBENCH_MANIFEST',
  'JP_WORKBENCH_MODELS_ROOT', 'JP_WORKBENCH_GLOSSARY_DIR', 'JP_WORKBENCH_TEMP_DIR',
  'JP_WORKBENCH_USER_DATA', 'ELECTRON_RUN_AS_NODE']) delete env[key]
const launch = () => _electron.launch({ executablePath: executable, args: [`--user-data-dir=${profile}`], env })
const links = []
let app
let completed
try {
  await mkdir(modelDir, { recursive: true })
  if (modelSource) {
    const link = join(modelDir, 'whisper-ja-1.5B')
    await rm(link, { recursive: false, force: true }).catch(() => {})
    await symlink(modelSource, link, 'junction')
    links.push({ path: link, dir: true })
  }
  if (vadSource) {
    for (const name of ['whisper_vad.onnx', 'whisper_vad_metadata.json']) {
      const dest = join(modelDir, name)
      await rm(dest, { force: true }).catch(() => {})
      // 文件符号链接在 Windows 需要特权；优先用同卷硬链接，否则复制。
      try {
        await link(join(vadSource, name), dest)
      } catch {
        await copyFile(join(vadSource, name), dest)
      }
      links.push({ path: dest, dir: false })
    }
  }

  app = await launch()
  const page = await app.firstWindow()
  await page.getByText('本地服务就绪', { exact: true }).waitFor()
  assert.deepEqual(await app.evaluate(({ app }) => ({ name: app.getName(), packaged: app.isPackaged })), {
    name: 'Whisper工作台', packaged: true,
  })
  assert.equal(await page.title(), 'Whisper工作台')
  const catalog = await page.evaluate(() => window.api.models())
  assert.equal(catalog.source, 'discovery')
  assert.equal(catalog.model_directory, modelDir)
  if (!modelSource) {
    await page.getByText(/未找到可用的日语转录模型/).waitFor()
    await capture(page, 'first-launch.png')
  } else {
    assert.equal(catalog.models[0]?.id, 'whisper-ja-1.5B')
    assert.equal(catalog.models[0]?.ok, true, '安装目录 model/ 中的完整模型应被识别为可用')
    assert.equal(catalog.vad?.ok, true, 'VAD 文件齐全时应识别本地 ONNX')
  }
  if (!modelSource) {
    await app.evaluate(({ shell }) => {
      globalThis.openedModelPath = new Promise((done) => {
        shell.openPath = async (path) => { done(path); return '' }
      })
    })
    await page.getByRole('button', { name: '打开模型目录', exact: true }).click()
    assert.equal(await app.evaluate(() => globalThis.openedModelPath), modelDir)
  }
  await page.getByRole('button', { name: '设置', exact: true }).click()
  await page.getByText('模型目录', { exact: true }).waitFor()
  await page.getByText(modelDir, { exact: true }).first().waitFor()
  await page.getByRole('button', { name: /重新扫描/ }).click()
  await capture(page, 'model-settings.png', [page.getByText(modelDir, { exact: true }).first()])
  console.log('通过：打包版启动、安装目录 model/ 自动发现、设置页显示模型目录、重新扫描。')

  await page.getByRole('button', { name: '术语表', exact: true }).click()
  await page.getByLabel('词表 ID', { exact: true }).fill('demo')
  await page.getByLabel('导入词表文件').setInputFiles(join(root, 'examples/glossary.demo.json'))
  await page.getByText(/已导入 \d+ 条词条/).waitFor()
  await page.getByRole('button', { name: '关闭消息' }).click()
  await page.getByLabel('待检查文本').fill('田中さんと渋谷で会いました')
  await page.getByRole('button', { name: '预览匹配' }).click()
  await page.locator('.preview-result mark').first().waitFor()
  await capture(page, 'glossary-preview.png')
  console.log('通过：打包版术语导入与预览。')

  if (audio && modelSource) {
    const clip = join(run, 'clip.wav')
    execFileSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-i', audio, '-t', '30',
      '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', clip], { stdio: 'pipe', windowsHide: true })
    const outputDir = join(run, 'subtitles')
    await mkdir(outputDir, { recursive: true })
    await app.evaluate(({ dialog }, files) => {
      dialog.showOpenDialog = async () => ({ canceled: false, filePaths: files })
    }, [clip])
    await app.evaluate(({ dialog }, dir) => {
      dialog.showOpenDialog = async () => ({ canceled: false, filePaths: [dir] })
    }, outputDir)
    await page.getByRole('button', { name: '工作台', exact: true }).click()
    await page.getByRole('button', { name: /拖入多个文件/ }).click()
    await page.getByRole('button', { name: '开始处理', exact: true }).click()
    const deadline = Date.now() + 180000
    while (Date.now() < deadline) {
      const [job] = await page.evaluate(() => window.api.listJobs())
      if (job?.state === 'failed') throw new Error(job.error)
      if (job?.state === 'succeeded') { completed = job; break }
      await new Promise((done) => setTimeout(done, 300))
    }
    assert.ok(completed?.segments.length, '冻结的 sidecar 应在安装目录模型上返回非空字幕')
    await page.waitForFunction(() => document.querySelector('.job-row.selected')?.textContent.includes('已完成'))
    const output = join(run, 'clip.srt')
    await app.evaluate(({ dialog }, path) => {
      dialog.showSaveDialog = async () => ({ canceled: false, filePath: path })
    }, output)
    await page.getByRole('button', { name: '选择位置并保存' }).click()
    await page.getByText(/字幕已保存至/).waitFor()
    assert.match(await readFile(output, 'utf8'), /\d\d:\d\d:\d\d,\d{3} --> /)
    console.log(`通过：打包版使用安装目录模型执行 30 秒本地 ASR，生成 ${completed.segments.length} 段并保存 SRT。`)
  }

  await app.close()
  app = await launch()
  const reopened = await app.firstWindow()
  await reopened.getByText('本地服务就绪', { exact: true }).waitFor()
  const state = await reopened.evaluate(async () => ({
    catalog: await window.api.models(), jobs: await window.api.listJobs(),
  }))
  assert.equal(state.catalog.source, 'discovery')
  assert.equal(state.catalog.model_directory, modelDir)
  if (completed) assert.equal(state.jobs[0].id, completed.id)
  console.log('通过：应用重启后仍从安装目录发现模型并保留历史。')
} finally {
  if (app) await app.close()
  // 只删除自己建立的联接，绝不跟随删除真实模型目录。
  for (const link of links.reverse()) {
    await (link.dir ? rmdir(link.path) : rm(link.path, { force: true })).catch(() => {})
  }
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
