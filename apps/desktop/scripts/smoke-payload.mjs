// 环回翻译 mock 使用的请求解析：字幕原文用 <subtitles>/<subtitle id="n"> 边界发送。
// 与 backend/app/translation/prompt.py 的 render_user_content 保持同一格式。
export function parseTranslationRequest(body) {
  const payload = JSON.parse(body)
  const system = payload?.messages?.[0]?.content
  const content = payload?.messages?.[1]?.content
  if (typeof system !== 'string' || !system.includes('<subtitles>')) {
    throw new Error('system 提示词缺少固定数据边界规则。')
  }
  if (typeof content !== 'string') throw new Error('user 消息不是文本。')
  const segments = [...content.matchAll(/<subtitle id="(\d+)">([\s\S]*?)<\/subtitle>/g)]
    .map(([, id, text]) => ({ id: Number(id), text }))
  if (segments.length === 0) throw new Error('没有解析到字幕段。')
  return { system, segments }
}
