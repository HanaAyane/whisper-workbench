import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { mkdir, mkdtemp, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises'
import { dirname, join, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import electron from 'electron'
import { _electron } from 'playwright'

const dir = fileURLToPath(new URL('../', import.meta.url))
const root = resolve(dir, '..', '..')
const output = join(root, 'data', 'desktop-smoke')
const audio = resolve(process.env.JP_WORKBENCH_SMOKE_AUDIO || join(root, 'data', 'demo', 'sample.wav'))
const expectSpeech = Boolean(process.env.JP_WORKBENCH_SMOKE_AUDIO)
await mkdir(output, { recursive: true })
const temporary = await mkdtemp(join(output, 'session-'))
const mic = join(temporary, 'microphone.wav')
const savePath = join(temporary, '字幕.srt')
const userData = join(temporary, 'profile')
let app
const launch = () => _electron.launch({
  executablePath: electron, args: ['.', '--use-fake-device-for-media-stream', `--use-file-for-fake-audio-capture=${mic}`],
  cwd: dir, env: { ...process.env, JP_WORKBENCH_SMOKE: '1', JP_WORKBENCH_VITE: '0',
    JP_WORKBENCH_USER_DATA: userData, JP_WORKBENCH_GLOSSARY_DIR: join(temporary, 'glossary') },
})
try {
  execFileSync('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-i', audio, '-t', '10',
    '-ac', '1', '-ar', '48000', '-c:a', 'pcm_s16le', mic], { stdio: 'pipe', windowsHide: true })
  app = await launch()
  await app.evaluate(() => {
    const NativeSocket = globalThis.WebSocket
    globalThis.jobFrames = 0
    globalThis.WebSocket = class extends NativeSocket {
      constructor(...args) {
        super(...args)
        this.addEventListener('message', () => { globalThis.jobFrames++ })
      }
    }
  })
  const page = await app.firstWindow()
  const errors = []
  page.on('pageerror', (error) => errors.push(error.message))
  await page.getByText('本地服务就绪', { exact: true }).waitFor()
  assert.equal(await page.evaluate(() => typeof window.require), 'undefined')
  assert.equal(await page.evaluate(() => 'token' in window.api), false)
  await page.waitForFunction(() => getComputedStyle(document.querySelector('.topbar')).backdropFilter.includes('liquid-glass-lens'))
  if (await page.locator('html').getAttribute('data-theme') === 'dark') {
    await page.getByRole('button', { name: '切换浅色模式' }).click()
  }
  await capture(app, page, 'workbench-light.png')
  await page.getByRole('button', { name: '切换深色模式' }).click()
  assert.equal(await page.locator('.topbar').getAttribute('data-kind'), 'dark')
  await capture(app, page, 'workbench-dark.png')
  const cdp = await page.context().newCDPSession(page)
  await cdp.send('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-transparency', value: 'reduce' }] })
  await page.waitForFunction(() => getComputedStyle(document.querySelector('.topbar')).backdropFilter === 'none')
  await cdp.send('Emulation.setEmulatedMedia', { features: [] })
  console.log('通过：Electron 窗口、IPC、本地服务和两种 Glasswork 材质。')

  await page.getByRole('button', { name: '术语表', exact: true }).click()
  await page.getByLabel('词表 ID', { exact: true }).fill('phase5-smoke')
  await page.getByLabel('导入词表文件').setInputFiles(join(root, 'examples', 'glossary.demo.json'))
  await page.getByText(/已导入 \d+ 条词条/).waitFor()
  await page.getByLabel('待检查文本').fill('🎙田中さんと渋谷で会いました')
  await page.getByRole('button', { name: '预览匹配' }).click()
  await page.locator('.preview-result mark').first().waitFor()
  assert.equal(await page.locator('.preview-result mark').first().textContent(), '田中')
  assert.match(await page.locator('.preview-result').innerText(), /田中太郎/)
  console.log('通过：导入合成词表、Unicode 命中高亮和替换预览。')

  await page.getByRole('button', { name: '工作台', exact: true }).click()
  await page.getByRole('button', { name: '开始录音', exact: true }).click()
  await page.getByRole('button', { name: '停止录音', exact: true }).waitFor({ timeout: 12000 })
  await page.waitForFunction(() => document.querySelector('.clock')?.textContent === '00:10', undefined, { timeout: 15000 })
  await page.getByRole('button', { name: '停止录音', exact: true }).click()
  await page.getByText('录音已就绪', { exact: true }).waitFor()
  if (expectSpeech) await page.getByLabel('保留录音副本').check()
  await page.getByRole('button', { name: '开始处理', exact: true }).click()
  await waitForJobs(page, 1)
  await page.waitForFunction(() => window.api.listJobs().then((jobs) => jobs[0]?.state === 'succeeded'), undefined, { timeout: 120000 })
  await page.waitForFunction(() => document.querySelector('.job-row.selected')?.textContent.includes('已完成'))
  const recording = await page.evaluate(() => window.api.listJobs().then((jobs) => ({
    count: jobs[0].segments.length, saved: jobs[0].recorded_path,
  })))
  if (expectSpeech) {
    assert.ok(recording.count > 0, '模拟麦克风的日语样本应生成字幕')
    assert.ok(recording.saved && (await stat(recording.saved)).size > 0, '选择保留时应有录音副本')
  } else {
    for (let attempt = 0; attempt < 20; attempt++) {
      if (!(await readdir(join(userData, 'tmp-recordings'))).length) break
      await new Promise((done) => setTimeout(done, 250))
    }
    assert.deepEqual(await readdir(join(userData, 'tmp-recordings')), [])
  }
  console.log(`通过：模拟麦克风录制约 10 秒，WebM 转录完成（${recording.count} 段），${expectSpeech ? '保留录音副本' : '清理临时录音'}。`)

  await page.evaluate(() => {
    const input = document.createElement('input')
    input.type = 'file'
    input.id = 'smoke-file'
    input.hidden = true
    document.body.append(input)
    input.addEventListener('change', () => {
      const transfer = new DataTransfer()
      transfer.items.add(input.files[0])
      document.querySelector('.drop-area').dispatchEvent(new DragEvent('drop', { bubbles: true, dataTransfer: transfer }))
      input.remove()
    }, { once: true })
  })
  await page.locator('#smoke-file').setInputFiles(audio)
  await page.getByRole('button', { name: '开始处理', exact: true }).click()
  await waitForJobs(page, 2)
  await page.waitForFunction(() => document.querySelector('.job-row.selected')?.textContent.includes('已完成'), undefined, { timeout: 120000 })
  const [job] = await page.evaluate(() => window.api.listJobs())
  assert.equal(job.state, 'succeeded')
  if (expectSpeech) assert.ok(job.segments.length > 0, '拖入日语样本应生成字幕')
  if (job.segments.length > 0) {
    await page.getByRole('button', { name: '编辑', exact: true }).first().click()
    await page.getByRole('textbox', { name: '编辑日语原文' }).fill('検証用の字幕')
    await page.getByRole('button', { name: '保存', exact: true }).click()
    await page.getByText('検証用の字幕', { exact: true }).waitFor()
    const current = await page.evaluate(() => window.api.listJobs().then((jobs) => jobs[0].segments[0]))
    assert.ok(current.raw_text === job.segments[0].raw_text, '编辑后应保留模型原文')
    assert.equal(current.text, '検証用の字幕')
  }
  await app.evaluate(({ dialog }, path) => { dialog.showSaveDialog = async () => ({ canceled: false, filePath: path }) }, savePath)
  await page.getByRole('button', { name: '保存文件' }).click()
  await page.getByText(/字幕已保存至/).waitFor()
  const content = await readFile(savePath, 'utf8')
  if (job.segments.length > 0) assert.match(content, /\d\d:\d\d:\d\d,\d{3} --> .*\n検証用の字幕/)
  else assert.equal(content, '')
  assert.deepEqual(errors, [])
  console.log(`通过：拖放本地音频（${job.segments.length} 段）、SRT 保存${job.segments.length ? '及字幕编辑保留原始结果' : ''}。`)
  assert.ok(await app.evaluate(() => globalThis.jobFrames > 0), '应通过 WebSocket 收到任务状态')
  await app.close()
  app = await launch()
  const reopened = await app.firstWindow()
  await reopened.getByText('本地服务就绪', { exact: true }).waitFor()
  await reopened.locator('.job-row').nth(1).waitFor()
  const restored = await reopened.evaluate(() => window.api.listJobs())
  assert.equal(restored.length, 2)
  assert.equal(restored[0].id, job.id)
  assert.ok(restored.every((item) => item.state === 'succeeded'))
  if (job.segments.length) assert.equal(restored[0].segments[0].text, '検証用の字幕')
  console.log('通过：桌面端收到 WebSocket 状态，应用重启后恢复历史任务和字幕。')
} finally {
  if (app) await app.close()
  const location = relative(output, temporary)
  if (dirname(temporary) === output && location.startsWith('session-') && !location.includes(sep)) {
    await rm(temporary, { recursive: true, force: true, maxRetries: 4, retryDelay: 300 })
  }
}

async function waitForJobs(page, count) {
  await page.waitForFunction((total) => window.api.listJobs().then((jobs) => jobs.length === total), count)
}

async function capture(app, page, name) {
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))))
  const encoded = await app.evaluate(async ({ BrowserWindow }) => {
    const window = BrowserWindow.getAllWindows()[0]
    const image = await window.webContents.capturePage(undefined, { stayHidden: true })
    return image.toPNG().toString('base64')
  })
  assert.ok(encoded.length > 100, '桌面窗口截图为空')
  await writeFile(join(output, name), Buffer.from(encoded, 'base64'))
}
