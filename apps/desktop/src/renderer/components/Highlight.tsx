import type { ReviewHit, TermHit } from '../../shared/api'
import { highlightedParts } from '../format'

export const policyLabel = { correct: '原文纠错', translate: '译名统一', keep: '仅标记' }

export function Highlight({ text, hits }: { text: string; hits: (TermHit | ReviewHit)[] }) {
  return <>{highlightedParts(text, hits).map((part, index) => part.hit
    ? <mark key={index} className={'decision' in part.hit ? `term-${part.hit.decision}` : undefined}
      title={part.hit.replacement
      ? `${policyLabel[part.hit.policy]} · ${part.hit.replacement}`
      : policyLabel[part.hit.policy]}>{part.text}</mark>
    : part.text)}</>
}
