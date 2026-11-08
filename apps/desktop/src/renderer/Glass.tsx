import { useEffect, useRef, type ComponentPropsWithoutRef } from 'react'
import { liquidGlass } from './glasswork/lens'
import { useWorkbench } from './store'

export function Glass({ className = '', ...props }: ComponentPropsWithoutRef<'div'>) {
  const ref = useRef<HTMLDivElement>(null)
  const theme = useWorkbench((state) => state.theme)
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-transparency: reduce)')
    const lens = liquidGlass(ref.current!, { rim: 40, edge: 1.1, power: 2.6, dispersion: 0.15, enabled: !media.matches })
    const update = () => lens.update({ enabled: !media.matches })
    media.addEventListener('change', update)
    return () => {
      media.removeEventListener('change', update)
      lens.destroy()
    }
  }, [])
  return <div ref={ref} className={`glass ${className}`} data-kind={theme} {...props} />
}
