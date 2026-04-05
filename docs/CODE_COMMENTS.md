Este proyecto se distribuye bajo licencia GNU GPL v3. Ver LICENSE.txt

# Comentarios de código (guía de lectura)

Este documento resume, función a función/clase a clase, el propósito y las decisiones de diseño más importantes. Para *docstrings* inline, consulta `main3_with_docstrings.py`.

## `ConfigService`
- Centraliza acceso a `config.json` y resuelve rutas (`app_icon_path`, `styles_qss_path`, `log_file_path`).
- Aporta *defaults* robustos y maneja errores de lectura/escritura de forma segura.

## `MainWindow`
- Construye la UI, toolbar, árbol de accesos, panel derecho y bandeja del sistema.
- Persistencia en vivo del tamaño/posición de ventana y *view mode*.
- Operaciones de archivos: crear accesos `.url`/`.lnk`, mover/copiar/pegar, renombrar, eliminar, drag&drop con diálogo de importación.
- Temas visuales: QSS embebidos (claro/oscuro/alto contraste) o nativo sistema anfitrión.

## Diálogos
- `ConfigDialog`: configura generales, apariencia, scripts de arranque/salida y **Servidor** (incluye resúmenes y accesos directos a diálogos específicos).
- `ServerOptionsDialog`, `TlsOptionsDialog`, `ThrottleConfigDialog`, `TokenDialog` para granularidad en servidor/TLS/backoff/token.

## Servidor HTTP/HTTPS
- `ServerThread` + `LauncherHTTPServer` + `LauncherRequestHandler`.
- Solo `GET`. Parámetros: `path`, `token` (o cabeceras), `close`, `silent`.
- Validaciones: método, cuerpo en GET, token si está habilitado, whitelist, extensión permitida, existencia; luego ejecuta y responde.
- Auditoría: `request_start`, `reject`, `executed`, `exec_error`, `exception`, y `server_started/stopped`.

## Auditoría/Backoff
- *deque* en memoria hasta 10.000 eventos, contador total, visor con auto-refresh.
- Penalización por IP/UA con ventana/base/máx/umbral configurables.

> Completa estos comentarios con detalles específicos de tu despliegue (rutas, políticas y riesgo aceptable).
