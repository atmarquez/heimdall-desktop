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
ui.server.patches

Parches (monkey patches) para integrar el servidor HTTP con la aplicación.

Este módulo aplica modificaciones dinámicas a clases del servidor HTTP
para:
- Integrar correctamente el servidor con MainWindow.
- Extender el sistema de auditoría.
- Registrar eventos de auditoría tanto en memoria como en log.

IMPORTANT:
- Este módulo utiliza *monkey patching* de forma deliberada.
- Debe importarse **una sola vez** durante la inicialización.
- No define clases ni funciones públicas de uso general.
"""

# ------------------------------------------------------------
# ui/server/patches.py
# ------------------------------------------------------------
# Código de parches HTTP / auditoría
# (apply_server_patches y _patched__audit)

import logging
from server.audit import audit_store
from server.http import (
    LauncherRequestHandler,
    apply_mainwindow_http_patches,
)

LOGGER = logging.getLogger(__name__)


def _patched__audit(self, action, **fields):
    """
    Implementación parcheada del método interno `_audit`
    de `LauncherRequestHandler`.

    Este método:
    - Almacena el evento de auditoría en el backend correspondiente.
    - Registra el evento en el sistema de logging.

    Args:
        self: Instancia de LauncherRequestHandler.
        action: Identificador de la acción auditada.
        **fields: Campos adicionales asociados al evento.

    NOTE:
        Cualquier excepción durante la auditoría se ignora
        explícitamente para no interferir con el flujo HTTP.
    """
    try:
        audit_store(action, **fields)
    except Exception:
        # Fallo de auditoría nunca debe romper el servidor
        pass

    try:
        parts = [f'{k}={fields[k]}' for k in fields]
        LOGGER.info(
            '[audit] ' + action + ' ' + ' '.join(parts)
        )
    except Exception:
        # Fallback de logging defensivo
        try:
            LOGGER.exception(
                '[auto] Exception capturada en '
                'LauncherRequestHandler._audit parcheado'
            )
        except Exception:
            pass


def apply_server_patches(MainWindowClass):
    """
    Aplica los parches necesarios para integrar el servidor HTTP
    con la aplicación principal.

    Este método:
    - Parchea la integración HTTP con MainWindow.
    - Sustituye el método `_audit` del request handler
      por la versión extendida definida en este módulo.

    Args:
        MainWindowClass: Clase MainWindow de la aplicación.

    IMPORTANT:
        - Este método debe llamarse **después** de definir MainWindow.
        - No debe llamarse múltiples veces.
        - El orden de parcheo es significativo.
    """
    # Parchear integración HTTP -> MainWindow
    apply_mainwindow_http_patches(MainWindowClass)

    # Parchear auditoría del request handler
    try:
        LauncherRequestHandler._audit = _patched__audit
    except Exception:
        # Fallback defensivo: no impedir arranque por fallo de parche
        pass
        