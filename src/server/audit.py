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
server.audit

Sistema de auditoría en memoria para el servidor integrado de Heimdall Desktop.

Este módulo proporciona:
- Registro de eventos de auditoría en memoria.
- Acceso concurrente seguro mediante locks.
- Consulta de eventos recientes para diagnóstico o UI.

DIFERENCIA CLAVE CON LOGGING:
- El logging está orientado a diagnóstico técnico.
- La auditoría está orientada a trazabilidad de acciones relevantes
  (peticiones, accesos, operaciones sensibles, etc.).

IMPORTANTE:
- No persistente: los eventos viven solo en memoria.
- Diseño intencionadamente sencillo y robusto.
- Nunca debe romper el flujo del servidor.
"""

import time
import threading
from collections import deque
from typing import List, Dict

# Logger opcional para reportar errores internos de auditoría
try:
    import logging
    LOGGER = logging.getLogger(__name__)
except Exception:
    # Fallback defensivo si logging no está disponible
    LOGGER = None


# ---------------------------------------------------------------------------
# Estado interno del sistema de auditoría
# ---------------------------------------------------------------------------

# Lock global para acceso concurrente seguro
_AUDIT_LOCK = threading.Lock()

# Contador total de eventos de auditoría registrados
# No está limitado por el tamaño del buffer
_AUDIT_COUNTER = 0

# Buffer circular de eventos recientes de auditoría
# Limitado deliberadamente para evitar uso excesivo de memoria
_AUDIT_EVENTS = deque(maxlen=10000)


def audit_store(action: str, **fields) -> None:
    """
    Registra un evento de auditoría en memoria.

    Cada evento incluye:
    - Un timestamp UNIX.
    - Una acción principal (string).
    - Campos adicionales arbitrarios (keyword arguments).

    Args:
        action: Identificador de la acción auditada.
        **fields: Campos adicionales asociados al evento.

    IMPORTANT:
        - Este método NO debe lanzar excepciones hacia el exterior.
        - Cualquier error interno debe capturarse y silenciarse.
        - La auditoría nunca debe interferir con el flujo normal
          del servidor o la aplicación.
    """
    global _AUDIT_COUNTER

    # Timestamp defensivo: nunca confiar ciegamente en time.time()
    try:
        ts = time.time()
    except Exception:
        ts = 0.0

    # Registro base del evento
    record = {
        "ts": ts,
        "action": action,
    }

    # Añadir campos personalizados
    for k, v in (fields or {}).items():
        record[k] = v

    try:
        with _AUDIT_LOCK:
            _AUDIT_COUNTER += 1
            _AUDIT_EVENTS.append(record)

    except Exception:
        # En caso extremo, registrar el error solo si logging está disponible
        if LOGGER:
            LOGGER.exception("Error almacenando evento de auditoría")


def audit_latest(n: int) -> List[Dict]:
    """
    Devuelve los últimos eventos de auditoría almacenados en memoria.

    Args:
        n: Número de eventos a devolver.
           Si n <= 0, se devuelven todos los eventos disponibles
           dentro del buffer circular.

    Returns:
        Lista de diccionarios de eventos de auditoría.
    """
    with _AUDIT_LOCK:
        if not n or n <= 0:
            return list(_AUDIT_EVENTS)

        return list(_AUDIT_EVENTS)[-int(n):]


def audit_count() -> int:
    """
    Devuelve el número total de eventos de auditoría registrados.

    IMPORTANTE:
        Este contador refleja el número TOTAL de eventos desde
        el arranque de la aplicación, no solo los retenidos
        actualmente en memoria.

    Returns:
        Número total de eventos auditados.
    """
    with _AUDIT_LOCK:
        return int(_AUDIT_COUNTER)