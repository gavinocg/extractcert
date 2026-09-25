import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import LoadingOverlay from './LoadingOverlay'

describe('LoadingOverlay', () => {
  afterEach(() => vi.useRealTimers())

  it('solo aparece después de 1000 ms y espera todas las solicitudes', () => {
    vi.useFakeTimers()
    render(<LoadingOverlay />)
    act(() => window.dispatchEvent(new Event('app:loading-start')))
    act(() => vi.advanceTimersByTime(999))
    expect(screen.queryByText('Cargando datos...')).not.toBeInTheDocument()
    act(() => window.dispatchEvent(new Event('app:loading-start')))
    act(() => vi.advanceTimersByTime(1))
    expect(screen.getByText('Cargando datos...')).toBeInTheDocument()
    act(() => window.dispatchEvent(new Event('app:loading-end')))
    expect(screen.getByText('Cargando datos...')).toBeInTheDocument()
    act(() => window.dispatchEvent(new Event('app:loading-end')))
    expect(screen.queryByText('Cargando datos...')).not.toBeInTheDocument()
  })

  it('no parpadea en solicitudes menores a un segundo', () => {
    vi.useFakeTimers()
    render(<LoadingOverlay />)
    act(() => window.dispatchEvent(new Event('app:loading-start')))
    act(() => vi.advanceTimersByTime(500))
    act(() => window.dispatchEvent(new Event('app:loading-end')))
    act(() => vi.advanceTimersByTime(600))
    expect(screen.queryByText('Cargando datos...')).not.toBeInTheDocument()
  })
})
