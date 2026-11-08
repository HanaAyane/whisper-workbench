// macOS 本地构建使用 ad-hoc 签名：Electron.app 被复制并改写 Info.plist 后，
// 原有的 linker 签名不再覆盖新增资源，Gatekeeper 会把下载到的包报成“已损坏”。
// 配置了 Developer ID（CSC_LINK/identity）时，electron-builder 会在 afterPack
// 之后用真实证书重新签名，此处的 ad-hoc 签名会被覆盖，不影响正式发布流程。
const { execFileSync } = require('node:child_process')
const { join } = require('node:path')

module.exports = async function afterPack(context) {
  if (context.electronPlatformName !== 'darwin') return
  const app = join(context.appOutDir, `${context.packager.appInfo.productFilename}.app`)
  execFileSync('codesign', ['--force', '--deep', '--sign', '-', app], { stdio: 'inherit' })
}
