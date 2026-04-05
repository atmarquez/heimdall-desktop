Este proyecto se distribuye bajo licencia GNU GPL v3. Ver LICENSE.txt

# Arquitectura

A alto nivel, el sistema se compone de:

- **ConfigService**: carga/guarda `config.json`, resuelve rutas de recursos y log. Centraliza acceso a configuración.
- **MainWindow (PySide6)**: UI principal, árbol de accesos/categorías, atajos, bandeja del sistema y notificaciones.
- **Diálogos de configuración**: `ConfigDialog`, `ServerOptionsDialog`, `TlsOptionsDialog`, `ThrottleConfigDialog`, `TokenDialog` y utilidades de creación de accesos.
- **Servidor**: `LauncherHTTPServer` + `ServerThread` con `LauncherRequestHandler` que atiende `GET`.
- **Auditoría/backoff**: almacenamiento en memoria (`deque`) y penalización por IP/UA con ventana, base, máximo y umbral configurables.

Flujo de petición HTTP:
1. Llega `GET` → se añaden cabeceras de seguridad mínimas.
2. Se valida método, tamaño y cabeceras; se procesan parámetros `close`/`silent`.
3. Si el **token** está habilitado: se extrae de **query**, `X-Launcher-Token` o `Authorization: Bearer` y se valida **HMAC** de la URL **sin el parámetro `token`**.
4. Si `server_whitelist_base` está activo: la `path` **debe ser relativa** a la carpeta base y pasa validaciones de segmentos/nombres.
5. Se verifica la **extensión** (`.exe/.com/.bat/.cmd/.vbs/.ps1/.py` por defecto) y la existencia del archivo.
6. Se ejecuta el destino y se responde según `silent` (204), `close` (HTML con `window.close()`) o JSON (ok/error). También se registra en auditoría y notificaciones.
