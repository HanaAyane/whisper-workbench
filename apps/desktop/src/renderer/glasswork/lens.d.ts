export function liquidGlass(element: HTMLElement, options?: {
  rim?: number
  edge?: number
  power?: number
  dispersion?: number
  enabled?: boolean
}): {
  supported: boolean
  update(options: { enabled?: boolean }): void
  destroy(): void
}
