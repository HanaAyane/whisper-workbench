import { spawn } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { join } from 'node:path'
import { createInterface } from 'node:readline'

export class SidecarResponseError extends Error {}

export class SidecarConnection {
  ended = false

  constructor(private readonly port: number, private readonly token: string) {}

  async request<T>(path: string, options: { method?: string; body?: unknown; text?: boolean } = {}): Promise<T> {
    if (this.ended) throw new Error('本地服务已停止。')
    let response: Response
    try {
      response = await fetch(`http://127.0.0.1:${this.port}/api${path}`, {
        method: options.method,
        headers: { 'X-Sidecar-Token': this.token, 'Content-Type': 'application/json' },
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
        redirect: 'error',
        signal: AbortSignal.timeout(8000),
      })
    } catch {
      throw new Error('无法连接本地服务，请重试。')
    }
    if (!response.ok) {
      const error: { detail?: unknown } = await response.json().catch(() => ({}))
      const detail = error.detail
      if (typeof detail === 'string') throw new SidecarResponseError(detail)
      if (response.status === 422) throw new SidecarResponseError('提交内容不符合要求，请检查填写的字段。')
      throw new SidecarResponseError(`本地服务返回错误（${response.status}）。`)
    }
    if (response.status === 204) return undefined as T
    return options.text ? await response.text() as T : await response.json() as T
  }
}

export class Sidecar {
  private process?: { stop: () => void; closed: Promise<void> }
  private pending?: Promise<SidecarConnection>

  constructor(private readonly root: string, private readonly packaged: boolean) {}

  connect(modelsDir?: string) {
    this.pending ??= this.start(modelsDir)
    return this.pending
  }

  async stop() {
    const child = this.process
    child?.stop()
    await child?.closed
  }

  private async start(modelsDir?: string) {
    const token = randomBytes(32).toString('hex')
    const python = process.env.JP_WORKBENCH_PYTHON || join(
      this.root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
    )
    const executable = this.packaged
      ? join(process.resourcesPath, 'sidecar', process.platform === 'win32' ? 'jp-sidecar.exe' : 'jp-sidecar')
      : python
    const env: NodeJS.ProcessEnv = {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      JP_WORKBENCH_ROOT: process.env.JP_WORKBENCH_ROOT || this.root,
      JP_WORKBENCH_DESKTOP: '1',
      SIDECAR_TOKEN: token,
    }
    if (modelsDir) {
      env.JP_WORKBENCH_MODELS_DIR = modelsDir
      env.JP_WORKBENCH_MANIFEST = join(modelsDir, 'manifest.json')
    }
    const child = spawn(executable, this.packaged ? [] : ['-m', 'app.main'], {
      cwd: this.packaged ? this.root : join(this.root, 'backend'),
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
      env,
    })
    let connection: SidecarConnection | undefined
    const closed = new Promise<void>((resolve) => {
      child.once('close', () => {
        if (connection) connection.ended = true
        this.process = undefined
        this.pending = undefined
        resolve()
      })
    })
    this.process = { stop: () => { child.kill() }, closed }
    child.stdin.on('error', () => {})
    child.stderr.resume()

    try {
      return await new Promise<SidecarConnection>((resolve, reject) => {
        const lines = createInterface({ input: child.stdout })
        const finish = () => {
          clearTimeout(timer)
          lines.close()
        }
        const fail = (message: string) => {
          finish()
          reject(new Error(message))
        }
        const timer = setTimeout(() => fail('本地服务启动超时，请检查 Python 环境。'), 30000)
        child.once('error', () => fail('无法启动本地服务，请检查项目 .venv 或 sidecar 程序。'))
        child.once('close', () => fail('本地服务已退出，请检查 Python 环境和启动配置。'))
        lines.on('line', (line) => {
          if (!line.startsWith('SIDECAR_READY ')) return
          try {
            const ready: { port: number; token: string } = JSON.parse(line.slice('SIDECAR_READY '.length))
            if (!Number.isInteger(ready.port) || ready.port < 1 || ready.port > 65535 || ready.token !== token) {
              throw new Error()
            }
            connection = new SidecarConnection(ready.port, token)
            finish()
            child.stdout.resume()
            console.info('本地服务已就绪。')
            resolve(connection)
          } catch {
            fail('本地服务启动凭据无效。')
          }
        })
      })
    } catch (error) {
      child.kill()
      await closed
      throw error
    }
  }
}
