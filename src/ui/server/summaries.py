# This file is part of Heimdall Desktop by Naidel.
#
# Copyright (C) 2024–2026 by Naidel
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
ui.server.summaries

Funciones puras de generación de resúmenes legibles de configuración
del servidor.

Este módulo contiene lógica **sin dependencias de interfaz gráfica**
para generar textos breves que resumen:
- Opciones generales del servidor HTTP/HTTPS.
- Configuración TLS.
- Parámetros de backoff / throttle.

IMPORTANT:
- Las funciones de este módulo NO modifican la configuración.
- NO acceden a UI.
- Están diseñadas para ser reutilizables desde cualquier parte
  de la aplicación (configuración, diálogos, paneles, etc.).
"""

# ------------------------------------------------------------
# ui/server/summaries.py -> Lógica de resúmenes
# ------------------------------------------------------------

from typing import Iterable


# Extensiones permitidas por defecto para ejecución vía servidor
SERVER_ALLOWED_EXTS = {'.exe', '.com', '.bat', '.cmd', '.vbs', '.ps1', '.py'}


def server_opts_summary(cfg: dict) -> str:
    """
    Devuelve un resumen legible de las opciones del servidor HTTP/HTTPS.

    El resumen incluye, si están disponibles:
    - Puerto de escucha.
    - Alcance (solo local o red).
    - Estado de whitelist.
    - Extensiones permitidas.
    - Política de notificaciones.

    Args:
        cfg: Diccionario de configuración del servidor.

    Returns:
        Cadena legible con el resumen de opciones,
        o un placeholder si ocurre algún error.

    NOTE:
        Esta función es deliberadamente tolerante a errores:
        cualquier excepción devuelve un resumen genérico.
    """
    try:
        try:
            port = int(cfg.get('server_port', 8080) or 8080)
        except Exception:
            port = 8080

        scope = (
            'Solo local'
            if bool(cfg.get('server_local_only', True))
            else 'Red'
        )
        wl = 'sí' if bool(cfg.get('server_whitelist_base', False)) else 'no'

        exts = cfg.get('server_allowed_exts')
        if not exts:
            exts = list(SERVER_ALLOWED_EXTS)

        if isinstance(exts, (list, tuple, set)):
            exts_txt = ','.join(
                sorted({
                    (e if str(e).startswith('.') else '.' + str(e)).lower()
                    for e in exts
                })
            )
        else:
            exts_txt = str(exts)

        mode = str(cfg.get('server_notify_mode', 'all') or 'all')
        label_map = {
            'all': 'Todas',
            'none': 'Ninguna',
            'only_ok': 'Solo ok',
            'only_errors': 'Solo errores',
        }
        notif = label_map.get(mode, 'Todas')

        return (
            f'Puerto: {port}; '
            f'Alcance: {scope}; '
            f'Whitelist: {wl}; '
            f'Exts: {exts_txt}; '
            f'Notif: {notif}'
        )

    except Exception:
        # Fallback defensivo: nunca romper la UI
        return 'Puerto: ?; Alcance: ?; Whitelist: ?; Exts: ?; Notif: ?'


def tls_opts_summary(cfg: dict) -> str:
    """
    Devuelve un resumen legible de las opciones TLS.

    Muestra:
    - Nombre del archivo de certificado.
    - Nombre del archivo de clave privada.
    - Versión mínima TLS configurada.

    Args:
        cfg: Diccionario de configuración del servidor.

    Returns:
        Cadena legible con el resumen TLS,
        o marcadores si ocurre un error.

    WARNING:
        No valida la existencia ni el contenido de los archivos,
        solo los muestra de forma informativa.
    """
    try:
        import os

        cert = (cfg.get('server_tls_certfile') or '').strip()
        key = (cfg.get('server_tls_keyfile') or '').strip()
        mv = str(
            cfg.get('server_tls_min_version', 'TLS1.2')
            or 'TLS1.2'
        ).upper()

        cert_b = os.path.basename(cert) if cert else '(ninguno)'
        key_b = os.path.basename(key) if key else '(ninguna)'

        return f'Cert: {cert_b}; Clave: {key_b}; MinTLS: {mv}'

    except Exception:
        # Fallback defensivo para fallos inesperados
        return 'Cert: ?; Clave: ?; MinTLS: ?'


def throttle_summary(params: dict) -> str:
    """
    Devuelve un resumen legible de la configuración de backoff / throttle.

    Incluye:
    - Ventana temporal.
    - Retardo base.
    - Retardo máximo.
    - Umbral de errores.

    Args:
        params: Diccionario con parámetros de throttle.

    Returns:
        Cadena legible con el resumen,
        o un mensaje de error si los valores no son válidos.

    NOTE:
        Se asume que los valores existen y son numéricos;
        cualquier fallo se maneja de forma segura.
    """
    try:
        return (
            f"Ventana: {int(params['window_sec'])} s; "
            f"Base: {int(params['base_ms'])} ms; "
            f"Máx: {int(params['max_ms'])} ms; "
            f"Umbral: {int(params['threshold'])}"
        )
    except Exception:
        return 'Backoff: (valores no válidos)'
