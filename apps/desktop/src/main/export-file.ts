import { randomUUID } from 'node:crypto'
import { open, rename, rm, writeFile } from 'node:fs/promises'
import { dirname, join } from 'node:path'

export async function writeExportFile(target: string, content: string, overwrite: boolean) {
  if (!overwrite) {
    const file = await open(target, 'wx')
    try {
      await file.writeFile(content, 'utf8')
      await file.close()
    } catch (error) {
      await file.close().catch(() => {})
      await rm(target, { force: true }).catch(() => {})
      throw error
    }
    return
  }

  const temporary = join(dirname(target), `.subtitle-${randomUUID()}.tmp`)
  try {
    await writeFile(temporary, content, { encoding: 'utf8', flag: 'wx' })
    await rename(temporary, target)
  } finally {
    await rm(temporary, { force: true }).catch(() => {})
  }
}

/**
 * 由媒体文件名生成字幕主文件名：去掉扩展名，替换文件系统不允许的字符。
 * 批量自动导出和单任务默认文件名共用这份规则。
 */
export function subtitleBaseName(name: string): string {
  const base = name.replace(/\.[^./\\]+$/, '').replace(/[<>:"/\\|?*]/g, '-').trim()
  return base || '字幕'
}

/**
 * 把已保存字幕写入指定目录，遇到同名文件自动追加序号，用排他创建保护已有文件。
 * 与单任务导出共用 `writeExportFile`，供批量自动导出调用。
 */
export async function writeSubtitleWithUniqueName(
  directory: string,
  baseName: string,
  format: string,
  content: string,
): Promise<string> {
  const base = subtitleBaseName(baseName)
  for (let attempt = 0; attempt < 10000; attempt += 1) {
    const name = attempt === 0 ? `${base}.${format}` : `${base} (${attempt}).${format}`
    const target = join(directory, name)
    try {
      await writeExportFile(target, content, false)
      return target
    } catch (error) {
      if (error instanceof Error && 'code' in error && error.code === 'EEXIST') continue
      throw error
    }
  }
  throw new Error('同名文件过多，无法生成唯一的字幕文件名。')
}
