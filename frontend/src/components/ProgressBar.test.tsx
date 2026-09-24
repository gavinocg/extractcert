import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import ProgressBar from './ProgressBar'

describe('ProgressBar', () => {
  it('muestra realizados, errores, pendientes y porcentaje', () => {
    render(<ProgressBar metricas={{ total: 10, realizados: 6, errores: 2, pendientes: 2, porcentaje: 80 }} />)

    expect(screen.getByText('6 realizados · 2 errores')).toBeInTheDocument()
    expect(screen.getByText('80%')).toBeInTheDocument()
    expect(screen.getByText('2 pendientes · 10 total')).toBeInTheDocument()
  })
})
