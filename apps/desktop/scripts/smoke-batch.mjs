import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import electron from 'electron'
import { _electron } from 'playwright'

const dir = fileURLToPath(new URL('../', import.meta.url))
const root = resolve(dir, '..', '..')
const output = join(root, 'data', 'desktop-smoke')
await mkdir(output, { recursive: true })
const run = await mkdtemp(join(output, 'batch-'))
const mediaA = join(run, 'a')
const mediaB = join(run, 'b')
const subtitles = join(run, 'subtitles')
const userData = join(run, 'profile')
await Promise.all([
  mkdir(mediaA, { recursive: true }), mkdir(mediaB, { recursive: true }), mkdir(subtitles, { recursive: true }),
])
// 两份主文件名相同（clip）的有效媒体 + 一份损坏文件。
const clips = [join(mediaA, 'clip.wav'), join(mediaB, 'clip.wav')]
for (const clip of clips) {
  execFileSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
    'anullsrc=r=16000:cl=mono', '-t', '1', '-c:a', 'pcm_s16le', clip], { stdio: 'pipe', windowsHide: true })
}
const broken = join(mediaA, 'broken.wav')
await writeFile(broken, Buffer.from('这不是有效的音频数据'))
// 预先放一份同名 SRT，验证批量导出保护已有文件并追加序号。
await writeFile(join(subtitles, 'clip.srt'), '残留字幕', 'utf8')
const files = [...clips, broken]
const env = {
  ...process.env, JP_WORKBENCH_SMOKE: '1', JP_WORKBENCH_VITE: '0',
  JP_WORKBENCH_USER_DATA: userData, JP_WORKBENCH_GLOSSARY_DIR: join(run, 'glossary'),
}
delete env.ELECTRON_RUN_AS_NODE
const launch = () => _electron.launch({ executablePath: electron, args: ['.', '--use-fake-device-for-media-stream'], cwd: dir, env })
let app
try {
  app = await launch()
  const page = await app.firstWindow()
  await page.getByText('本地服务就绪', { exact: true }).waitFor()
  await app.evaluate(({ dialog }, { files: list, dir: directory }) => {
    dialog.showOpenDialog = async (_win, options) => {
      const properties = options?.properties || []
      if (properties.includes('openDirectory')) return { canceled: false, filePaths: [directory] }
      return { canceled: false, filePaths: list }
    }
  }, { files, dir: subtitles })

  await page.getByRole('button', { name: '工作台', exact: true }).click()

  async function importFiles() {
    await page.getByRole('button', { name: /拖入多个文件/ }).click()
    await page.waitForFunction(() => document.querySelectorAll('.batch-row').length === 3)
  }
  async function waitTerminal(minJobs) {
    const deadline = Date.now() + 120000
    while (Date.now() < deadline) {
      const jobs = await page.evaluate(() => window.api.listJobs())
      if (jobs.length >= minJobs && jobs.every((job) => ['succeeded', 'failed', 'cancelled'].includes(job.state))) return jobs
      await new Promise((done) => setTimeout(done, 250))
    }
    throw new Error('批量任务未在超时内结束')
  }

  // 第一批：SRT，包含两份同名有效媒体和一份损坏文件。
  await importFiles()
  await page.locator('.capture-form .button-row button').click()
  await page.getByRole('button', { name: /开始批量处理/ }).click()
  const firstJobs = await waitTerminal(3)
  assert.equal(firstJobs.filter((job) => job.state === 'succeeded').length, 2)
  assert.equal(firstJobs.filter((job) => job.state === 'failed').length, 1)
  await page.waitForFunction(() => document.querySelectorAll('.batch-status.success').length >= 2, undefined, { timeout: 30000 })
  assert.equal(await readFile(join(subtitles, 'clip.srt'), 'utf8'), '残留字幕', '已有同名文件必须保持原样')
  const afterFirst = (await readdir(subtitles)).sort()
  assert.deepEqual(afterFirst, ['clip (1).srt', 'clip (2).srt', 'clip.srt'])
  assert.ok(!(await readdir(subtitles)).some((name) => name.startsWith('broken')), '损坏文件不应产生字幕')
  console.log('通过：批量导入两份同名有效媒体与一份损坏文件，按序转录；成功 2 / 失败 1，同名 SRT 追加序号且保护原文件。')

  // 第二批：VTT，验证格式切换与扩展名一致。
  await page.getByRole('button', { name: '清空列表', exact: true }).click()
  await importFiles()
  await page.getByLabel('批量输出格式').selectOption('vtt')
  await page.locator('.capture-form .button-row button').click()
  await page.getByRole('button', { name: /开始批量处理/ }).click()
  await waitTerminal(6)
  await page.waitForFunction(() => document.querySelectorAll('.batch-status.success').length >= 2, undefined, { timeout: 30000 })
  const afterSecond = (await readdir(subtitles)).sort()
  assert.ok(afterSecond.includes('clip.vtt') && afterSecond.includes('clip (1).vtt'), 'VTT 批次应按主文件名与 .vtt 扩展名写出')
  console.log('通过：第二批切换 VTT，生成 clip.vtt / clip (1).vtt，扩展名与格式一致。')
} finally {
  if (app) await app.close()
  const name = relative(output, run)
  if (dirname(run) === output && name.startsWith('batch-') && !name.includes(sep)) {
    await rm(run, { recursive: true, force: true, maxRetries: 4, retryDelay: 300 })
  }
}
