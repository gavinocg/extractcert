# Seguridad de contrasenas y cambio obligatorio

## Funcionalidad implementada

- Checkbox administrativo para exigir cambio en el siguiente inicio.
- Usuarios nuevos quedan marcados por defecto.
- Sesion restringida hasta completar el cambio.
- Backend bloquea todas las APIs salvo sesion, cambio y logout.
- JWT versionado; resets y cambios invalidan sesiones anteriores.
- Cookies `Secure` automaticamente en produccion HTTPS.
- Auditoria sin contrasenas, hashes ni tokens.

## Politica

- Minimo 6 caracteres.
- Maximo 72 bytes para bcrypt.
- Diferente de la contrasena actual.
- No puede contener el username completo.
- Rechaza contrasenas comunes.

## Casos de aceptacion

### Usuario nuevo

1. Administrador crea usuario con contrasena temporal.
2. Confirmar checkbox marcado.
3. Iniciar sesion con el nuevo usuario.
4. Verificar redireccion a `/cambiar-password-obligatorio`.
5. Intentar abrir otra URL manualmente.

Resultado: vuelve a la pantalla obligatoria y no aparece el menu.

### Cambio correcto

1. Escribir contrasena actual.
2. Registrar y confirmar una contrasena valida.
3. Confirmar acceso a Pendientes.
4. Cerrar sesion e ingresar con la clave nueva.

Resultado: acceso normal y la clave temporal deja de funcionar.

### Politica

Probar:

- Menos de 6 caracteres.
- Mas de 72 bytes.
- Username dentro de la contrasena.
- Contrasena comun.
- Igual a la actual.
- Confirmacion diferente.

Resultado: cada caso se rechaza con mensaje claro.

### Reset administrativo

1. Mantener una sesion abierta del usuario.
2. Administrador cambia la clave y marca cambio obligatorio.
3. Usar la sesion anterior.

Resultado: token anterior invalido; nuevo login obliga cambio.

### Forzar sin cambiar clave

1. Administrador marca el checkbox sin modificar password.
2. Usuario intenta continuar con una sesion abierta.

Resultado: sesion anterior se invalida y el siguiente login queda restringido.

### Todos los roles

Repetir con Operador, Supervisor y Administrador.

Resultado: ninguno puede evadir el cambio obligatorio.

## Auditoria esperada

Eventos en `security_audit`:

- `creacion_usuario`
- `force_password_change`
- `reset_password`
- `cambio_password`
- `login_restringido`

Nunca deben registrarse contrasenas, hashes, cookies o JWT.
