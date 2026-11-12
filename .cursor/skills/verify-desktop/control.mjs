#!/usr/bin/env node
import { spawn } from 'node:child_process'
import { randomBytes, randomUUID } from 'node:crypto'
import { createRequire } from 'node:module'
import { mkdir, open, readFile, rm, writeFile } from 'node:fs/promises'
import { createServer } from 'node:http'
import { dirname, isAbsolute, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptPath = fileURLToPath(import.meta.url)
const root = resolve(dirname(scriptPath), '..', '..', '..')
const desktopDir = join(root, 'apps', 'desktop')
const home = process.env.VERIFY_DESKTOP_HOME || '/tmp/verify-desktop'
const pointerPath = join(home, 'current.json')
const require = createRequire(join(desktopDir, 'package.json'))

const args = process.argv.slice(2)
const command = args[0]

function flag(name) {
  const index = args.indexOf(name)
  if (index === -1) return undefined
  const value = args[index + 1]
  if (!value || value.startsWith('--')) throw new Error(`${name} 需要参数。`)
  return value
}

function hasFlag(name) {
  return args.includes(name)
}

function inside(child, parent) {
  const rel = relative(parent, child)
  return rel === '' || (!rel.startsWith('..') && !isAbsolute(rel))
}

async function readJson(path) {
  try {
    return JSON.parse(await readFile(path, 'utf8'))
  } catch (error) {
    if (error && error.code === 'ENOENT') return null
    throw error
  }
}

function alive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false
  try {
    process.kill(pid, 0)
    return true
  } catch {
    return false
  }
}

async function currentSession() {
  const session = await readJson(pointerPath)
  if (!session?.port || !session.token) throw new Error('没有验证实例。先运行 launch。')
  if (!alive(session.daemonPid)) throw new Error('验证实例已退出。运行 cleanup 后重新 launch。')
  return session
}

async function call(route, body) {
  const session = await currentSession()
  const response = await fetch(`http://127.0.0.1:${session.port}${route}`, {
    method: body ? 'POST' : 'GET',
    headers: { 'content-type': 'application/json', 'x-verify-token': session.token },
    body: body ? JSON.stringify(body) : undefined,
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.error || `验证实例返回 ${response.status}`)
  }
  return payload
}

function print(payload) {
  console.log(JSON.stringify(payload, null, 2))
}

async function launch() {
  const evidence = resolve(flag('--evidence') || '/tmp/verify-desktop-evidence')
  const existing = await readJson(pointerPath)
  if (existing && alive(existing.daemonPid)) {
    throw new Error(`已有验证实例 ${existing.id}，拒绝再启动。先 cleanup。`)
  }
  await mkdir(evidence, { recursive: true })
  const id = randomUUID()
  const runDir = join(home, 'runs', id)
  if (inside(evidence, runDir) || inside(runDir, evidence)) {
    throw new Error('证据目录不能放在本次运行的临时目录里，cleanup 会删掉临时目录。')
  }
  await mkdir(join(runDir, 'user-data'), { recursive: true })
  await mkdir(join(runDir, 'glossary'), { recursive: true })
  await writeFile(join(evidence, 'KEEP'), `${id}\n`)
  const log = await open(join(runDir, 'daemon.log'), 'a')
  const child = spawn(process.execPath, [scriptPath, '--daemon', id], {
    detached: true,
    cwd: root,
    stdio: ['ignore', log.fd, log.fd],
    env: {
      ...process.env,
      VERIFY_DESKTOP_HOME: home,
      VERIFY_DESKTOP_EVIDENCE: evidence,
      VERIFY_DESKTOP_RUN: id,
    },
  })
  child.unref()
  log.close()
  const statusPath = join(runDir, 'status.json')
  const deadline = Date.now() + 60000
  while (Date.now() < deadline) {
    const status = await readJson(statusPath)
    if (status?.ok) {
      print({ ok: true, id, evidence, userData: status.userData, title: status.title })
      return
    }
    if (status?.error) throw new Error(status.error)
    await new Promise((done) => setTimeout(done, 200))
  }
  const logText = await readFile(join(runDir, 'daemon.log'), 'utf8').catch(() => '')
  throw new Error(`启动超时。\n${logText.slice(-2000)}`)
}

async function cleanup() {
  const session = await readJson(pointerPath)
  let shutdownError
  if (session && alive(session.daemonPid)) {
    try {
      await call('/shutdown', { confirm: true })
      const deadline = Date.now() + 5000
      while (alive(session.daemonPid) && Date.now() < deadline) {
        await new Promise((done) => setTimeout(done, 100))
      }
    } catch (error) {
      if (alive(session.electronPid)) process.kill(session.electronPid, 'SIGTERM')
      if (alive(session.daemonPid)) process.kill(session.daemonPid, 'SIGTERM')
      shutdownError = error
    }
  }
  if (session?.runDir && inside(session.runDir, home)) {
    await rm(session.runDir, { recursive: true, force: true })
  }
  await rm(pointerPath, { force: true })
  if (session?.evidence) await readFile(join(session.evidence, 'KEEP'), 'utf8')
  if (shutdownError) throw shutdownError
  print({ ok: true, removed: session?.runDir ?? null, evidence: session?.evidence ?? null })
}

async function daemon(id) {
  const evidence = resolve(process.env.VERIFY_DESKTOP_EVIDENCE)
  const runDir = join(home, 'runs', id)
  const userData = join(runDir, 'user-data')
  const glossaryDir = join(runDir, 'glossary')
  const statusPath = join(runDir, 'status.json')
  const token = randomBytes(24).toString('hex')
  let app
  let page
  const publish = (status) => writeFile(statusPath, JSON.stringify(status))
  const fail = async (error) => {
    await publish({ ok: false, error: error instanceof Error ? error.message : String(error) })
    if (app) await app.close().catch(() => {})
    process.exit(1)
  }
  try {
    await readFile(join(desktopDir, 'dist', 'index.html'))
    await readFile(join(desktopDir, 'dist-electron', 'main', 'index.js'))
  } catch {
    await fail(new Error('缺少生产构建。在仓库根目录运行 pnpm --dir apps/desktop build。'))
    return
  }
  const env = { ...process.env }
  delete env.ELECTRON_RUN_AS_NODE
  delete env.JP_WORKBENCH_SMOKE
  env.JP_WORKBENCH_VITE = '0'
  env.JP_WORKBENCH_USER_DATA = userData
  env.JP_WORKBENCH_GLOSSARY_DIR = glossaryDir
  env.JP_WORKBENCH_PYTHON = join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')
  const launchArgs = ['.']
  if (process.env.VERIFY_DESKTOP_FAKE_MIC === '1') launchArgs.push('--use-fake-device-for-media-stream')
  if (process.env.VERIFY_DESKTOP_NO_SANDBOX === '1') launchArgs.push('--no-sandbox')
  try {
    const electron = require('electron')
    const { _electron } = require('playwright')
    app = await _electron.launch({
      executablePath: electron,
      args: launchArgs,
      cwd: desktopDir,
      env,
      chromiumSandbox: process.env.VERIFY_DESKTOP_NO_SANDBOX === '1' ? false : undefined,
    })
    page = await app.firstWindow()
    page.setDefaultTimeout(15000)
    page.on('dialog', (dialog) => {
      dialog.dismiss().catch(() => {})
      page.__verifyDialog = dialog.message()
    })
    await page.locator('.app-shell').waitFor({ timeout: 20000 })
    await page.getByText('本地服务就绪', { exact: true }).waitFor({ timeout: 45000 })
    const title = await page.title()
    if (title !== 'Whisper工作台') throw new Error(`窗口标题是 ${title}`)
    await page.screenshot({ path: join(evidence, 'launch.png'), fullPage: true })
    const session = {
      ok: true,
      id,
      daemonPid: process.pid,
      electronPid: app.process().pid,
      token,
      userData,
      glossaryDir,
      evidence,
      runDir,
      title,
    }
    const server = createServer(async (request, response) => {
      if (request.headers['x-verify-token'] !== token) {
        response.writeHead(401, { 'content-type': 'application/json' })
        response.end(JSON.stringify({ ok: false, error: '验证令牌不匹配。' }))
        return
      }
      try {
        const body = await readBody(request)
        const result = await handle(request.url, body)
        unexpectedDialog()
        response.writeHead(200, { 'content-type': 'application/json' })
        response.end(JSON.stringify({ ok: true, ...result }))
      } catch (error) {
        response.writeHead(500, { 'content-type': 'application/json' })
        response.end(JSON.stringify({ ok: false, error: error instanceof Error ? error.message : String(error) }))
      }
    })
    await new Promise((done) => server.listen(0, '127.0.0.1', done))
    session.port = server.address().port
    await publish(session)
    await writeFile(pointerPath, JSON.stringify(session))
    await new Promise((done) => server.on('close', done))
  } catch (error) {
    await fail(error)
  }

  function unexpectedDialog() {
    if (!page?.__verifyDialog) return
    const message = page.__verifyDialog
    page.__verifyDialog = ''
    throw new Error(`出现未预期的对话框：${message}`)
  }

  function evidencePath(name) {
    if (!name) throw new Error('缺少证据文件名。')
    const target = resolve(evidence, name)
    if (!inside(target, evidence)) throw new Error('证据路径必须留在 --evidence 目录内。')
    return target
  }

  async function handle(url, body) {
    if (url === '/doctor') return doctor()
    if (url === '/click') {
      await page.getByRole(body.role, { name: body.name, exact: body.exact !== false }).click()
      return { clicked: body.name }
    }
    if (url === '/fill') {
      await page.getByLabel(body.label, { exact: true }).fill(body.value)
      return { filled: body.label }
    }
    if (url === '/files') {
      const file = resolve(body.path)
      await page.getByLabel(body.label, { exact: true }).setInputFiles(file)
      return { files: file }
    }
    if (url === '/select') {
      await page.getByLabel(body.label, { exact: true }).selectOption(body.value)
      return { selected: body.value }
    }
    if (url === '/wait') {
      const locator = body.role
        ? page.getByRole(body.role, { name: body.name, exact: Boolean(body.exact) })
        : page.getByText(body.text, { exact: Boolean(body.exact) })
      await locator.first().waitFor()
      return { waited: body.name || body.text }
    }
    if (url === '/shot') {
      const target = evidencePath(body.path)
      await mkdir(dirname(target), { recursive: true })
      await page.screenshot({ path: target, fullPage: true })
      return { path: target }
    }
    if (url === '/aria') {
      const target = evidencePath(body.path)
      await mkdir(dirname(target), { recursive: true })
      await writeFile(target, await page.locator('.app-shell').ariaSnapshot())
      return { path: target }
    }
    if (url === '/assert-glossary') return assertGlossary(body.id)
    if (url === '/assert-models') return assertModels()
    if (url === '/shutdown') {
      await app.close()
      app = undefined
      await rm(userData, { recursive: true, force: true })
      await rm(glossaryDir, { recursive: true, force: true })
      await readFile(join(evidence, 'KEEP'), 'utf8')
      setTimeout(() => process.exit(0), 300)
      return { evidence }
    }
    throw new Error(`未知请求 ${url}`)
  }

  async function doctor() {
    if (!alive(app.process().pid)) throw new Error('Electron 进程不在。')
    const title = await page.title()
    const health = await page.evaluate(() => window.api.health())
    const leaked = await page.evaluate(() => 'token' in window.api || typeof window.require !== 'undefined')
    const ready = await page.getByText('本地服务就绪', { exact: true }).isVisible()
    if (title !== 'Whisper工作台') throw new Error(`窗口标题是 ${title}`)
    if (!ready) throw new Error('界面没有显示本地服务就绪。')
    // 版本以 apps/desktop/package.json 为准，避免每次发版都要改校验脚本。
    const expectedVersion = (await readJson(join(desktopDir, 'package.json'))).version
    if (health.status !== 'ok' || health.version !== expectedVersion) {
      throw new Error(`健康检查返回 ${JSON.stringify(health)}`)
    }
    if (leaked) throw new Error('渲染进程暴露了令牌或 Node。')
    const report = {
      title,
      version: health.version,
      modelsOk: health.models_ok,
      userData,
      electronPid: app.process().pid,
      ready: true,
    }
    await writeFile(join(evidence, 'doctor.json'), JSON.stringify(report, null, 2))
    return report
  }

  async function assertGlossary(id) {
    if (!/^[a-z0-9_-]{1,64}$/i.test(id || '')) throw new Error('词表 ID 无效。')
    const mark = await page.locator('.preview-result mark').first().textContent()
    const preview = await page.locator('.preview-result').innerText()
    if (mark !== '田中') throw new Error(`高亮文本是 ${mark || '空'}。`)
    if (!preview.includes('田中太郎') || !preview.includes('替换预览')) throw new Error('替换预览没有出现田中太郎。')
    const storedPath = join(glossaryDir, `${id}.json`)
    const stored = JSON.parse(await readFile(storedPath, 'utf8'))
    const entry = stored.find((item) => item.source === '田中' && item.target === '田中太郎')
    if (!entry) throw new Error(`词表文件 ${storedPath} 没有保存田中 → 田中太郎。`)
    const dir = join(evidence, 'glossary-preview')
    await mkdir(dir, { recursive: true })
    await writeFile(join(dir, 'stored.json'), JSON.stringify(stored, null, 2))
    return { mark, entries: stored.length, storedPath, proof: join(dir, 'stored.json') }
  }

  async function assertModels() {
    await page.getByRole('heading', { name: '工作台设置', exact: true }).waitFor()
    const health = await page.evaluate(() => window.api.health())
    const text = await page.locator('main').innerText()
    const missing = text.includes('无法读取模型清单') || text.includes('未就绪') || text.includes('缺少文件')
    if (health.models_ok && !text.includes('可用')) throw new Error('模型可用，但设置页没有显示可用。')
    if (!health.models_ok && !missing) throw new Error('模型不可用，但设置页没有缺件或清单错误。')
    const report = { modelsOk: health.models_ok, missingShown: missing, readyShown: text.includes('可用') }
    await writeFile(join(evidence, 'model-status.json'), JSON.stringify(report, null, 2))
    return report
  }
}

function readBody(request) {
  return new Promise((resolveBody, reject) => {
    let data = ''
    request.on('data', (chunk) => {
      data += chunk
      if (data.length > 1_000_000) reject(new Error('请求过大。'))
    })
    request.on('end', () => {
      try {
        resolveBody(data ? JSON.parse(data) : {})
      } catch {
        reject(new Error('请求不是 JSON。'))
      }
    })
  })
}

const routes = {
  doctor: ['/doctor'],
  click: ['/click', () => ({ role: flag('--role'), name: flag('--name'), exact: !hasFlag('--inexact') })],
  fill: ['/fill', () => ({ label: flag('--label'), value: flag('--value') })],
  files: ['/files', () => ({ label: flag('--label'), path: flag('--path') })],
  select: ['/select', () => ({ label: flag('--label'), value: flag('--value') })],
  wait: ['/wait', () => ({ role: flag('--role'), name: flag('--name'), text: flag('--text'), exact: hasFlag('--exact') })],
  shot: ['/shot', () => ({ path: flag('--path') })],
  aria: ['/aria', () => ({ path: flag('--path') })],
  'assert-glossary': ['/assert-glossary', () => ({ id: flag('--id') })],
  'assert-models': ['/assert-models'],
}

try {
  if (command === '--daemon') {
    await daemon(args[1])
  } else if (command === 'launch') {
    await launch()
  } else if (command === 'cleanup') {
    await cleanup()
  } else if (command === 'list') {
    print({
      features: ['glossary-preview', 'model-status', 'record-ready', 'export-subtitles', 'batch-import'],
    })
  } else if (routes[command]) {
    const [route, body] = routes[command]
    print(await call(route, body ? body() : undefined))
  } else {
    throw new Error('命令是 launch、doctor、click、fill、files、select、wait、shot、aria、assert-glossary、assert-models、list、cleanup。')
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : error)
  process.exit(1)
}
