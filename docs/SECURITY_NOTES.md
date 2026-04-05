Este proyecto se distribuye bajo licencia GNU GPL v3. Ver LICENSE.txt

# Notas de seguridad

## Superficie expuesta
- Solo `GET`; resto de métodos → `405`.
- Cabeceras mínimas: `Referrer-Policy: no-referrer`, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`.

## Autenticación por token
- Habilitable desde Opciones → Servidor. El token (hex) puede ir en query o cabeceras.
- HMAC-SHA256 sobre la URL sin el parámetro `token` (tal cual). Comparación en tiempo constante.
- La clave se guarda protegida con **DPAPI** en Windows; en otros SO, se guarda como `plain:` Base64 URL-safe.

## Controles de ruta y ejecución
- **Whitelist de carpeta base** (opcional): obliga a que `path` sea **relativa**, valida segmentos y niega `..`, UNC, nombres reservados, etc.
- **Extensiones permitidas**: `.exe,.com,.bat,.cmd,.vbs,.ps1,.py` por defecto.
- Ejecución delegada a la aplicación (métodos `os.startfile`, `shell_execute` o `_run_script`).

## Anti-abuso
- Backoff exponencial por IP + User-Agent ante errores (ventana/base/máx/umbral).
- Auditoría en memoria (hasta 10.000 eventos) y notificaciones configurables.

## Recomendaciones (mejora futura)
- **Token estable**: firmar una versión **canónica** de la URL que excluya `token`, `close`, `silent` y **ordene** el resto de parámetros (evita tener que distribuir otra URL si cambian esos flags).
- **TLS obligatorio** cuando `server_local_only=false` (no levantar HTTP plano en red).
- Añadir cabeceras `X-Frame-Options: DENY`, `Permissions-Policy: ...` y `Strict-Transport-Security` (en HTTPS) según el despliegue.
