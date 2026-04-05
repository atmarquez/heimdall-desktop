Este proyecto se distribuye bajo licencia GNU GPL v3. Ver LICENSE.txt

# API HTTP/HTTPS

**Método**: `GET`

**Ruta**: `/` con parámetros de consulta.

## Parámetros de consulta (query)
- `path` (obligatorio): Ruta del archivo a ejecutar. Puede ir en `?path=...` o como parte de la ruta (`/MiCarpeta%5CMiExe.exe`).
- `token` (opcional*): Token HMAC en formato hex (si la autenticación por token está habilitada; también puede ir en cabeceras, ver abajo).
- `close` (opcional): `1|true|yes` → devuelve HTML con `window.close()`.
- `silent` (opcional): `1|true|yes` → devuelve `204 No Content` y cierra conexión (tiene prioridad sobre `close`).

## Cabeceras de autenticación
- `X-Launcher-Token: <hex>`
- `Authorization: Bearer <hex>`

> El servidor acepta token en **query** o en las **cabeceras** anteriores.

## Cálculo del token (estado actual)
Se calcula **HMAC-SHA256** sobre la URL **sin el parámetro `token`** (mismo `path` y el resto de query tal cual). El resultado se compara en **tiempo constante**.  
**Clave**: Base64 URL-safe recomendada, protegida con **DPAPI** en Windows cuando se persiste.  
**Dónde se configura/genera**: diálogo **Calcular Token** en Opciones → Servidor.

## Respuestas
- `204 No Content` si `silent=1`.
- `200 OK` con `{"ok": true}` si se ejecuta correctamente.
- `4xx/5xx` con JSON `{"ok": false, "error": "..."}` en errores; `silent=1` prioriza `204`.

## Ejemplo
```
GET http://127.0.0.1:8080/?path=MiCarpeta%5CMiExe.exe&close=1&token=<HMAC>
```
