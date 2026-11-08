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
