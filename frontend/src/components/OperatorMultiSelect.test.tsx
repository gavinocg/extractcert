import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import OperatorMultiSelect from './OperatorMultiSelect'

const operators = [
  { id: 1, username: 'ana', nombre: 'Ana Uno', email: 'ana@example.com' },
  { id: 2, username: 'beto', nombre: 'Beto Dos', email: 'beto@example.com' },
]

describe('OperatorMultiSelect', () => {
  it('agrega y retira responsables sin perder los demás', () => {
    const onChange = vi.fn()
    const { rerender } = render(<OperatorMultiSelect operators={operators} selected={[1]} search="" onSearch={() => undefined} onChange={onChange} />)

    fireEvent.click(screen.getByRole('button', { name: /1 responsable seleccionado/i }))
    fireEvent.click(screen.getByRole('checkbox', { name: /Beto Dos/i }))
    expect(onChange).toHaveBeenLastCalledWith([1, 2])

    rerender(<OperatorMultiSelect operators={operators} selected={[1, 2]} search="" onSearch={() => undefined} onChange={onChange} />)
    fireEvent.click(screen.getByRole('checkbox', { name: /Ana Uno/i }))
    expect(onChange).toHaveBeenLastCalledWith([2])
  })
})
