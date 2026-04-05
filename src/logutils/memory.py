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
logutils.memory

Sistema de logging en memoria para diagnóstico y visualización en la UI.

Este módulo proporciona:
- Almacenamiento circular de eventos de log en memoria.
- Acceso seguro concurrente mediante locking.
- Un handler de logging estándar compatible con `logging`.

CARACTERÍSTICAS CLAVE:
- No depende de Qt.
- No realiza E/S en disco.
- Diseñado para ser extremadamente robusto.

IMPORTANTE:
- El sistema de logging NUNCA debe lanzar excepciones hacia afuera.
- Cualquier error interno debe ser atrapado y silenciado.
"""

import logging
import threading
import time
from collections import deque
from typing import List, Dict


# ---------------------------------------------------------------------------
# Estado interno del sistema de logging en memoria
# ---------------------------------------------------------------------------

# Lock global para garantizar acceso seguro desde múltiples hilos
_LOG_LOCK = threading.Lock()

# Contador total de eventos registrados (no limitado por el tamaño del buffer)
_LOG_COUNTER = 0

# Buffer circular de eventos recientes
# Se limita deliberadamente para evitar consumo de memoria descontrolado
_LOG_EVENTS = deque(maxlen=10000)


def _log_store(level: str, message: str) -> None:
    """
    Almacena un evento de log en memoria.

    Este método es interno y debe ser:
    - Rápido
    - Seguro frente a excepciones
    - Thread-safe

    Args:
        level: Nivel del log (INFO, WARNING, ERROR, etc.).
        message: Mensaje de log ya formateado.
    """
    global _LOG_COUNTER

    # Timestamp defensivo (nunca confiar en que time.time() no falle)
    try:
        ts = time.time()
    except Exception:
        ts = 0.0

    rec = {
        "ts": ts,
        "level": str(level or ""),
        "message": str(message or ""),
    }

    # Acceso protegido frente a concurrencia
    with _LOG_LOCK:
        _LOG_COUNTER += 1
        _LOG_EVENTS.append(rec)


def log_count() -> int:
    """
    Devuelve el número total de eventos de log registrados.

    IMPORTANTE:
        Este contador no está limitado por el tamaño del buffer,
        por lo que representa el número real de eventos emitidos
        desde el arranque de la aplicación.

    Returns:
        Número total de eventos registrados.
    """
    with _LOG_LOCK:
        return int(_LOG_COUNTER)


def log_latest(n: int | None = None) -> List[Dict]:
    """
    Devuelve los últimos eventos de log almacenados en memoria.

    Args:
        n: Número máximo de eventos a devolver.
           Si es None o <= 0, se devuelven todos los disponibles
           dentro del buffer circular.

    Returns:
        Lista de diccionarios con las claves:
        - ts: timestamp UNIX
        - level: nivel de log
        - message: mensaje formateado
    """
    with _LOG_LOCK:
        if not n or n <= 0:
            return list(_LOG_EVENTS)

        return list(_LOG_EVENTS)[-int(n):]


class MemoryLogHandler(logging.Handler):
    """
    Handler de logging que persiste los eventos en memoria.

    Este handler puede añadirse al root logger para:
    - Capturar logs recientes.
    - Visualizarlos desde la UI.
    - Facilitar diagnóstico sin depender de ficheros de log.

    NOTE:
        Este handler delega todo el almacenamiento real
        a funciones internas protegidas (`_log_store`).
    """

    def emit(self, record: logging.LogRecord) -> None:
        """
        Procesa un evento de logging y lo almacena en memoria.

        Args:
            record: Instancia de LogRecord generada por logging.

        WARNING:
            Este método JAMÁS debe lanzar excepciones hacia el exterior.
            Cualquier fallo debe ser silenciado para no romper logging global.
        """
        try:
            msg = self.format(record)
        except Exception:
            # Fallback si el formateador falla
            try:
                msg = record.getMessage()
            except Exception:
                msg = str(record)

        level = getattr(record, "levelname", "INFO")

        try:
            _log_store(level, msg)
        except Exception:
            # Fallo silencioso intencionado:
            # logging nunca debe romper la aplicación
            pass