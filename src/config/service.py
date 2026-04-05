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
config.service

Servicio centralizado de configuración persistente para Heimdall Desktop.

Este módulo se encarga de:
- Cargar y guardar la configuración desde `config.json`.
- Proporcionar valores por defecto coherentes.
- Resolver rutas relativas respecto al directorio de la aplicación.
- Exponer una API estable y reutilizable para el resto del proyecto.

IMPORTANTE:
- Este módulo NO debe depender de la UI.
- Se permite el uso opcional de Qt únicamente para generar el icono
  por defecto y solo como último recurso.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional


# ------------------------------------------------------------
# Utilidades base
# ------------------------------------------------------------

def app_dir() -> Path:
    """
    Devuelve el directorio base de la aplicación.

    Este método es compatible con:
    - Ejecución normal desde código fuente.
    - Ejecución empaquetada mediante PyInstaller.

    Returns:
        Ruta base de la aplicación como pathlib.Path.
    """
    # Cuando se ejecuta como binario (PyInstaller),
    # sys.executable apunta al ejecutable final.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent

    # En desarrollo, usamos la raíz del proyecto.
    return Path(__file__).resolve().parents[1]


def default_app_title() -> str:
    """
    Devuelve el título por defecto de la aplicación.

    Returns:
        Título de la aplicación como string.
    """
    return "Heimdall Desktop by Naidel"


# ------------------------------------------------------------
# ConfigService
# ------------------------------------------------------------

class ConfigService:
    """
    Servicio que centraliza el acceso a la configuración persistente
    de la aplicación (`config.json`).

    Responsabilidades:
    - Cargar configuración desde disco.
    - Aplicar valores por defecto cuando faltan claves.
    - Resolver rutas relativas.
    - Guardar cambios de forma segura.

    Esta clase representa la fuente única de verdad de la
    configuración durante la ejecución.
    """

    #: Nombre del fichero de configuración.
    CONFIG_FILENAME = "config.json"

    def __init__(self) -> None:
        """
        Inicializa el servicio de configuración.

        - Calcula el directorio base de la aplicación.
        - Determina la ruta del fichero `config.json`.
        - Carga la configuración (o valores por defecto).
        """
        self._app_dir: Path = app_dir()
        self._config_path: Path = self._app_dir / self.CONFIG_FILENAME
        self.data: Dict[str, Any] = self._load()

    # --------------------------------------------------------
    # Acceso básico
    # --------------------------------------------------------

    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor de configuración.

        Args:
            key: Clave de configuración.
            default: Valor por defecto si la clave no existe.

        Returns:
            Valor de la configuración o el valor por defecto.
        """
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """
        Establece un valor de configuración en memoria.

        NOTE:
            No guarda automáticamente en disco.
            Para persistir cambios, llamar a `save()`.

        Args:
            key: Clave de configuración.
            value: Valor a asignar.
        """
        self.data[key] = value

    # --------------------------------------------------------
    # Persistencia
    # --------------------------------------------------------

    def save(self) -> None:
        """
        Guarda la configuración actual en disco (`config.json`).

        - Crea el directorio si no existe.
        - Escribe JSON con indentación y UTF-8.
        """
        self._config_path.parent.mkdir(parents=True, exist_ok=True)

        with self._config_path.open("w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    # --------------------------------------------------------
    # Resolución de rutas
    # --------------------------------------------------------

    def resolve_path(self, p: Optional[str | Path]) -> Optional[Path]:
        """
        Convierte una ruta relativa en absoluta respecto al directorio de la app.

        Args:
            p: Ruta relativa o absoluta (str o Path).

        Returns:
            Ruta absoluta como Path o None si no se proporciona entrada.
        """
        if not p:
            return None

        path = Path(p)

        if not path.is_absolute():
            path = (self._app_dir / path).resolve()

        return path

    # --------------------------------------------------------
    # Rutas comunes
    # --------------------------------------------------------

    def log_file_path(self) -> Path:
        """
        Devuelve la ruta al fichero de log.

        Returns:
            Ruta absoluta al fichero de log.
        """
        p = self.get("log_file_path", "launcher.log")
        return self.resolve_path(p) or (self._app_dir / "launcher.log")

    def styles_qss_path(self) -> Optional[Path]:
        """
        Devuelve la ruta al fichero styles.qss si existe.

        Returns:
            Ruta al fichero QSS o None si no existe.
        """
        p = self.resolve_path("styles.qss")
        return p if p and p.exists() else None

    def app_icon_path(self) -> Path:
        """
        Devuelve la ruta al icono de la aplicación.

        - Usa el icono configurado si existe.
        - Garantiza siempre un icono válido, creando uno por defecto si es necesario.

        Returns:
            Ruta absoluta al icono (Path).
        """
        custom = (self.get("app_icon_path") or "").strip()

        if custom:
            p = self.resolve_path(custom)
            if p and p.exists():
                return p

        # Icono por defecto
        res_dir = self._app_dir / "resources"
        res_dir.mkdir(exist_ok=True)

        ico = res_dir / "app.ico"

        if not ico.exists():
            self._create_default_icon(ico)

        return ico

    # --------------------------------------------------------
    # Internos
    # --------------------------------------------------------

    def _load(self) -> Dict[str, Any]:
        """
        Carga el fichero de configuración desde disco.

        Si el fichero no existe o está corrupto, se devuelven
        los valores por defecto.

        Returns:
            Diccionario de configuración.
        """
        defaults = self._defaults()

        if not self._config_path.exists():
            return defaults.copy()

        try:
            with self._config_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

                if isinstance(data, dict):
                    merged = defaults.copy()
                    merged.update(data)
                    return merged
        except Exception:
            # Falla silenciosamente para evitar romper el arranque
            pass

        return defaults.copy()

    def _defaults(self) -> Dict[str, Any]:
        """
        Devuelve el conjunto de valores por defecto de la aplicación.

        Returns:
            Diccionario con claves y valores por defecto.
        """
        return {
            "base_dir": ".\\apps",
            "window": {
                "width": 520,
                "height": 640,
                "x": None,
                "y": None,
            },
            "start_minimized": True,
            "minimize_to_tray": True,
            "launch_and_minimize": True,
            "view_mode": "grouped",
            "startup_behavior": "grouped",
            "root_category_name": "Sin categoría",
            "app_title": default_app_title(),
            "app_icon_path": "",
            "theme": "system",
            "web_search_url": "https://www.bing.com",
            "log_enabled": True,
            "log_file_path": "launcher.log",
            "autostart_enabled": False,
            "autostart_method": "registry",
            "autostart_minimized": True,
            "quick_buttons": [],
            "scheduled_tasks": [],
        }

    def _create_default_icon(self, path: Path) -> None:
        """
        Crea un icono básico por defecto si no existe ninguno.

        NOTE:
            - Usa Qt SOLO en este punto.
            - Este método es opcional y defensivo.
            - Fallos al crear el icono no deben impedir el arranque.
        """
        try:
            from PySide6 import QtGui, QtCore

            pixmap = QtGui.QPixmap(64, 64)
            pixmap.fill(QtGui.QColor("#4f4f4f"))

            painter = QtGui.QPainter(pixmap)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)

            painter.setBrush(QtGui.QColor("#00acc1"))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRoundedRect(8, 8, 48, 48, 10, 10)

            painter.setPen(QtGui.QColor("white"))
            painter.setFont(QtGui.QFont("Segoe UI", 24, QtGui.QFont.Bold))
            painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, "P")

            painter.end()

            pixmap.save(str(path), "ICO")
        except Exception:
            # Fallo silencioso intencionado
            pass


# ---------------------------------------------------------------------------
# API compatible con main_legacy.py
# ---------------------------------------------------------------------------

def load_config() -> dict:
    """
    Carga la configuración de la aplicación.

    Wrapper de compatibilidad que devuelve directamente
    el diccionario de configuración.

    Returns:
        Diccionario de configuración.
    """
    return get_cfg_service().data


def save_config(cfg: dict) -> None:
    """
    Guarda la configuración de la aplicación.

    Args:
        cfg: Diccionario de configuración a persistir.
    """
    service = get_cfg_service()
    service.data = cfg if isinstance(cfg, dict) else {}
    service.save()


# ------------------------------------------------------------
# Singleton helpers
# ------------------------------------------------------------

_CONFIG_SERVICE: Optional[ConfigService] = None


def get_config_service() -> ConfigService:
    """
    Devuelve una instancia singleton de ConfigService.

    Returns:
        Instancia de ConfigService.
    """
    global _CONFIG_SERVICE

    if _CONFIG_SERVICE is None:
        _CONFIG_SERVICE = ConfigService()

    return _CONFIG_SERVICE


def get_config() -> Dict[str, Any]:
    """
    Devuelve el diccionario de configuración actual.

    Returns:
        Diccionario de configuración.
    """
    return get_config_service().data


def save_config(cfg: Dict[str, Any]) -> None:
    """
    Guarda la configuración persistente.

    Args:
        cfg: Diccionario de configuración.
    """
    svc = get_config_service()
    svc.data = cfg if isinstance(cfg, dict) else {}
    svc.save()


# ---------------------------------------------------------------------------
# Singleton de configuración (API compatible con main_legacy)
# ---------------------------------------------------------------------------

_CFG_SERVICE_SINGLETON: ConfigService | None = None


def get_cfg_service() -> ConfigService:
    """
    Devuelve la instancia singleton principal de ConfigService.

    Esta función existe para mantener compatibilidad con código legacy
    que ya espera esta API.

    Returns:
        Instancia singleton de ConfigService.
    """
    global _CFG_SERVICE_SINGLETON

    if _CFG_SERVICE_SINGLETON is None:
        _CFG_SERVICE_SINGLETON = ConfigService()

    return _CFG_SERVICE_SINGLETON