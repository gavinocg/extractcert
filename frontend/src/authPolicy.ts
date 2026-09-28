import type { User } from './store/auth'

export const REQUIRED_PASSWORD_PATH = '/cambiar-password-obligatorio'

export function authRedirect(user: User, pathname: string): string | null {
  if (user.must_change_password && pathname !== REQUIRED_PASSWORD_PATH) return REQUIRED_PASSWORD_PATH
  if (!user.must_change_password && pathname === REQUIRED_PASSWORD_PATH) return '/'
  return null
}

export function passwordPolicyError(password: string, username: string): string | null {
  if (password.length < 10) return 'La contraseña debe tener al menos 10 caracteres.'
  if (new TextEncoder().encode(password).length > 72) return 'La contraseña no puede superar 72 bytes.'
  if (username && password.toLocaleLowerCase().includes(username.toLocaleLowerCase())) {
    return 'La contraseña no puede contener tu nombre de usuario.'
  }
  return null
}
