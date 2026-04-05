# This file is part of Heimdall Desktop.
#
# Copyright (C) 2024–2026 Naidel
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
Servidor HTTP embebido de Heimdall Desktop (Parte 1).

Este módulo implementa un servidor HTTP restrictivo cuyo propósito es
permitir la ejecución controlada de recursos locales mediante peticiones
GET, bajo una arquitectura defensiva.

Esta primera parte incluye:
- Imports y configuración global
- Definición de extensiones permitidas
- Manejador HTTP principal (`LauncherRequestHandler`)
- Métodos auxiliares de seguridad, auditoría y respuesta
- Rechazo explícito de métodos HTTP no permitidos

IMPORTANT:
    Este servidor NO es un servidor web genérico.
    Está diseñado exclusivamente como mecanismo de control interno/remoto
    con múltiples capas de validación.

NOTE:
    El código es intencionadamente redundante y defensivo.
    Cualquier simplificación debe analizarse desde el punto de vista
    de seguridad antes de aplicarse.
"""

import os
import ssl
import time
import threading
import urllib.parse as urlparse
import http.server as http_server
from pathlib import Path
from PySide6 import QtCore, QtWidgets
import json as _json_for_srv

from server.audit import audit_store
from server.throttle import (
    throttle_penalty_for,
    record_error,
    reset_throttle_state,
)
from server.security import (
    dpapi_unprotect_user,
    compute_hmac_hex,
    consteq,
    split_path_query,
    strip_token_param,
)

import logging
LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuración de seguridad por defecto
# ---------------------------------------------------------------------------

# Extensiones permitidas por defecto para ejecución vía HTTP.
#
# NOTE:
#   Esta lista puede ser redefinida mediante configuración del usuario.
#   Se normaliza posteriormente a minúsculas y con prefijo ".".
SERVER_ALLOWED_EXTS = {
    '.exe', '.com', '.bat', '.cmd', '.vbs', '.ps1', '.py'
}


class LauncherRequestHandler(http_server.BaseHTTPRequestHandler):
    """
    Manejador de peticiones HTTP para el servidor de lanzamiento.

    Cada instancia de esta clase gestiona una única conexión entrante y es
    responsable de aplicar todas las políticas de seguridad antes de que
    se permita cualquier tipo de ejecución local.

    Responsabilidades principales:
    - Endurecimiento de cabeceras HTTP.
    - Auditoría de todas las acciones.
    - Aplicación de throttling adaptativo ante errores.
    - Envío de respuestas JSON, HTML mínimo o 204.
    - Rechazo explícito de métodos HTTP no permitidos.

    IMPORTANT:
        Este handler NO debe servir contenido genérico ni ficheros arbitrarios.
    """

    # Identificador del servidor visible en cabeceras HTTP
    server_version = 'LauncherServer/0.7'

    def end_headers(self):
        """
        Sobrescribe el envío de cabeceras HTTP.

        Antes de finalizar las cabeceras, se añaden políticas defensivas
        para reducir superficie de ataque y evitar comportamientos no deseados.
        """
        try:
            self._harden_headers()
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en LauncherRequestHandler::end_headers'
            )
        super().end_headers()

    def _harden_headers(self):
        """
        Aplica cabeceras HTTP defensivas estándar.

        Se limita:
        - El envío de referencias (`Referrer-Policy`)
        - El sniffing de contenido (`X-Content-Type-Options`)
        - El cacheo de respuestas (`Cache-Control`)
        """
        try:
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Cache-Control', 'no-store')
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en LauncherRequestHandler::_harden_headers'
            )

    def _audit(self, action, **fields):
        """
        Registra una acción relevante en el sistema de auditoría.

        La auditoría se envía tanto al logger como al backend de auditoría
        persistente.

        Args:
            action (str): Identificador de la acción.
            **fields: Campos adicionales asociados a la acción.
        """
        try:
            parts = [f'{k}={fields[k]}' for k in fields]
            LOGGER.info('[audit] ' + action + ' ' + ' '.join(parts))
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en LauncherRequestHandler::_audit'
            )
        try:
            audit_store(action, **fields)
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en LauncherRequestHandler::_audit::audit_store'
            )

    def _maybe_throttle(self, status_code):
        """
        Aplica un retardo progresivo en respuestas con error.

        Si el código HTTP indica error (4xx/5xx), se calcula una penalización
        basada en IP y User-Agent para mitigar abusos.

        NOTE:
            Este mecanismo funciona como backoff adaptativo.
        """
        try:
            sc = int(status_code)
            if 400 <= sc <= 599:
                try:
                    ua = self.headers.get('User-Agent', '') if getattr(self, 'headers', None) else ''
                except Exception:
                    ua = ''
                key = f'{self.client_address[0]}|{ua[:128]}'
                now = time.time()
                penalty_ms, count = throttle_penalty_for(key, now)
                record_error(key, now)
                if penalty_ms > 0:
                    self._audit(
                        'throttle',
                        ip=self.client_address[0],
                        count=count,
                        delay_ms=penalty_ms
                    )
                    time.sleep(penalty_ms / 1000.0)
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en LauncherRequestHandler::_maybe_throttle'
            )

    def log_message(self, fmt, *args):
        """
        Redirige el log estándar del servidor HTTP.

        Elimina el uso de stderr y lo integra con el sistema de logging
        de la aplicación.
        """
        try:
            LOGGER.info('[server] ' + fmt % args)
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en LauncherRequestHandler::log_message'
            )

    def _send_json(self, code, obj):
        """
        Envía una respuesta JSON al cliente.

        Args:
            code (int): Código HTTP a devolver.
            obj (dict): Objeto serializable a JSON.
        """
        try:
            self._maybe_throttle(code)
            data = _json_for_srv.dumps(obj).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Connection', 'close')
            self.end_headers()
            try:
                self.wfile.write(data)
            except (ConnectionAbortedError, BrokenPipeError):
                LOGGER.debug("Cliente cerró la conexión antes de recibir la respuesta")
            finally:
                self.close_connection = True
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en LauncherRequestHandler::_send_json'
            )

    def _send_close_html(self):
        """
        Devuelve una página HTML mínima que intenta cerrar la pestaña del navegador.
        """
        try:
            body = (
                '<!doctype html><html><head><meta charset="utf-8">'
                '<title>Cerrando…</title></head>'
                '<body><script>try{window.close();}catch(e){}</script>'
                '</body></html>'
            ).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            self.end_headers()
            try:
                self.wfile.write(body)
            except (ConnectionAbortedError, BrokenPipeError):
                LOGGER.debug("Cliente cerró la conexión antes de recibir la respuesta")
            finally:
                self.close_connection = True
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en LauncherRequestHandler::_send_close_html'
            )

    def _send_no_content(self):
        """
        Responde con HTTP 204 (sin contenido).

        Se utiliza típicamente cuando la petición es válida pero el cliente
        ha solicitado modo silencioso.
        """
        try:
            self.send_response(204)
            self.send_header('Connection', 'close')
            self.end_headers()
            self.close_connection = True
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en LauncherRequestHandler::_send_no_content'
            )

    def handle_expect_100(self):
        """
        Rechaza explícitamente peticiones con Expect: 100-continue.

        Este comportamiento evita ciertos tipos de abusos y simplifica
        la gestión del cuerpo de las peticiones.
        """
        try:
            self._audit(
                'reject',
                reason='expect_100',
                ip=self.client_address[0]
            )
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en LauncherRequestHandler::handle_expect_100'
            )
        try:
            self._maybe_throttle(417)
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en LauncherRequestHandler::handle_expect_100'
            )
        try:
            self.send_response_only(417, 'Expectation Failed')
            self.send_header('Connection', 'close')
            self.end_headers()
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en LauncherRequestHandler::handle_expect_100'
            )
        self.close_connection = True
        return False

    def _method_not_allowed(self):
        """
        Rechaza métodos HTTP distintos de GET.

        Incluye auditoría y aplicación de throttling.
        """
        try:
            self._audit(
                'reject',
                reason='method_not_allowed',
                method=self.command,
                ip=self.client_address[0]
            )
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en LauncherRequestHandler::_method_not_allowed'
            )
        try:
            self._maybe_throttle(405)
            self.send_response(405)
            self.send_header('Allow', 'GET')
            self.send_header('Connection', 'close')
            self.end_headers()
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en LauncherRequestHandler::_method_not_allowed'
            )
        self.close_connection = True

    # Métodos HTTP explícitamente no soportados
    def do_POST(self):
        return self._method_not_allowed()

    def do_PUT(self):
        return self._method_not_allowed()

    def do_DELETE(self):
        return self._method_not_allowed()

    def do_PATCH(self):
        return self._method_not_allowed()

    def do_OPTIONS(self):
        return self._method_not_allowed()

    def do_HEAD(self):
        return self._method_not_allowed()


    def do_GET(self):
        """
        Maneja peticiones HTTP GET entrantes.

        Este método es el núcleo del servidor HTTP y concentra toda la lógica
        de seguridad, validación y ejecución controlada de archivos locales.

        Flujo general:
        1. Gestión especial de favicon.
        2. Auditoría inicial de la petición.
        3. Lectura de parámetros de control (close, silent).
        4. Autenticación opcional mediante token HMAC.
        5. Validación estricta de cabeceras (GET sin cuerpo).
        6. Resolución y validación del parámetro `path`.
        7. Aplicación opcional de whitelist de carpeta base.
        8. Validación de extensión permitida.
        9. Ejecución controlada del archivo.
        10. Auditoría, notificación a UI y respuesta al cliente.

        WARNING:
            Este método es intencionadamente largo y redundante.
            La complejidad es una decisión de seguridad, no un error de diseño.

        NOTE:
            El comportamiento `silent` y `close` permite integraciones
            limpias con navegadores y scripts externos.

        Args:
            self: Instancia del manejador HTTP.

        Returns:
            Respuesta HTTP apropiada según el resultado de la operación.
        """
        # --------------------------------------------------------------
        # Gestión especial de favicon (peticiones automáticas del navegador)
        # --------------------------------------------------------------
        _p = self.path.lower() if isinstance(self.path, str) else ''
        if _p in ('/favicon.ico', 'favicon.ico', '/favicon.png', 'favicon.png', '/favicon.svg', 'favicon.svg'):
            try:
                from pathlib import Path as PF
                _base = PF(__file__).parent
                _fav = _base / 'resources' / 'app.ico'
                _ctype = 'image/x-icon'

                # Fallback progresivo a PNG o SVG si no existe ICO
                if not _fav.exists():
                    _cand_png = _base / 'resources' / 'app.png'
                    _cand_svg = _base / 'resources' / 'app.svg'
                    if _cand_png.exists():
                        _fav = _cand_png
                        _ctype = 'image/png'
                    elif _cand_svg.exists():
                        _fav = _cand_svg
                        _ctype = 'image/svg+xml'

                if _fav.exists() and _fav.is_file():
                    _data = _fav.read_bytes()
                    self.send_response(200)
                    self.send_header('Content-Type', _ctype)
                    self.send_header('Content-Length', str(len(_data)))
                    self.send_header('Cache-Control', 'public, max-age=300')
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    try:
                        self.wfile.write(_data)
                    except (ConnectionAbortedError, BrokenPipeError):
                        if LOGGER:
                            LOGGER.debug("Cliente cerró la conexión antes de recibir la respuesta")
                            pass
                    finally:
                        self.close_connection = True
                    return
                else:
                    return self._send_no_content()
            except Exception as e:
                return self._send_no_content()

        try:
            # Timeout defensivo de la conexión
            self.connection.settimeout(2.0)

            # Auditoría inicial de la petición
            self._audit('request_start', ip=self.client_address[0], raw=self.path)

            # Parseo de la URL y parámetros GET
            parsed = urlparse.urlparse(self.path)
            q = urlparse.parse_qs(parsed.query)

            # Parámetros de control
            close_tab = q.get('close', ['0'])[0] in ('1', 'true', 'yes')
            silent = q.get('silent', ['0'])[0] in ('1', 'true', 'yes')

            # ----------------------------------------------------------
            # Autenticación opcional mediante token HMAC
            # ----------------------------------------------------------
            try:
                cfg = getattr(self.server.window, 'cfg', {})
                if bool(cfg.get('server_token_enabled', False)):
                    prot = cfg.get('server_token_key_protected', '')
                    if not prot:
                        if silent:
                            return self._send_no_content()
                        return self._send_json(401, {'ok': False, 'error': 'Token requerido'})
                    try:
                        secret = dpapi_unprotect_user(prot).decode('utf-8')
                    except Exception as e:
                        if silent:
                            return self._send_no_content()
                        return self._send_json(401, {'ok': False, 'error': 'Clave inválida'})

                    # Extracción del token desde query, header o Authorization
                    path_part, query_raw = split_path_query(self.path)
                    q_wo, token_from_query, _n_tok = strip_token_param(query_raw)
                    hdr_tok = (self.headers.get('X-Launcher-Token') or '').strip() if self.headers else ''
                    authz = (self.headers.get('Authorization') or '').strip() if self.headers else ''
                    bearer_tok = authz[7:].strip() if authz.lower().startswith('bearer ') else ''
                    token_val = hdr_tok or bearer_tok or token_from_query

                    if not token_val:
                        if silent:
                            return self._send_no_content()
                        return self._send_json(401, {'ok': False, 'error': 'Token ausente'})

                    # Cálculo y comparación segura del HMAC
                    raw_without = path_part if not q_wo else f'{path_part}?{q_wo}'
                    calc = compute_hmac_hex(raw_without, secret)
                    if not consteq(calc, token_val):
                        if silent:
                            return self._send_no_content()
                        return self._send_json(401, {'ok': False, 'error': 'Token inválido'})
            except Exception as e:
                if silent:
                    return self._send_no_content()
                return self._send_json(401, {'ok': False, 'error': 'Autenticación fallida'})

            # ----------------------------------------------------------
            # Validación estricta: GET no debe tener cuerpo
            # ----------------------------------------------------------
            try:
                cl = self.headers.get('Content-Length') if self.headers else None
                te = (self.headers.get('Transfer-Encoding') or '').lower() if self.headers else ''
                if cl and cl.strip() and (int(cl) > 0) or (te and te != 'identity'):
                    self._audit('reject', reason='body_in_get', ip=self.client_address[0], cl=cl or '0', te=te)
                    if silent:
                        return self._send_no_content()
                    return self._send_json(400, {'ok': False, 'error': 'Cuerpo no permitido en GET'})
            except Exception as e:
                self._audit('reject', reason='bad_headers', ip=self.client_address[0])
                if silent:
                    return self._send_no_content()
                return self._send_json(400, {'ok': False, 'error': 'Cabeceras no válidas'})

            # ----------------------------------------------------------
            # Obtención del parámetro path
            # ----------------------------------------------------------
            path = q.get('path', [None])[0]
            if not path:
                path = urlparse.unquote(parsed.path or '')
                if path.startswith('/'):
                    path = path[1:]

            if not path:
                self._audit('reject', reason='missing_path', ip=self.client_address[0])
                if silent:
                    return self._send_no_content()
                return self._send_close_html() if close_tab else self._send_json(
                    400, {'ok': False, 'error': 'Falta parámetro path o ruta en URL'}
                )

            # ----------------------------------------------------------
            # Resolución con whitelist de carpeta base (opcional)
            # ----------------------------------------------------------
            whitelist = bool(getattr(self.server.window, 'cfg', {}).get('server_whitelist_base', False))
            if whitelist:
                try:
                    from pathlib import PureWindowsPath as _PWin
                    from pathlib import Path as _PLocal

                    raw = path or ''
                    rel = _PWin(raw)

                    # Rechazo de rutas absolutas y UNC
                    if rel.is_absolute() or getattr(rel, 'drive', '') or str(raw).startswith(('\\', '//')):
                        self._audit('reject', reason='invalid_relative', ip=self.client_address[0], path=str(raw))
                        if silent:
                            return self._send_no_content()
                        try:
                            self.server.window._notify_http_execution(str(raw), 'error', 'Ruta no válida')
                        except Exception:
                            LOGGER.exception('[auto] Exception capturada en LauncherRequestHandler::do_GET')
                        return self._send_json(400, {'ok': False, 'error': 'Ruta no válida'})

                    parts = [p for p in str(rel).replace('/', '\\').split('\\') if p]

                    # Nombres reservados de Windows
                    reserved = {
                        'con', 'prn', 'aux', 'nul', 'clock$', 'conin$', 'conout$'
                    } | {f'com{i}' for i in range(0, 10)} | {f'lpt{i}' for i in range(0, 10)}

                    def _clean_seg(s: str) -> str:
                        return s.strip().rstrip('. ')

                    for seg in parts:
                        # Bloqueos de traversal y caracteres peligrosos
                        if seg == '..' or '~' in seg:
                            self._audit('reject', reason='invalid_relative', ip=self.client_address[0], path=str(raw))
                            if silent:
                                return self._send_no_content()
                            try:
                                self.server.window._notify_http_execution(str(raw), 'error', 'Ruta no válida')
                            except Exception:
                                LOGGER.exception('[auto] Exception capturada en LauncherRequestHandler::do_GET')
                            return self._send_json(400, {'ok': False, 'error': 'Ruta no válida'})

                        seg_clean = _clean_seg(seg)
                        if any((ord(c) < 32 or ord(c) == 127 for c in seg_clean)):
                            self._audit('reject', reason='control_char', ip=self.client_address[0], path=str(raw))
                            if silent:
                                return self._send_no_content()
                            try:
                                self.server.window._notify_http_execution(str(raw), 'error', 'Ruta no válida')
                            except Exception:
                                LOGGER.exception('[auto] Exception capturada en LauncherRequestHandler::do_GET')
                            return self._send_json(400, {'ok': False, 'error': 'Ruta no válida'})

                        # Rechazo de nombres reservados
                        base_noext = seg_clean.split('.', 1)[0]
                        if base_noext.casefold() in reserved or seg_clean.casefold() in reserved:
                            self._audit('reject', reason='reserved_name', ip=self.client_address[0], path=str(raw))
                            if silent:
                                return self._send_no_content()
                            try:
                                self.server.window._notify_http_execution(str(raw), 'error', 'Ruta no válida')
                            except Exception:
                                LOGGER.exception('[auto] Exception capturada en LauncherRequestHandler::do_GET')
                            return self._send_json(400, {'ok': False, 'error': 'Ruta no válida'})

                    base = self.server.window.base_dir() if hasattr(self.server.window, 'base_dir') else Path('.')
                    p = _PLocal(base).joinpath(*parts).resolve()
                    bres = _PLocal(base).resolve()

                    # Protección frente a salto de unidad
                    try:
                        base_drive = getattr(bres, 'drive', '')
                        p_drive = getattr(p, 'drive', '')
                        if (base_drive or p_drive) and p_drive.casefold() != base_drive.casefold():
                            self._audit('reject', reason='outside_base_drive', ip=self.client_address[0], path=str(p))
                            if silent:
                                return self._send_no_content()
                            try:
                                self.server.window._notify_http_execution(
                                    str(p), 'error', 'Ruta fuera de la carpeta base'
                                )
                            except Exception:
                                LOGGER.exception('[auto] Exception capturada en LauncherRequestHandler::do_GET')
                            return self._send_json(403, {
                                'ok': False,
                                'error': 'Ruta fuera de la carpeta base'
                            })
                    except Exception:
                        pass

                    # Protección final de prefijo
                    base_s = str(bres)
                    p_s = str(p)
                    base_cf = base_s.casefold().rstrip('\\/')
                    p_cf = p_s.casefold()
                    sep = '\\' if '\\' in base_s or '\\' in p_s else os.sep
                    prefix = base_cf + (sep if not base_cf.endswith(('/', '\\')) else '')

                    if not (p_cf == base_cf or p_cf.startswith(prefix if prefix.endswith(sep) else prefix + sep)):
                        self._audit('reject', reason='outside_base', ip=self.client_address[0], path=str(p))
                        if silent:
                            return self._send_no_content()
                        try:
                            self.server.window._notify_http_execution(
                                str(p), 'error', 'Ruta fuera de la carpeta base'
                            )
                        except Exception:
                            LOGGER.exception('[auto] Exception capturada en LauncherRequestHandler::do_GET')
                        return self._send_json(403, {
                            'ok': False,
                            'error': 'Ruta fuera de la carpeta base'
                        })
                except Exception as _e:
                    if silent:
                        return self._send_no_content()
                    try:
                        self.server.window._notify_http_execution(
                            str(path or ''), 'error', 'Ruta no válida'
                        )
                    except Exception:
                        LOGGER.exception('[auto] Exception capturada en LauncherRequestHandler::do_GET')
                    return self._send_json(400, {'ok': False, 'error': 'Ruta no válida'})
            else:
                p = Path(path)

            # ----------------------------------------------------------
            # Validación de existencia y tipo de archivo
            # ----------------------------------------------------------
            if not (p.exists() and p.is_file()):
                self._audit('reject', reason='not_found', ip=self.client_address[0], path=str(p))
            try:
                self.server.window._notify_http_execution(str(p), 'inexistente', '')
            except Exception:
                pass
                if silent:
                    return self._send_no_content()
                return self._send_close_html() if close_tab else self._send_json(
                    404, {'ok': False, 'error': 'Archivo no encontrado'}
                )

            # ----------------------------------------------------------
            # Validación de extensión permitida
            # ----------------------------------------------------------
            try:
                allowed = getattr(self.server.window, 'cfg', {}).get('server_allowed_exts')
                if not allowed:
                    allowed = list(SERVER_ALLOWED_EXTS)
                allowed = {
                    str(e).lower() if str(e).startswith('.') else '.' + str(e).lower()
                    for e in allowed
                }
                ext = Path(p).suffix.lower()
                if ext not in allowed:
                    self._audit('reject', reason='ext_not_allowed', ip=self.client_address[0], path=str(p), ext=ext)
                    try:
                        self.server.window._notify_http_execution(
                            str(p), 'error', 'Tipo de archivo no permitido'
                        )
                    except Exception:
                        LOGGER.exception('[auto] Exception capturada en LauncherRequestHandler::do_GET')
                    if silent:
                        return self._send_no_content()
                    return self._send_json(415, {
                        'ok': False,
                        'error': 'Tipo de archivo no permitido'
                    })
            except Exception:
                LOGGER.exception('[auto] Exception capturada en LauncherRequestHandler::do_GET')

            # ----------------------------------------------------------
            # Ejecución controlada del archivo
            # ----------------------------------------------------------
            ok, err = self.server.window._execute_external(p)
            if ok:
                self._audit('executed', ip=self.client_address[0], path=str(p))
            else:
                self._audit('exec_error', ip=self.client_address[0], path=str(p), error=err or '')

            try:
                if ok:
                    self.server.window._notify_http_execution(str(p), 'ok', '')
                else:
                    self.server.window._notify_http_execution(
                        str(p), 'error', err or ''
                    )
            except Exception:
                LOGGER.exception('[auto] Exception capturada en LauncherRequestHandler::do_GET')

            # ----------------------------------------------------------
            # Respuesta final al cliente
            # ----------------------------------------------------------
            if silent:
                return self._send_no_content()
            if close_tab:
                return self._send_close_html()
            if ok:
                return self._send_json(200, {'ok': True})
            return self._send_json(500, {'ok': False, 'error': err or 'Error al lanzar'})

        except Exception as e:
            # Manejo defensivo de excepciones no controladas
            self._audit('exception', ip=self.client_address[0], error=str(e))
            try:
                q = urlparse.parse_qs(urlparse.urlparse(self.path).query)
                if q.get('silent', ['0'])[0] in ('1', 'true', 'yes'):
                    return self._send_no_content()
                if q.get('close', ['0'])[0] in ('1', 'true', 'yes'):
                    return self._send_close_html()
            except Exception:
                LOGGER.exception('[auto] Exception capturada en LauncherRequestHandler::do_GET')
            return self._send_json(500, {'ok': False, 'error': str(e)})


class LauncherHTTPServer(http_server.ThreadingHTTPServer):
    """
    Servidor HTTP con soporte para hilos y estado extendido.

    Esta clase extiende `ThreadingHTTPServer` para añadir:
    - Ejecución concurrente de peticiones (una por hilo).
    - Asociación explícita con la ventana principal (`MainWindow`),
      lo que permite a los handlers acceder a configuración y servicios
      de la aplicación.

    IMPORTANT:
        Esta clase NO implementa lógica de seguridad ni ejecución.
        Su única responsabilidad es proporcionar un contenedor de servidor
        que exponga el contexto de la aplicación a los handlers.

    Atributos:
        window:
            Referencia a la ventana principal de la aplicación.
            Se utiliza posteriormente por `LauncherRequestHandler`
            para acceder a configuración, notificaciones y ejecución.
    """

    # Permite finalizar hilos automáticamente al cerrar el servidor
    daemon_threads = True

    # Permite reutilizar la dirección/puerto tras un reinicio rápido
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, window, bind_and_activate=True):
        """
        Inicializa el servidor HTTP.

        Args:
            server_address (tuple):
                Tupla (host, puerto) donde el servidor escuchará conexiones.
            RequestHandlerClass:
                Clase manejadora de peticiones HTTP (normalmente LauncherRequestHandler).
            window:
                Referencia a la ventana principal de la aplicación.
                Se almacena para permitir que los handlers accedan al estado global.
            bind_and_activate (bool):
                Indica si el servidor debe enlazar y activarse inmediatamente.

        NOTE:
            La referencia a `window` se guarda antes de llamar a `super().__init__`
            para garantizar que esté disponible durante el ciclo de vida del servidor.
        """
        self.window = window
        super().__init__(server_address, RequestHandlerClass, bind_and_activate=bind_and_activate)


class ServerThread(threading.Thread):
    """
    Hilo dedicado para la ejecución del servidor HTTP/HTTPS integrado.

    Esta clase encapsula el ciclo de vida del servidor:
    - Creación del servidor.
    - Activación opcional de TLS.
    - Ejecución en segundo plano.
    - Apagado limpio del servidor.

    Características clave:
    - Se ejecuta como hilo daemon para no bloquear el cierre de la aplicación.
    - No interactúa directamente con la UI, salvo mediante la referencia a ventana.
    - Diseñada para ser extremadamente robusta: nunca debe bloquear la app.

    NOTE:
        Este hilo existe porque `serve_forever` es una llamada bloqueante
        y no debe ejecutarse en el hilo principal de la interfaz.
    """

    def __init__(self, window, host, port, ssl_context=None):
        """
        Inicializa el hilo del servidor.

        Args:
            window: Referencia a la ventana principal de la aplicación.
                Se pasa al RequestHandler para permitir interacción controlada.
            host: Dirección IP o nombre de host donde escuchar.
            port: Puerto de escucha (convertido internamente a int).
            ssl_context: Contexto SSL ya configurado para HTTPS,
                o None para servir HTTP sin cifrado.

        IMPORTANT:
            El hilo se inicializa como daemon=True para asegurar que
            el cierre de la aplicación no quede bloqueado por el servidor.
        """
        super().__init__(daemon=True)

        self.window = window
        self.host = host
        self.port = int(port)
        self.ssl_context = ssl_context

        # Instancia del servidor HTTP una vez inicializado
        self.httpd = None

    def run(self):
        """
        Punto de entrada del hilo del servidor.

        Este método:
        - Crea el servidor HTTP.
        - Aplica TLS si se ha proporcionado un ssl_context.
        - Inicia el bucle `serve_forever`.

        WARNING:
            Este método contiene múltiples bloques defensivos try/except
            porque cualquier fallo en el servidor NO debe cerrar la aplicación.
        """
        try:
            # Crear el servidor HTTP con referencia a la ventana principal
            self.httpd = LauncherHTTPServer(
                (self.host, self.port),
                LauncherRequestHandler,
                self.window
            )

            try:
                # Configuración opcional de HTTPS
                if getattr(self, "ssl_context", None) is not None:
                    try:
                        self.httpd.socket = self.ssl_context.wrap_socket(
                            self.httpd.socket,
                            server_side=True,
                        )
                        LOGGER.info(
                            f"Servidor HTTPS escuchando en {self.host}:{self.port}"
                        )
                        try:
                            audit_store(
                                "server_started",
                                host=self.host,
                                port=self.port,
                                tls=True,
                            )
                        except Exception:
                            # Auditoría nunca debe romper el flujo
                            pass

                    except Exception as e:
                        # Fallback automático a HTTP si falla TLS
                        LOGGER.error(f"Fallo preparando TLS: {e}")
                        LOGGER.info(
                            f"Servidor HTTP escuchando en {self.host}:{self.port}"
                        )
                        try:
                            audit_store(
                                "server_started",
                                host=self.host,
                                port=self.port,
                                tls=False,
                            )
                        except Exception:
                            pass

                else:
                    # Servidor HTTP sin cifrado
                    LOGGER.info(
                        f"Servidor HTTP escuchando en {self.host}:{self.port}"
                    )
                    try:
                        audit_store(
                            "server_started",
                            host=self.host,
                            port=self.port,
                            tls=False,
                        )
                    except Exception:
                        pass

            except Exception:
                # Protección adicional para errores de inicialización
                LOGGER.exception(
                    "[auto] Exception capturada en ServerThread::run"
                )

            # Bucle principal del servidor (bloqueante)
            self.httpd.serve_forever(poll_interval=0.5)

        except Exception as e:
            try:
                LOGGER.error(f"Error en servidor: {e}")
            except Exception:
                LOGGER.exception(
                    "[auto] Exception capturada en ServerThread::run"
                )

    def stop(self):
        """
        Detiene el servidor y libera los recursos asociados.

        Este método:
        - Detiene el bucle `serve_forever`.
        - Cierra el socket del servidor.
        - Registra el evento en auditoría.
        - Limpia la referencia interna al servidor.

        IMPORTANT:
            Puede llamarse de forma segura incluso si el servidor
            no está completamente inicializado.
        """
        try:
            if self.httpd:
                self.httpd.shutdown()
                self.httpd.server_close()

            try:
                audit_store(
                    "server_stopped",
                    host=self.host,
                    port=self.port,
                )
            except Exception:
                # Auditoría nunca debe bloquear la detención
                pass

            self.httpd = None

        except Exception:
            LOGGER.exception(
                "[auto] Exception capturada en ServerThread::stop"
            )


def _mw_execute_external(self, p: Path):
    """
    Ejecuta un archivo externo de forma controlada.

    Este método centraliza la lógica de lanzamiento de archivos locales
    iniciados desde el servidor HTTP. El comportamiento depende de la
    extensión del archivo.

    Reglas generales:
    - Ejecutables (.exe, .com): se lanzan directamente.
    - Scripts (.bat, .cmd, .ps1, .py, etc.): se ejecutan mediante
      `_run_script` en modo oculto y sin bloqueo.
    - Otros tipos: se intenta abrir mediante el sistema operativo.

    Args:
        self:
            Instancia de MainWindow (inyectada dinámicamente).
        p (Path):
            Ruta al archivo a ejecutar.

    Returns:
        tuple:
            (ok: bool, mensaje: str)
    """
    try:
        suf = p.suffix.lower()

        # ------------------------------------------------------------------
        # Ejecutables binarios
        # ------------------------------------------------------------------
        if suf in ('.exe', '.com'):
            try:
                os.startfile(os.fspath(p))
                return (True, '')
            except Exception as e:
                # Fallback defensivo a shell_execute
                try:
                    shell_execute(str(p))
                    return (True, '')
                except Exception as e2:
                    return (False, str(e2))

        # ------------------------------------------------------------------
        # Scripts (ejecución indirecta)
        # ------------------------------------------------------------------
        if suf in ('.bat', '.cmd', '.ps1', '.py', '.vbs', '.vb', '.sh'):
            ok, err = self._run_script(
                str(p),
                args='',
                wait=False,
                timeout_sec=0,
                run_hidden=True
            )
            return (ok, err)

        # ------------------------------------------------------------------
        # Otros tipos de archivo: apertura por el SO
        # ------------------------------------------------------------------
        try:
            os.startfile(os.fspath(p))
            return (True, '')
        except Exception as e:
            try:
                shell_execute(str(p))
                return (True, '')
            except Exception as e3:
                return (False, str(e3))
    except Exception as e:
        # Fallback defensivo: cualquier excepción se devuelve como error
        return (False, str(e))


def _mw_notify_http_execution(self, path: str, status: str, error_text: str=''):
    """
    Notifica a la UI el resultado de una ejecución vía HTTP.

    Esta función muestra notificaciones en la bandeja del sistema
    dependiendo del estado de la ejecución y de la configuración del usuario.

    Soporta:
    - Filtrado por tipo de evento (ok / error / inexistente).
    - Supresión de notificaciones según modo configurado.
    - Agrupación temporal para evitar spam visual.

    Args:
        self:
            Instancia de MainWindow.
        path (str):
            Ruta ejecutada.
        status (str):
            Estado de la ejecución (ok, error, inexistente, etc.).
        error_text (str, optional):
            Texto de error asociado.

    Returns:
        None
    """
    try:
        mode = str(getattr(self, 'cfg', {}).get('server_notify_mode', 'all'))
        s = (status or '').strip().lower()

        # ------------------------------------------------------------------
        # Filtros de notificación según configuración
        # ------------------------------------------------------------------
        if mode == 'none':
            return
        if mode == 'only_ok' and s != 'ok':
            return
        if mode == 'only_errors' and s == 'ok':
            return

        # Inicialización diferida de cachés internas
        if not hasattr(self, '_notify_cache'):
            self._notify_cache = {}
        if not hasattr(self, '_notify_pending_tokens'):
            self._notify_pending_tokens = {}

        key = (path or '').strip().lower()
        from time import monotonic as _mono
        now = _mono()

        def _show_now_ui(stat: str):
            """
            Muestra inmediatamente una notificación en la bandeja.
            """
            try:
                title = 'Ejecución vía HTTP'
                st = (stat or '').strip().lower()

                if st == 'ok':
                    icon = QtWidgets.QSystemTrayIcon.Information
                    body = f'{path} -> Ok'
                elif st in ('inexistente', 'notfound', 'not_found'):
                    icon = QtWidgets.QSystemTrayIcon.Warning
                    body = f'{path} -> Inexistente'
                else:
                    icon = QtWidgets.QSystemTrayIcon.Critical
                    et = (error_text or '').strip()
                    if len(et) > 200:
                        et = et[:197] + '...'
                    body = f'{path} -> Error' + (f': {et}' if et else '')

                tray = getattr(self, 'tray', None)
                if tray and isinstance(tray, QtWidgets.QSystemTrayIcon):
                    tray.showMessage(title, body, icon, 5000)
            except Exception:
                LOGGER.exception(
                    '[auto] Exception capturada en _mw_notify_http_execution::_show_now_ui'
                )

        def _post_to_ui(fn):
            """
            Ejecuta una función de UI en el hilo principal.
            """
            try:
                QtCore.QTimer.singleShot(0, self, fn)
            except Exception:
                try:
                    fn()
                except Exception:
                    LOGGER.exception(
                        '[auto] Exception capturada en _mw_notify_http_execution::_post_to_ui'
                    )

        # ------------------------------------------------------------------
        # Caso OK: notificación inmediata
        # ------------------------------------------------------------------
        if s == 'ok':
            tok = self._notify_pending_tokens.get(key, 0) + 1
            self._notify_pending_tokens[key] = tok
            self._notify_cache[key] = ('ok', now)
            _post_to_ui(lambda: _show_now_ui('ok'))
            return

        # ------------------------------------------------------------------
        # Caso INEXISTENTE: notificación diferida (para evitar flicker)
        # ------------------------------------------------------------------
        if s in ('inexistente', 'notfound', 'not_found'):
            tok = self._notify_pending_tokens.get(key, 0) + 1
            self._notify_pending_tokens[key] = tok

            def _maybe_fire():
                try:
                    if self._notify_pending_tokens.get(key, 0) != tok:
                        return
                    prev = self._notify_cache.get(key)
                    if prev and prev[0] == 'ok' and (_mono() - prev[1] < 1.0):
                        return
                    _show_now_ui(s)
                except Exception:
                    LOGGER.exception(
                        '[auto] Exception capturada en _mw_notify_http_execution::_maybe_fire'
                    )

            try:
                QtCore.QTimer.singleShot(700, self, _maybe_fire)
            except Exception:
                QtCore.QTimer.singleShot(700, _maybe_fire)
            return

        # ------------------------------------------------------------------
        # Otros estados (error, etc.)
        # ------------------------------------------------------------------
        self._notify_cache[key] = (s, now)
        _post_to_ui(lambda: _show_now_ui(s))

    except Exception:
        LOGGER.exception('[auto] Exception capturada en _mw_notify_http_execution')


def _mw_server_settings(self):
    """
    Obtiene los parámetros básicos del servidor HTTP.

    Returns:
        dict:
            Diccionario con:
            - enabled (bool)
            - port (int)
            - local_only (bool)
    """
    return {
        'enabled': bool(self.cfg.get('server_enabled', False)),
        'port': int(self.cfg.get('server_port', 8080) or 8080),
        'local_only': bool(self.cfg.get('server_local_only', True)),
    }


def _mw_server_start(self):
    """
    Arranca el servidor HTTP según la configuración actual.

    Este método:
    - Garantiza valores por defecto.
    - Detiene cualquier servidor previo.
    - Inicializa throttling.
    - Configura TLS si está habilitado.
    - Lanza el servidor en un hilo dedicado.

    WARNING:
        Cualquier excepción se maneja de forma defensiva para evitar
        dejar la aplicación en estado inconsistente.
    """
    try:
        # Valores por defecto defensivos
        self.cfg.setdefault('server_enabled', False)
        self.cfg.setdefault('server_port', 8080)
        self.cfg.setdefault('server_local_only', True)
        self.cfg.setdefault('server_throttle_window_sec', 30)
        self.cfg.setdefault('server_throttle_base_ms', 100)
        self.cfg.setdefault('server_throttle_max_ms', 1000)
        self.cfg.setdefault('server_throttle_threshold', 3)
        self.cfg.setdefault('server_allowed_exts', list(SERVER_ALLOWED_EXTS))
    except Exception:
        LOGGER.exception('[auto] Exception capturada en _mw_server_start')

    # Detención previa del servidor (rearranque limpio)
    try:
        self.server_stop()
    except Exception:
        LOGGER.exception('[auto] Exception capturada en _mw_server_start')

    s = self.server_settings()
    if not s['enabled']:
        return

    # Reset del estado de throttling
    try:
        reset_throttle_state()
        LOGGER.info('[server] throttle/backoff state cleared on start')
    except Exception:
        LOGGER.exception(
            '[auto] Exception capturada al limpiar _THROTTLE_STATE en _mw_server_start'
        )

    # Configuración dinámica del módulo throttle
    try:
        from server import throttle
        throttle.THROTTLE_WINDOW_SEC = int(self.cfg.get('server_throttle_window_sec', 30) or 30)
        throttle.THROTTLE_BASE_MS = int(self.cfg.get('server_throttle_base_ms', 100) or 100)
        throttle.THROTTLE_MAX_MS = int(self.cfg.get('server_throttle_max_ms', 1000) or 1000)
        throttle.THROTTLE_THRESHOLD = int(self.cfg.get('server_throttle_threshold', 3) or 3)
        try:
            LOGGER.info(
                f"[server] backoff window={throttle.THROTTLE_WINDOW_SEC}s "
                f"base={throttle.THROTTLE_BASE_MS}ms "
                f"max={throttle.THROTTLE_MAX_MS}ms "
                f"threshold={throttle.THROTTLE_THRESHOLD}"
            )
        except Exception:
            LOGGER.exception('[auto] Exception capturada en _mw_server_start')
    except Exception:
        LOGGER.exception('[auto] Exception capturada en _mw_server_start')

    host = '127.0.0.1' if s['local_only'] else '0.0.0.0'
    ssl_context = None

    # ------------------------------------------------------------------
    # Configuración opcional de TLS
    # ------------------------------------------------------------------
    try:
        if bool(self.cfg.get('server_tls_enabled', False)):
            from pathlib import Path as _P
            certfile = (self.cfg.get('server_tls_certfile') or '').strip()
            keyfile = (self.cfg.get('server_tls_keyfile') or '').strip()
            minv = str(self.cfg.get('server_tls_min_version', 'TLS1.2')).upper()

            def _abs(p):
                if not p:
                    return None
                pp = _P(p)
                if not pp.is_absolute():
                    pp = (app_dir() / pp).resolve()
                return pp

            cf = _abs(certfile)
            kf = _abs(keyfile) if keyfile else None

            if not cf or not cf.exists():
                raise FileNotFoundError('No se encontró el certificado configurado')
            if kf and (not kf.exists()):
                raise FileNotFoundError('No se encontró la clave privada configurada')

            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            try:
                if minv in ('TLS1.3', 'TLS13', '1.3'):
                    ctx.minimum_version = ssl.TLSVersion.TLSv1_3
                else:
                    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
            except Exception:
                LOGGER.exception('[auto] Exception capturada en _mw_server_start')

            ctx.load_cert_chain(certfile=str(cf), keyfile=str(kf) if kf else None)
            try:
                ctx.set_ciphers('ECDHE+AESGCM:ECDHE+CHACHA20')
            except Exception:
                LOGGER.exception('[auto] Exception capturada en _mw_server_start')

            ssl_context = ctx
    except Exception as e:
        # Fallback defensivo: continuar en HTTP
        try:
            QtWidgets.QMessageBox.warning(
                self,
                'Servidor (TLS)',
                f'No se pudo habilitar TLS: {e}. Se iniciará en HTTP.'
            )
        except Exception:
            LOGGER.exception('[auto] Exception capturada en _mw_server_start')
        ssl_context = None

    # Lanzamiento del servidor en hilo dedicado
    try:
        self._server_thread = ServerThread(self, host, s['port'], ssl_context)
        self._server_thread.start()
    except Exception as e:
        try:
            QtWidgets.QMessageBox.warning(
                self,
                'Servidor',
                f'No se pudo iniciar el servidor: {e}'
            )
        except Exception:
            LOGGER.exception('[auto] Exception capturada en _mw_server_start')


def _mw_server_stop(self):
    """
    Detiene el servidor HTTP en ejecución (si existe).

    Incluye:
    - Parada ordenada del hilo del servidor.
    - Espera con timeout.
    - Limpieza del estado de throttling.
    """
    t = getattr(self, '_server_thread', None)
    if t is not None:
        try:
            t.stop()
        except Exception:
            LOGGER.exception('[auto] Exception capturada en _mw_server_stop')
        try:
            t.join(timeout=3.0)
        except Exception:
            LOGGER.exception('[auto] Exception capturada en _mw_server_stop')
        self._server_thread = None

    try:
        reset_throttle_state()
        LOGGER.info('[server] throttle/backoff state cleared on stop')
    except Exception:
        LOGGER.exception(
            '[auto] Exception capturada al limpiar _THROTTLE_STATE en _mw_server_stop'
        )


def _mw_init(self, *a, **k):
    """
    Hook de inicialización de MainWindow para integración HTTP.

    Se conecta al evento `aboutToQuit` para garantizar que el servidor
    se detenga al cerrar la aplicación.
    """
    _orig_init(self, *a, **k)
    try:
        app = QtWidgets.QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(lambda: self.server_stop())
        if bool(self.cfg.get('server_enabled', False)):
            self.server_start()
    except Exception:
        LOGGER.exception('[auto] Exception capturada en _mw_init')


def _mw_open_config(self):
    """
    Hook que reacciona a cambios de configuración del servidor.

    Si los parámetros relevantes cambian, se reinicia el servidor
    automáticamente para aplicar los nuevos valores.
    """

    def _build_tuple(cfg):
        """
        Construye una tupla comparable de configuración del servidor.

        Se utiliza para detectar cambios relevantes entre configuraciones.
        """
        try:
            return (
                bool(cfg.get('server_enabled', False)),
                int(cfg.get('server_port', 8080) or 8080),
                bool(cfg.get('server_local_only', True)),
                int(cfg.get('server_throttle_window_sec', 30) or 30),
                int(cfg.get('server_throttle_base_ms', 100) or 100),
                int(cfg.get('server_throttle_max_ms', 1000) or 1000),
                int(cfg.get('server_throttle_threshold', 3) or 3),
                bool(cfg.get('server_tls_enabled', False)),
                str(cfg.get('server_tls_certfile', '') or ''),
                str(cfg.get('server_tls_keyfile', '') or ''),
                str(cfg.get('server_tls_min_version', 'TLS1.2') or 'TLS1.2').upper(),
            )
        except Exception:
            return (False, 8080, True, 30, 100, 1000, 3, False, '', '', 'TLS1.2')

    try:
        old = _build_tuple(self.cfg)
    except Exception:
        old = (False, 8080, True, 30, 100, 1000, 3, False, '', '', 'TLS1.2')

    _orig_open_config(self)

    try:
        new = _build_tuple(self.cfg)
    except Exception:
        new = old

    if new != old:
        try:
            if new[0]:
                self.server_start()
            else:
                self.server_stop()
        except Exception:
            LOGGER.exception('[auto] Exception capturada en _mw_open_config')


def apply_mainwindow_http_patches(MainWindow):
    """
    Aplica dinámicamente a MainWindow la lógica del servidor HTTP.

    Este enfoque evita acoplar directamente MainWindow con el servidor,
    permitiendo mantener responsabilidades separadas.
    """

    # Métodos principales
    MainWindow._execute_external = _mw_execute_external
    MainWindow._notify_http_execution = _mw_notify_http_execution
    MainWindow.server_settings = _mw_server_settings
    MainWindow.server_start = _mw_server_start
    MainWindow.server_stop = _mw_server_stop

    # Hook de __init__ solo para cleanup, NO para arrancar explícito
    orig_init = MainWindow.__init__

    def _init(self, *a, **k):
        orig_init(self, *a, **k)
        app = QtWidgets.QApplication.instance()
        if app:
            app.aboutToQuit.connect(lambda: self.server_stop())

    MainWindow.__init__ = _init