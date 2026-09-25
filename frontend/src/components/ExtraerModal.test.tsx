import { StrictMode } from 'react'
import { act, render } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import ExtraerModal from './ExtraerModal'

const { post } = vi.hoisted(() => ({ post: vi.fn(() => Promise.resolve({})) }))

vi.mock('../api/client', () => ({
  api: { post },
  ApiError: class ApiError extends Error { status = 409 },
}))
vi.mock('./PdfViewer', () => ({ default: () => <div>PDF</div> }))
vi.mock('./ErrorModal', () => ({ default: () => null }))

describe('ExtraerModal lease', () => {
  afterEach(() => { vi.useRealTimers(); post.mockClear() })

  it('no libera el lease por el remount de StrictMode y sí al cerrar realmente', () => {
    vi.useFakeTimers()
    const view = render(
      <StrictMode>
        <ExtraerModal ruta="/lote/a.pdf" documentoId={10} leaseToken="lease-1" onClose={() => undefined} onGuardado={() => undefined} />
      </StrictMode>,
    )

    act(() => { vi.advanceTimersByTime(200) })
    expect(post).not.toHaveBeenCalledWith('/api/lotes/documentos/10/release', expect.anything())

    view.unmount()
    act(() => { vi.advanceTimersByTime(200) })
    expect(post).toHaveBeenCalledWith('/api/lotes/documentos/10/release', { lease_token: 'lease-1' })
  })
})
