import { readFile, rm, writeFile } from 'node:fs/promises'
import type { DeepSeekSettingsInput, DeepSeekThinking } from '../shared/api.js'

/** 与 backend/app/translation/deepseek.py 的 THINKING_LEVELS 保持一致。 */
export const THINKING_LEVELS: readonly DeepSeekThinking[] = ['disabled', 'low', 'high', 'max']
const MODEL_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/
const MAX_KEY_CHARS = 512

/**
 * Key 的加解密由主进程注入：生产环境用 Electron safeStorage（Windows DPAPI、
 * macOS Keychain）。模块本身不接触明文 Key 的存储格式，便于单测。
 */
export interface SecretCodec {
  /** 加密成功返回可落盘的密文；系统不支持安全存储时返回 null。 */
  encrypt(plain: string): Promise<string | null>
  /** 解密失败（密文损坏、换了机器或系统账户）返回 null。 */
  decrypt(payload: string): Promise<string | null>
}

export interface StoredDeepSeekSettings {
  api_key?: string
  model?: string
  thinking?: DeepSeekThinking
  /** 读到旧版明文 api_key；调用方应重新加密保存。 */
  legacy_api_key?: boolean
  /** 有密文但当前系统解不开，界面需要提示重新填写。 */
  api_key_unreadable?: boolean
}

interface FileSettings {
  api_key_encrypted?: string
  api_key?: string
  model?: string
  thinking?: DeepSeekThinking
}

/** 只显示首尾，避免把完整 Key 送回渲染进程。 */
export function maskApiKey(key: string): string {
  const trimmed = key.trim()
  if (trimmed.length <= 8) return '••••'
  return `${trimmed.slice(0, 3)}…${trimmed.slice(-4)}`
}

export function normalizeApiKey(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value !== 'string') throw new Error('API Key 必须是文本。')
  const key = value.trim()
  if (!key) return ''
  if (key.length > MAX_KEY_CHARS) throw new Error(`API Key 不能超过 ${MAX_KEY_CHARS} 个字符。`)
  if (/\s/.test(key) || [...key].some((char) => char.charCodeAt(0) < 32)) {
    throw new Error('API Key 不能包含空白或控制字符。')
  }
  return key
}

export function normalizeModel(value: unknown): string {
  if (value === null || value === undefined) return ''
  if (typeof value !== 'string') throw new Error('模型名必须是文本。')
  const model = value.trim()
  if (!model) return ''
  if (!MODEL_PATTERN.test(model)) throw new Error('模型名只能包含字母、数字和 . _ : -，最长 128 个字符。')
  return model
}

export function normalizeThinking(value: unknown): DeepSeekThinking | '' {
  if (value === undefined || value === null || value === '') return ''
  if (typeof value !== 'string' || !THINKING_LEVELS.includes(value as DeepSeekThinking)) {
    throw new Error('思考强度只支持 disabled、low、high 或 max。')
  }
  return value as DeepSeekThinking
}

async function readFileSettings(path: string): Promise<FileSettings> {
  const raw = await readFile(path, 'utf8').catch(() => null)
  if (!raw) return {}
  try {
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return {}
    const source = parsed as Record<string, unknown>
    const settings: FileSettings = {}
    if (typeof source.api_key_encrypted === 'string') settings.api_key_encrypted = source.api_key_encrypted
    if (typeof source.api_key === 'string') settings.api_key = source.api_key
    if (typeof source.model === 'string') settings.model = source.model
    if (typeof source.thinking === 'string') settings.thinking = source.thinking as DeepSeekThinking
    return settings
  } catch {
    return {}
  }
}

/** 读取设置页保存的 DeepSeek 覆盖项；文件缺失或损坏时按未设置处理。 */
export async function readDeepSeekSettings(
  path: string,
  codec: SecretCodec,
): Promise<StoredDeepSeekSettings> {
  const file = await readFileSettings(path)
  const settings: StoredDeepSeekSettings = {}
  if (file.api_key_encrypted) {
    const decrypted = await codec.decrypt(file.api_key_encrypted)
    if (decrypted) settings.api_key = normalizeApiKey(decrypted)
    else settings.api_key_unreadable = true
  } else if (file.api_key) {
    // 旧版本直接存明文；交给调用方迁移为密文。
    settings.api_key = normalizeApiKey(file.api_key)
    if (settings.api_key) settings.legacy_api_key = true
  }
  if (file.model) settings.model = normalizeModel(file.model)
  if (file.thinking) settings.thinking = normalizeThinking(file.thinking) || undefined
  return settings
}

/**
 * 合并写入设置：undefined 表示保持原值，null / 空串表示清除该覆盖项。
 * Key 只以密文落盘；全部清空时删除文件，回到 .env / 环境变量配置。
 */
export async function writeDeepSeekSettings(
  path: string,
  input: DeepSeekSettingsInput,
  codec: SecretCodec,
): Promise<StoredDeepSeekSettings> {
  const file = await readFileSettings(path)
  const next: FileSettings = { ...file }
  if ('api_key' in input) {
    const key = normalizeApiKey(input.api_key)
    if (key) {
      const encrypted = await codec.encrypt(key)
      if (!encrypted) {
        throw new Error('当前系统不支持安全存储 Key，请改用 .env 或环境变量配置。')
      }
      next.api_key_encrypted = encrypted
      delete next.api_key
    } else {
      delete next.api_key_encrypted
      delete next.api_key
    }
  }
  if ('model' in input) {
    const model = normalizeModel(input.model)
    if (model) next.model = model
    else delete next.model
  }
  if ('thinking' in input) {
    const thinking = normalizeThinking(input.thinking)
    if (thinking) next.thinking = thinking
    else delete next.thinking
  }
  if (!next.api_key_encrypted && !next.model && !next.thinking) {
    await rm(path, { force: true })
    return {}
  }
  // 密文与其余覆盖项放在同一文件里，权限收紧到仅当前用户可读；Key 本身只有密文。
  await writeFile(path, `${JSON.stringify(next, null, 2)}\n`, { encoding: 'utf8', mode: 0o600 })
  const settings: StoredDeepSeekSettings = {}
  if (next.api_key_encrypted) {
    const decrypted = await codec.decrypt(next.api_key_encrypted)
    if (decrypted) settings.api_key = normalizeApiKey(decrypted)
  }
  if (next.model) settings.model = normalizeModel(next.model)
  if (next.thinking) settings.thinking = normalizeThinking(next.thinking) || undefined
  return settings
}
