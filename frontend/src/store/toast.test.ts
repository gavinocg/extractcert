import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useToast } from './toast'

describe('toast store', () => {
  beforeEach(() => {
    useToast.setState({ toasts: [] })
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('agrega un toast', () => {
    useToast.getState().show('Hola', 'info')
    expect(useToast.getState().toasts).toHaveLength(1)
    expect(useToast.getState().toasts[0].message).toBe('Hola')
  })

  it('autodescarta el toast a los 4 segundos', () => {
    useToast.getState().show('x')
    expect(useToast.getState().toasts).toHaveLength(1)
    vi.advanceTimersByTime(4000)
    expect(useToast.getState().toasts).toHaveLength(0)
  })

  it('dismiss elimina un toast concreto', () => {
    useToast.getState().show('a')
    useToast.getState().show('b')
    const id = useToast.getState().toasts[0].id
    useToast.getState().dismiss(id)
    const rest = useToast.getState().toasts
    expect(rest).toHaveLength(1)
    expect(rest[0].message).toBe('b')
  })
})
