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
Gestión centralizada de temas y apariencia (DEFINITIVO).

Este módulo contiene toda la lógica relacionada con:
- Definición de paletas de color.
- Construcción dinámica de hojas de estilo (QSS).
- Aplicación de temas a nivel de aplicación y ventana.
- Integración con el tema del sistema anfitrión (Windows).
- Reaplicación dinámica del tema en caliente.
- Personalización avanzada de la barra de título en Windows.

IMPORTANT:
    Este módulo define la apariencia global de la aplicación.
    Cambios en este archivo impactan directamente en toda la UI.

NOTE:
    La arquitectura está pensada para aislar completamente
    la lógica de tema del resto de la aplicación.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Optional

from PySide6 import QtGui, QtWidgets

from config.service import get_cfg_service
from logutils.setup import get_logger
# Logger del módulo (configurado globalmente por la aplicación)
LOGGER = get_logger()

# ============================================================
# Constantes públicas de tema
# ============================================================

# Identificadores de tema utilizados en la configuración
THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"
THEME_HIGH_CONTRAST = "high_contrast"
THEME_HOST_SYSTEM = "host_system"

# ============================================================
# Paletas internas
# ============================================================

# Paleta clara (light)
_PALETTE_LIGHT: Dict[str, str | int] = {
    "bg": "#f5f6f7",
    "fg": "#202124",
    "panel_bg": "#f1f3f4",
    "border": "#dadce0",
    "border_w": 1,
    "radius": 4,
    "btn_radius": 6,
    "input_bg": "#ffffff",
    "focus_border": "#0b57d0",
    "btn_bg": "#e8eaed",
    "btn_hover": "#f1f3f4",
    "btn_pressed": "#e2e3e5",
    "menu_bg": "#ffffff",
    "menu_sel_bg": "#e8f0fe",
    "menu_sel_fg": "#202124",
    "view_bg": "#ffffff",
    "sel_bg": "#1a73e8",
    "sel_fg": "#ffffff",
    "hover_bg": "#e8f0fe",
    "progress_bg": "#ffffff",
    "progress_chunk": "#1a73e8",
    "separator": "#dadce0",
}

# Paleta oscura (dark)
_PALETTE_DARK: Dict[str, str | int] = {
    "bg": "#202124",
    "fg": "#e8eaed",
    "panel_bg": "#17191c",
    "border": "#5f6368",
    "border_w": 1,
    "radius": 4,
    "btn_radius": 6,
    "input_bg": "#303134",
    "focus_border": "#8ab4f8",
    "btn_bg": "#2b2d30",
    "btn_hover": "#3c4043",
    "btn_pressed": "#34373a",
    "menu_bg": "#2b2d30",
    "menu_sel_bg": "#1a73e8",
    "menu_sel_fg": "#ffffff",
    "view_bg": "#2b2d30",
    "sel_bg": "#1a73e8",
    "sel_fg": "#ffffff",
    "hover_bg": "#3c4043",
    "progress_bg": "#2b2d30",
    "progress_chunk": "#8ab4f8",
    "separator": "#202124",
}

# Paleta de alto contraste (accesibilidad)
_PALETTE_HC: Dict[str, str | int] = {
    "bg": "#000000",
    "fg": "#ffff00",
    "panel_bg": "#000000",
    "border": "#00ffff",
    "border_w": 2,
    "radius": 0,
    "btn_radius": 0,
    "input_bg": "#000000",
    "focus_border": "#ff00ff",
    "btn_bg": "#000000",
    "btn_hover": "#111111",
    "btn_pressed": "#222222",
    "menu_bg": "#000000",
    "menu_sel_bg": "#00ffff",
    "menu_sel_fg": "#000000",
    "view_bg": "#000000",
    "sel_bg": "#ff00ff",
    "sel_fg": "#000000",
    "hover_bg": "#00ffff",
    "progress_bg": "#000000",
    "progress_chunk": "#ff00ff",
    "separator": "#00ffff",
}

# ============================================================
# QSS base
# ============================================================

# Plantilla base de hoja de estilo (QSS)
# Se rellena dinámicamente a partir de la paleta activa
_QSS_TEMPLATE = """
QWidget {{
    background: {bg};
    color: {fg};
}}

QMainWindow, QDialog {{
    background: {bg};
}}

QLineEdit, QComboBox, QTextEdit, QPlainTextEdit {{
    background: {input_bg};
    color: {fg};
    border: {border_w}px solid {border};
    border-radius: {radius}px;
    padding: 4px;
}}

QLineEdit:focus, QComboBox:focus {{
    border: {border_w}px solid {focus_border};
}}

QPushButton {{
    background: {btn_bg};
    border: {border_w}px solid {border};
    border-radius: {btn_radius}px;
    padding: 6px 10px;
}}

QPushButton:hover {{
    background: {btn_hover};
}}

QPushButton:pressed {{
    background: {btn_pressed};
}}

QTreeWidget {{
    background: {view_bg};
    border: {border_w}px solid {border};
}}

QTreeWidget::item:selected {{
    background: {sel_bg};
    color: {sel_fg};
}}

QProgressBar {{
    border: {border_w}px solid {border};
    background: {progress_bg};
    height: 10px;
}}

QProgressBar::chunk {{
    background-color: {progress_chunk};
}}

QTabWidget::pane {{
    border: 1px solid {border};
}}

QTabBar::tab {{
    background: {panel_bg};
    color: {fg};
    border: 1px solid {border};
    padding: 6px 10px;
}}

QTabBar::tab:selected {{
    background: {bg};
}}

QTabBar::tab:hover {{
    background: {hover_bg};
}}

QHeaderView::section {{
    background-color: {panel_bg};
    color: {fg};
    border-top: 0;
    border-left: 0;
    border-right: {border_w}px solid {border};
    border-bottom: {border_w}px solid {border};
    padding: 6px;
}}

QHeaderView::section:hover {{
    background-color: {hover_bg};
}}

QTreeWidget::header,
QTableView::header {{
    background-color: {panel_bg};
}}
""".strip()

def _load_qss_from_path(path: Optional[str]) -> str:
    """
    Carga un fichero QSS desde una ruta absoluta.
    Devuelve una cadena vacía si hay cualquier problema.
    """
    try:
        if not path:
            return ""

        if not os.path.isfile(path):
            LOGGER.warning(f"QSS no encontrado: {path}")
            return ""

        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    except Exception as e:
        LOGGER.exception(f"Error cargando QSS desde {path}")
        return ""

def _load_system_qss() -> str:
    """
    Carga el fichero styles.qss desde el directorio principal
    de la aplicación y devuelve su contenido como texto.

    Si el fichero no existe o hay algún problema, devuelve
    una cadena vacía (no rompe la aplicación).
    """
    try:
        # Directorio donde está main.py
        if getattr(sys, 'frozen', False):
            # Ejecutable empaquetado (PyInstaller, etc.)
            base_dir = os.path.dirname(sys.executable)
        else:
            # Ejecución normal desde código fuente
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        qss_path = os.path.join(base_dir, "styles.qss")

        if not os.path.isfile(qss_path):
            return ""

        with open(qss_path, "r", encoding="utf-8") as f:
            return f.read()

    except Exception:
        return ""

def _build_qss(palette: Dict[str, str | int]) -> str:
    """
    Construye una hoja de estilo QSS a partir de una paleta.

    Args:
        palette (dict):
            Diccionario de colores y parámetros visuales.

    Returns:
        str: Hoja de estilo QSS lista para aplicar.
    """
    return _QSS_TEMPLATE.format(**palette)

# ============================================================
# Utilidades específicas de Windows
# ============================================================

def _is_windows_dark_mode() -> bool:
    """
    Detecta si Windows está configurado en modo oscuro.

    Returns:
        bool: True si el sistema usa modo oscuro, False en caso contrario.
    """
    if os.name != "nt":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return val == 0
    except Exception:
        # Código defensivo: cualquier fallo asume modo claro
        return False


def _hex_to_colorref(hex_color: Optional[str]) -> Optional[int]:
    """
    Convierte un color hexadecimal (#RRGGBB) a formato COLORREF de Windows.

    Args:
        hex_color (str | None):
            Color en formato hexadecimal.

    Returns:
        int | None: Valor COLORREF o None si no es válido.
    """
    if not hex_color or not hex_color.startswith("#"):
        return None
    try:
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        return (b << 16) | (g << 8) | r
    except Exception:
        return None


def _is_windows_11() -> bool:
    """
    Detecta si el sistema es Windows 11.

    Returns:
        bool: True si es Windows 11, False en otro caso.
    """
    if os.name != "nt":
        return False
    try:
        return sys.getwindowsversion().build >= 22000
    except Exception:
        return False

# ============================================================
# ThemeManager (API pública)
# ============================================================

class ThemeManager:
    """
    Gestor centralizado de temas.

    Proporciona una API estática para aplicar y reaplicar temas
    a nivel de aplicación y ventana, manteniendo una única fuente
    de verdad para la apariencia visual.
    """

    # --------------------------------------------------------
    # Aplicación inicial del tema
    # --------------------------------------------------------

    @staticmethod
    def apply_theme(app: QtWidgets.QApplication, cfg: dict) -> None:
        """
        Aplica el tema configurado a la aplicación.

        Args:
            app (QApplication):
                Instancia de la aplicación.
            cfg (dict):
                Diccionario de configuración global.
        """
        theme = cfg.get("theme", THEME_SYSTEM)

        if theme == THEME_SYSTEM:
            from config.service import get_cfg_service

            cfg = get_cfg_service()
            qss_path = cfg.get("system_qss_path")

            qss = _load_qss_from_path(qss_path)

            if qss:
                QtWidgets.QApplication.instance().setStyleSheet(qss)
                LOGGER.info(f"Tema QSS cargado desde fichero: {qss_path}")
            else:
                QtWidgets.QApplication.instance().setStyleSheet("")
                LOGGER.info("Tema SYSTEM activo pero sin QSS válido")
            return

        # ❌ Bloquear host system en Windows 10
        if theme == THEME_HOST_SYSTEM and os.name == "nt" and not _is_windows_11():
            if _is_windows_dark_mode():
                theme = THEME_DARK  # fallback seguro
            else:
                theme = THEME_LIGHT

        if theme == THEME_LIGHT:
            app.setStyleSheet(_build_qss(_PALETTE_LIGHT))
        elif theme == THEME_DARK:
            app.setStyleSheet(_build_qss(_PALETTE_DARK))
        elif theme == THEME_HIGH_CONTRAST:
            app.setStyleSheet(_build_qss(_PALETTE_HC))
        elif theme == THEME_HOST_SYSTEM:
            app.setStyleSheet("")
            ThemeManager._apply_host_palette(app)
        else:
            app.setStyleSheet("")

    # --------------------------------------------------------

    @staticmethod
    def _apply_host_palette(app: QtWidgets.QApplication) -> None:
        if not _is_windows_dark_mode():
            return
        pal = QtGui.QPalette()

        # Fondos
        pal.setColor(QtGui.QPalette.Window, QtGui.QColor(32, 33, 36))
        pal.setColor(QtGui.QPalette.Base, QtGui.QColor(48, 49, 52))
        pal.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(43, 45, 48))

        # Textos
        pal.setColor(QtGui.QPalette.WindowText, QtGui.QColor(232, 234, 237))
        pal.setColor(QtGui.QPalette.Text, QtGui.QColor(232, 234, 237))
        pal.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(232, 234, 237))

        # Botones
        pal.setColor(QtGui.QPalette.Button, QtGui.QColor(48, 49, 52))

        # Selección
        pal.setColor(QtGui.QPalette.Highlight, QtGui.QColor(138, 180, 248))
        pal.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(0, 0, 0))

        # Relieve / bordes
        pal.setColor(QtGui.QPalette.Dark, QtGui.QColor(24, 25, 28))
        pal.setColor(QtGui.QPalette.Mid, QtGui.QColor(60, 63, 65))
        pal.setColor(QtGui.QPalette.Light, QtGui.QColor(90, 90, 90))
        pal.setColor(QtGui.QPalette.Shadow, QtGui.QColor(0, 0, 0))

        app.setPalette(pal)

    # --------------------------------------------------------
    # Reaplicación en caliente (CLAVE)
    # --------------------------------------------------------

    @staticmethod
    def reapply_theme(
        app: QtWidgets.QApplication,
        window: QtWidgets.QWidget,
        cfg: dict,
    ) -> None:
        """
        Reaplica el tema en caliente sin reiniciar la aplicación.

        Fuerza el repolish completo de todos los widgets existentes.

        IMPORTANT:
            Este método es crítico para cambios dinámicos de tema.
        """
        ThemeManager.apply_theme(app, cfg)
        ThemeManager.apply_titlebar(window, cfg)

        # Forzar repintado completo de todos los widgets
        for w in app.allWidgets():
            try:
                w.style().unpolish(w)
                w.style().polish(w)
                w.update()
            except Exception:
                # Código defensivo: un fallo puntual no debe afectar al resto
                pass

    # --------------------------------------------------------
    # Barra de título (Windows)
    # --------------------------------------------------------

    @staticmethod
    def apply_titlebar(window: QtWidgets.QWidget, cfg: dict) -> None:
        """
        Aplica personalización avanzada de la barra de título en Windows.

        Permite:
        - Sincronizar modo oscuro con el sistema.
        - Cambiar color de fondo y texto de la barra.

        NOTE:
            Esta funcionalidad solo está disponible en Windows.
        """
        if os.name != "nt":
            return

        try:
            from ctypes import windll, byref, c_int
            from ctypes.wintypes import HWND, DWORD

            hwnd = HWND(int(window.winId()))

            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
            DWMWA_CAPTION_COLOR = 35
            DWMWA_TEXT_COLOR = 36

            # Sincronización automática con el modo oscuro del sistema
            if cfg.get("titlebar_align_dark_mode"):
                val = c_int(1 if _is_windows_dark_mode() else 0)
                windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWORD(DWMWA_USE_IMMERSIVE_DARK_MODE),
                    byref(val),
                    DWORD(4)
                )

            # Color de fondo personalizado
            bg = _hex_to_colorref(cfg.get("titlebar_color"))
            if bg is not None:
                val = c_int(bg)
                windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWORD(DWMWA_CAPTION_COLOR),
                    byref(val),
                    DWORD(4)
                )

            # Color de texto personalizado
            fg = _hex_to_colorref(cfg.get("titlebar_text_color"))
            if fg is not None:
                val = c_int(fg)
                windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    DWORD(DWMWA_TEXT_COLOR),
                    byref(val),
                    DWORD(4)
                )

        except Exception:
            # Código defensivo: fallo silencioso si la API no está disponible
            pass