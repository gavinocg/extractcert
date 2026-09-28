import { describe, expect, it } from 'vitest'
import { authRedirect, passwordPolicyError, REQUIRED_PASSWORD_PATH } from './authPolicy'
import type { User } from './store/auth'

const user = (mustChange: boolean): User => ({ id: 1, username: 'operador', nombre: 'Operador', email: 'o@example.com', rol: 'usuario', must_change_password: mustChange })

describe('authRedirect', () => {
  it('restringe cualquier ruta mientras el cambio sea obligatorio', () => {
    expect(authRedirect(user(true), '/historial')).toBe(REQUIRED_PASSWORD_PATH)
    expect(authRedirect(user(true), REQUIRED_PASSWORD_PATH)).toBeNull()
  })

  it('impide que una sesión normal permanezca en la ruta obligatoria', () => {
    expect(authRedirect(user(false), REQUIRED_PASSWORD_PATH)).toBe('/')
    expect(authRedirect(user(false), '/historial')).toBeNull()
  })
})

describe('passwordPolicyError', () => {
  it('valida longitud, bytes UTF-8 y nombre de usuario', () => {
    expect(passwordPolicyError('corta', 'operador')).toContain('6 caracteres')
    expect(passwordPolicyError('á'.repeat(37), 'operador')).toContain('72 bytes')
    expect(passwordPolicyError('ClaveOPERADOR2026', 'operador')).toContain('usuario')
    expect(passwordPolicyError('Ab1!xy', 'operador')).toBeNull()
  })
})
