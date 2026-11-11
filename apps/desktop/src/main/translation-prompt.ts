import { readFile, rm, writeFile } from 'node:fs/promises'

/** 与 backend/app/translation/prompt.py 的 MAX_SYSTEM_PROMPT_CHARS 保持一致。 */
export const MAX_TRANSLATION_PROMPT_CHARS = 4000

/** 校验设置页提交的翻译提示词；空白表示回到内置预设。 */
export function normalizeTranslationPrompt(prompt: unknown): string {
  if (typeof prompt !== 'string') throw new Error('翻译提示词必须是文本。')
  const value = prompt.trim()
  if (value.length > MAX_TRANSLATION_PROMPT_CHARS) {
    throw new Error(`翻译提示词不能超过 ${MAX_TRANSLATION_PROMPT_CHARS} 个字符。`)
  }
  return value
}

/** 读取用户保存的自定义提示词；文件缺失或损坏时按未自定义处理。 */
export async function readTranslationPrompt(path: string): Promise<string> {
  const raw = await readFile(path, 'utf8').catch(() => null)
  if (!raw) return ''
  try {
    const parsed: unknown = JSON.parse(raw)
    const value = typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)
      ? (parsed as { system_prompt?: unknown }).system_prompt
      : null
    return typeof value === 'string' ? normalizeTranslationPrompt(value) : ''
  } catch {
    return ''
  }
}

/** 保存自定义提示词；空内容删除文件，恢复内置预设。 */
export async function writeTranslationPrompt(path: string, prompt: string): Promise<string> {
  const value = normalizeTranslationPrompt(prompt)
  if (!value) {
    await rm(path, { force: true })
    return ''
  }
  await writeFile(path, `${JSON.stringify({ system_prompt: value }, null, 2)}\n`, 'utf8')
  return value
}
