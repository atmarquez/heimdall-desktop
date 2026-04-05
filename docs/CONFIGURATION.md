Este proyecto se distribuye bajo licencia GNU GPL v3. Ver LICENSE.txt

# Configuración (`config.json`)

Claves relevantes:

- `base_dir` (str): Carpeta base de accesos.
- `window` (obj): Tamaño y posición (`width`, `height`, `x`, `y`).
- `start_minimized` (bool), `minimize_to_tray` (bool), `launch_and_minimize` (bool).
- `view_mode` (str): `grouped` | `flat`.
- `root_category_name`, `app_title`, `app_icon_path`, `web_search_url`.
- `theme` (str): `system` | `light` | `dark` | `high_contrast` | `host_system`.
- `log_enabled` (bool), `log_file_path` (str).
- **Servidor**:
  - `server_enabled` (bool), `server_port` (int), `server_local_only` (bool).
  - `server_whitelist_base` (bool): exigir rutas **relativas** bajo `base_dir`.
  - `server_allowed_exts` (lista): extensiones permitidas.
  - `server_notify_mode`: `all` | `none` | `only_ok` | `only_errors`.
  - **TLS**: `server_tls_enabled`, `server_tls_certfile`, `server_tls_keyfile`, `server_tls_min_version` (`TLS1.2|TLS1.3`).
  - **Token**: `server_token_enabled`, `server_token_key_protected` (DPAPI/`plain:`).
  - **Backoff**: `server_throttle_window_sec`, `server_throttle_base_ms`, `server_throttle_max_ms`, `server_throttle_threshold`.
