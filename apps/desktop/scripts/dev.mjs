import { spawn } from 'node:child_process'
import { createServer as createProbe } from 'node:net'
import { fileURLToPath } from 'node:url'
import electron from 'electron'
import { createServer } from 'vite'

const dir = fileURLToPath(new URL('../', import.meta.url))
const compiler = spawn(process.execPath, ['node_modules/typescript/bin/tsc', '-p', 'tsconfig.main.json'], {
  cwd: dir, stdio: 'inherit', windowsHide: true,
})
const compiled = await new Promise((resolve, reject) => {
  compiler.once('error', reject)
  compiler.once('exit', resolve)
})
if (compiled !== 0) process.exit(1)

const server = await startVite()
const { port } = server.httpServer.address()
server.printUrls()
const child = spawn(electron, ['.'], {
  cwd: dir,
  env: { ...process.env, JP_WORKBENCH_VITE: '1', JP_WORKBENCH_VITE_PORT: String(port) },
  stdio: 'inherit',
})
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill())
child.on('error', (error) => { console.error(error.message) })
const exit = await new Promise((resolve) => child.once('close', resolve))
await server.close()
process.exitCode = typeof exit === 'number' ? exit : 1

async function startVite() {
  const server = await createServer({ root: dir })
  try {
    return await server.listen()
  } catch (error) {
    await server.close()
    if (!['EACCES', 'EADDRINUSE'].includes(error.code) && !/Port 5173 is already in use/.test(error.message)) throw error
    console.info('默认开发端口 5173 不可用，改用系统分配的环回端口。')
  }
  const port = await new Promise((resolve, reject) => {
    const probe = createProbe()
    probe.once('error', reject)
    probe.listen(0, '127.0.0.1', () => {
      const { port } = probe.address()
      probe.close((error) => error ? reject(error) : resolve(port))
    })
  })
  const fallback = await createServer({ root: dir, server: { port } })
  try {
    return await fallback.listen()
  } catch (error) {
    await fallback.close()
    throw error
  }
}
