import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import LoadingOverlay from './LoadingOverlay'

describe('LoadingOverlay', () => {
  afterEach(() => vi.useRealTimers())

  it('solo aparece después de 4000 ms y espera todas las solicitudes', () => {
    vi.useFakeTimers()
    render(<LoadingOverlay />)
    act(() => window.dispatchEvent(new Event('app:loading-start')))
    act(() => vi.advanceTimersByTime(3999))
    expect(screen.queryByText('Procesando, un momento...')).not.toBeInTheDocument()
    act(() => window.dispatchEvent(new Event('app:loading-start')))
    act(() => vi.advanceTimersByTime(1))
    expect(screen.getByText('Procesando, un momento...')).toBeInTheDocument()
    act(() => window.dispatchEvent(new Event('app:loading-end')))
    expect(screen.getByText('Procesando, un momento...')).toBeInTheDocument()
    act(() => window.dispatchEvent(new Event('app:loading-end')))
    expect(screen.queryByText('Procesando, un momento...')).not.toBeInTheDocument()
  })

  it('no parpadea en solicitudes menores a un segundo', () => {
    vi.useFakeTimers()
    render(<LoadingOverlay />)
    act(() => window.dispatchEvent(new Event('app:loading-start')))
    act(() => vi.advanceTimersByTime(500))
    act(() => window.dispatchEvent(new Event('app:loading-end')))
    act(() => vi.advanceTimersByTime(600))
    expect(screen.queryByText('Procesando, un momento...')).not.toBeInTheDocument()
  })
})
