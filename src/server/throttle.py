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
Mecanismo de throttling (limitación de frecuencia) para Heimdall Desktop.

Este módulo implementa un sistema sencillo de *backoff progresivo*
basado en errores recientes, utilizado principalmente por el servidor HTTP
para mitigar abusos o comportamientos erróneos repetidos.

Características:
- Ventana temporal configurable.
- Umbral de activación configurable.
- Penalización exponencial controlada por límites.
- Estado completamente en memoria (no persistente).

IMPORTANT:
    Este sistema no pretende ser criptográficamente seguro ni distribuido.
    Su objetivo es únicamente reducir impactos locales y abuso accidental.

NOTE:
    Los parámetros globales pueden ser sobrescritos dinámicamente
    desde otros módulos (por ejemplo, al arrancar el servidor).
"""

import time
from typing import Dict, List, Tuple

# ------------------------------------------------------------------
# Logging opcional
# ------------------------------------------------------------------
# NOTE:
#   El módulo funciona correctamente aunque logging no esté disponible.
try:
    import logging
    LOGGER = logging.getLogger(__name__)
except Exception:
    LOGGER = None

# ------------------------------------------------------------------
# Estado interno del throttling
# ------------------------------------------------------------------
# Diccionario que asocia una clave (ej. IP|User-Agent) con una lista
# de timestamps de errores recientes.
_THROTTLE_STATE: Dict[str, List[float]] = {}

# ------------------------------------------------------------------
# Configuración (sobrescribible desde fuera del módulo)
# ------------------------------------------------------------------

# Ventana de tiempo (en segundos) para considerar errores recientes
THROTTLE_WINDOW_SEC = 30

# Penalización base (en milisegundos)
THROTTLE_BASE_MS = 100

# Penalización máxima (en milisegundos)
THROTTLE_MAX_MS = 1000

# Número de errores a partir del cual se empieza a penalizar
THROTTLE_THRESHOLD = 3


def reset_throttle_state():
    """
    Reinicia completamente el estado interno del throttling.

    Se eliminan todos los registros de errores acumulados.

    NOTE:
        Este método se utiliza típicamente al arrancar o detener
        el servidor HTTP para evitar heredar penalizaciones antiguas.
    """
    _THROTTLE_STATE.clear()
    if LOGGER:
        LOGGER.info("Estado de throttle reiniciado")


def throttle_penalty_for(key: str, now: float) -> Tuple[int, int]:
    """
    Calcula la penalización actual para una clave dada.

    La penalización depende del número de errores recientes dentro
    de la ventana temporal configurada.

    Política:
    - Hasta THROTTLE_THRESHOLD errores: sin penalización.
    - A partir del umbral: penalización exponencial basada en
      THROTTLE_BASE_MS, con tope en THROTTLE_MAX_MS.

    Args:
        key (str):
            Identificador lógico del origen (normalmente IP|User-Agent).
        now (float):
            Timestamp actual (time.time()).

    Returns:
        Tuple[int, int]:
            - penalty_ms: Penalización en milisegundos.
            - count: Número de errores recientes contabilizados.
    """
    lst = _THROTTLE_STATE.get(key, [])

    # Se filtran únicamente los errores dentro de la ventana temporal
    lst = [t for t in lst if now - t <= THROTTLE_WINDOW_SEC]
    count = len(lst)

    penalty_ms = 0
    if count >= THROTTLE_THRESHOLD:
        steps = count - THROTTLE_THRESHOLD
        try:
            penalty_ms = min(
                int(THROTTLE_MAX_MS),
                int(THROTTLE_BASE_MS) * (2 ** max(0, steps)),
            )
        except Exception:
            # Código defensivo: fallback simple si algo falla
            penalty_ms = int(THROTTLE_BASE_MS)

    # Se actualiza el estado con la lista filtrada
    _THROTTLE_STATE[key] = lst
    return penalty_ms, count


def record_error(key: str, now: float):
    """
    Registra un nuevo error para una clave dada.

    El error se almacena con timestamp actual y se descartan
    automáticamente los registros fuera de la ventana temporal.

    Args:
        key (str):
            Identificador lógico del origen (normalmente IP|User-Agent).
        now (float):
            Timestamp actual (time.time()).
    """
    lst = _THROTTLE_STATE.get(key, [])
    lst.append(now)

    # Limpieza de errores antiguos
    _THROTTLE_STATE[key] = [
        t for t in lst if now - t <= THROTTLE_WINDOW_SEC
    ]