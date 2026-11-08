import { spawnSync } from 'node:child_process'
import { createRequire } from 'node:module'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

if (process.platform !== 'win32' && process.platform !== 'darwin') {
  throw new Error('请在 Windows 或 macOS 上构建本机安装包。')
}

const root = fileURLToPath(new URL('../../../', import.meta.url))
const python = process.env.JP_WORKBENCH_PYTHON || join(
  root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python',
)
const backend = join(root, 'backend')
const result = spawnSync(python, ['-m', 'PyInstaller', '--noconfirm',
  '--distpath', 'dist', '--workpath', 'build', 'pyinstaller.spec'], {
  cwd: backend,
  stdio: 'inherit',
  windowsHide: true,
})
if (result.error) throw new Error('无法启动构建 Python，请先准备项目 .venv。', { cause: result.error })
if (result.status !== 0) process.exit(result.status ?? 1)

// Electron 的 npm 包按需获取本机运行时，builder 直接复用这个已校验的副本。
createRequire(import.meta.url)('electron')
