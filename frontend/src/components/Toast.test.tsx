import { beforeEach, describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ToastHost } from './Toast'
import { useToast } from '../store/toast'

describe('ToastHost', () => {
  beforeEach(() => useToast.setState({ toasts: [] }))

  it('renderiza los toasts activos', () => {
    useToast.getState().show('Primero', 'success')
    useToast.getState().show('Error!', 'error')
    render(<ToastHost />)
    expect(screen.getByText('Primero')).toBeInTheDocument()
    expect(screen.getByText('Error!')).toBeInTheDocument()
  })

  it('no renderiza nada sin toasts', () => {
    const { container } = render(<ToastHost />)
    expect(container.firstChild).toBeEmptyDOMElement()
  })
})
