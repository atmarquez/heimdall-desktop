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
logutils.setup

Configuración centralizada del sistema de logging de Heimdall Desktop.

Este módulo se encarga de:
- Inicializar logging según la configuración (`config.json`).
- Definir un logger global del proyecto.
- Añadir filtros de redacción de información sensible.
- Integrar QMessageBox con logging.
- Registrar excepciones no capturadas.

IMPORTANTE:
- El sistema de logging NUNCA debe romper la aplicación.
- Todos los errores internos de logging deben capturarse y silenciarse.
- Este módulo se ejecuta muy temprano en el arranque.
"""

from __future__ import annotations

import app_meta
import logging
import sys
from pathlib import Path
from typing import Optional, Dict, Any


# ------------------------------------------------------------
# Logger global del proyecto
# ------------------------------------------------------------

# El nombre del logger se basa en el nombre oficial de la aplicación.
# Esto permite:
# - Identificar fácilmente los logs.
# - Agruparlos correctamente en herramientas externas.
_LOGGER_NAME = app_meta.APP_NAME

LOGGER = logging.getLogger(_LOGGER_NAME)

# Ruta absoluta del fichero de log activo.
# Se expone solo a modo informativo.
LOG_FILE_ABS: Optional[str] = None


def get_logger() -> logging.Logger:
    """
    Devuelve el logger principal del proyecto.

    Returns:
        Instancia de logging.Logger asociada a Heimdall Desktop.
    """
    return LOGGER


# ------------------------------------------------------------
# Filtro de redacción de tokens sensibles
# ------------------------------------------------------------

class _RedactTokenFilter(logging.Filter):
    """
    Filtro de logging que redacta automáticamente tokens sensibles.

    Ejemplo:
        Antes:  token=abcdef123
        Después: token=<redacted>

    Se aplica a TODOS los logs escritos en fichero.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Procesa un LogRecord sustituyendo tokens sensibles si existen.

        Args:
            record: Registro de logging original.

        Returns:
            Siempre True para permitir que el log continúe.

        WARNING:
            Este método NUNCA debe lanzar excepciones.
        """
        try:
            import html
            import re

            msg = str(record.getMessage())

            # Desescapar entidades HTML por si llegan mensajes codificados
            msg = html.unescape(msg)

            # Redactar tokens en formatos comunes (case-insensitive)
            msg = re.sub(
                r"(?i)(token=)([^&\s]+)",
                r"\1<redacted>",
                msg,
            )

            # Reescribir el mensaje ya redactado
            record.msg = msg
            record.args = ()

        except Exception:
            # Logging jamás debe bloquearse por errores internos
            pass

        return True


# ------------------------------------------------------------
# Configuración de logging desde config.json
# ------------------------------------------------------------

def setup_logging_from_cfg(cfg: Dict[str, Any]) -> None:
    """
    Inicializa y configura el sistema de logging según la configuración.

    Args:
        cfg: Diccionario de configuración cargado desde config.json.

    IMPORTANT:
        Esta función DEBE llamarse una sola vez durante el arranque.
        Re‑ejecutarla puede provocar duplicación de handlers.
    """
    global LOG_FILE_ABS

    try:
        enabled = bool(cfg.get("log_enabled", True))

        root = logging.getLogger()

        # IMPORTANTE:
        # Eliminamos solo FileHandler previos para evitar duplicados,
        # pero respetamos otros handlers (consola, memoria, etc.).
        for h in list(root.handlers):
            if isinstance(h, logging.FileHandler):
                root.removeHandler(h)

        # Nivel máximo: el filtrado se hace por handler
        root.setLevel(logging.DEBUG)

        # Logging deshabilitado explícitamente
        if not enabled:
            root.addHandler(logging.NullHandler())
            LOG_FILE_ABS = None
            return

        log_path = _resolve_log_path(cfg)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        LOG_FILE_ABS = str(log_path)

        handler = logging.FileHandler(
            LOG_FILE_ABS,
            encoding="utf-8",
            mode="a",
        )

        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
        handler.setFormatter(formatter)

        # Aplicar filtro de redacción
        handler.addFilter(_RedactTokenFilter())

        root.addHandler(handler)

    except Exception as e:
        # Fallback defensivo: informar por stderr, nunca romper la app
        try:
            sys.stderr.write(
                f"[logging] No se pudo configurar logging: {e}\n"
            )
        except Exception:
            pass


def _resolve_log_path(cfg: Dict[str, Any]) -> Path:
    """
    Resuelve la ruta absoluta del fichero de log.

    Args:
        cfg: Diccionario de configuración.

    Returns:
        Ruta absoluta del fichero de log.
    """
    from config.service import get_config_service

    try:
        svc = get_config_service()
        return svc.log_file_path()
    except Exception:
        # Fallback seguro si la configuración falla
        return Path.cwd() / "launcher.log"


# ------------------------------------------------------------
# Integración con QMessageBox (Qt)
# ------------------------------------------------------------

def install_qmessagebox_logging() -> None:
    """
    Redirige llamadas a QMessageBox hacia el sistema de logging.

    Cada diálogo mostrado al usuario se registra automáticamente:
    - information  → INFO
    - warning      → WARNING
    - critical     → ERROR
    - question     → INFO

    NOTE:
        Esta integración es opcional y depende de PySide6.
    """
    try:
        from PySide6 import QtWidgets

        # Guardar referencias originales
        orig_info = QtWidgets.QMessageBox.information
        orig_warn = QtWidgets.QMessageBox.warning
        orig_crit = QtWidgets.QMessageBox.critical
        orig_question = QtWidgets.QMessageBox.question

        def _info(parent, title, text, *a, **k):
            LOGGER.info("%s: %s", title, text)
            return orig_info(parent, title, text, *a, **k)

        def _warn(parent, title, text, *a, **k):
            LOGGER.warning("%s: %s", title, text)
            return orig_warn(parent, title, text, *a, **k)

        def _crit(parent, title, text, *a, **k):
            LOGGER.error("%s: %s", title, text)
            return orig_crit(parent, title, text, *a, **k)

        def _question(parent, title, text, *a, **k):
            LOGGER.info("%s: %s", title, text)
            return orig_question(parent, title, text, *a, **k)

        # Monkey‑patch seguro de QMessageBox
        QtWidgets.QMessageBox.information = _info
        QtWidgets.QMessageBox.warning = _warn
        QtWidgets.QMessageBox.critical = _crit
        QtWidgets.QMessageBox.question = _question

    except Exception:
        # Logging nunca debe romper la aplicación
        pass


# ------------------------------------------------------------
# Hook global de excepciones no capturadas
# ------------------------------------------------------------

def install_excepthook() -> None:
    """
    Registra en el log todas las excepciones no capturadas.

    Sustituye sys.excepthook por una versión que:
    - Registra la excepción en el log.
    - Luego delega al manejador original de Python.
    """

    def _excepthook(exc_type, exc_value, exc_tb):
        try:
            LOGGER.exception(
                "Excepción no capturada",
                exc_info=(exc_type, exc_value, exc_tb),
            )
        except Exception:
            pass

        # Llamar siempre al hook original como fallback
        try:
            sys.__excepthook__(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    sys.excepthook = _excepthook


# ------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------

def get_log_file_path() -> str | None:
    """
    Devuelve la ruta absoluta del fichero de log actual.

    Returns:
        Ruta del fichero de log o None si el logging está deshabilitado.
    """
    return LOG_FILE_ABS