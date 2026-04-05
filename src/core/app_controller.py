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
Controlador principal de la aplicación.

Este módulo contiene el controlador central responsable de coordinar
el comportamiento de la aplicación que NO pertenece a la UI directamente.

El AppController actúa como nexo entre la interfaz (MainWindow) y la
lógica de aplicación propiamente dicha.

Responsabilidades principales:
- Aplicar cambios de configuración en caliente (sin reinicio).
- Coordinar el ciclo de vida del servidor interno.
- Ejecutar scripts de pre-inicio y post-salida.
- Centralizar la lógica de comportamiento en tiempo de ejecución.

IMPORTANT:
    Este módulo NO debe crear widgets ni layouts.
    Toda interacción visual se delega explícitamente en MainWindow.

Filosofía de diseño:
    - MainWindow: UI, eventos, señales, interacción con el usuario.
    - AppController: lógica de aplicación, decisiones y orquestación.
"""

from PySide6 import QtWidgets
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt

from config.service import default_app_title, get_cfg_service
from logutils.setup import get_logger

# Logger del módulo (configurado globalmente por la aplicación)
LOGGER = get_logger()


class AppController:
    """
    Controlador principal de la aplicación.

    Esta clase encapsula toda la lógica de comportamiento que no pertenece
    directamente a la interfaz gráfica.

    Responsabilidades:
        - Aplicar cambios de configuración en vivo.
        - Decidir cuándo arrancar, parar o reiniciar el servidor.
        - Ejecutar scripts asociados al ciclo de vida de la aplicación.

    NOTE:
        Esta clase no conoce ni maneja widgets.
        El acceso a la UI se realiza exclusivamente a través de MainWindow.
    """

    def __init__(self, main_window):
        """
        Inicializa el AppController.

        Args:
            main_window: Instancia de MainWindow. Se utiliza para delegar
                acciones que requieren acceso a la UI o a componentes
                integrados (servidor, bandeja del sistema, scripts, etc.).
        """
        self.main_window = main_window

    def apply_config_live(self, old_cfg, new_cfg):
        """
        Aplica en caliente los cambios de configuración que NO requieren
        reinicio de la aplicación.

        IMPORTANT:
            - Este método NO persiste configuración.
            - La persistencia debe realizarse antes de invocar este método.
            - Las decisiones de reinicio pertenecen al código llamador.

        Args:
            old_cfg (dict): Configuración anterior (snapshot).
            new_cfg (dict): Configuración nueva ya validada y aplicada.
        """

        mw = self.main_window

        # ------------------------------------------------------------------
        # Captura del estado previo del servidor.
        #
        # NOTE:
        #   No se modifica mw.cfg aquí; se asume que el llamador
        #   ya ha actualizado la configuración activa.
        # ------------------------------------------------------------------
        old_srv = mw._server_params_tuple(old_cfg)

        # ------------------------------------------------------------------
        # Obtención del estado nuevo del servidor.
        # ------------------------------------------------------------------
        new_srv = mw._server_params_tuple(new_cfg)

        # ------------------------------------------------------------------
        # Aplicación del tema y de la barra de título.
        #
        # WARNING:
        #   Este bloque es defensivo. Cualquier excepción se captura
        #   para evitar que la UI quede en estado inconsistente.
        # ------------------------------------------------------------------
        try:
            from themes.theme_manager import ThemeManager
            app = QtWidgets.QApplication.instance()
            if app:
                ThemeManager.reapply_theme(app, mw, mw.cfg)
                ThemeManager.apply_titlebar(mw, mw.cfg)
        except Exception:
            LOGGER.exception("Error aplicando tema en vivo")

        # ------------------------------------------------------------------
        # Actualización del título de la ventana y del icono de la aplicación.
        #
        # IMPORTANT:
        #   La ruta del icono se resuelve a través de config.service.
        # ------------------------------------------------------------------
        try:
            title = mw.cfg.get("app_title") or default_app_title()
            mw.setWindowTitle(title)

            icon_path = str(get_cfg_service().app_icon_path())
            icon = QIcon(icon_path)
            mw.setWindowIcon(icon)

            # Código opcional: actualización del icono de la bandeja
            if hasattr(mw, "tray") and mw.tray:
                mw.tray.setIcon(icon)
                mw.tray.setToolTip(title)
        except Exception:
            LOGGER.exception("Error aplicando título/icono")

        # ------------------------------------------------------------------
        # Actualizaciones adicionales de la interfaz dependientes de config.
        # ------------------------------------------------------------------
        try:
            mw._apply_titlebar_colors()
            mw._refresh_ui_from_cfg()
        except Exception:
            LOGGER.exception("Error actualizando UI")

        # ------------------------------------------------------------------
        # Gestión del ciclo de vida del servidor.
        #
        # NOTE:
        #   Se comparan tuplas completas de parámetros para decidir
        #   si es necesario actuar (start/stop).
        # ------------------------------------------------------------------
        LOGGER.info("[Controller] Server cfg old=%s new=%s", old_srv, new_srv)

        try:
            if old_srv != new_srv:
                LOGGER.info("[Controller] server config CHANGED -> applying")

                # El primer elemento indica si el servidor debe estar activo
                if new_srv[0]:
                    mw.server_start()
                else:
                    mw.server_stop()
            else:
                LOGGER.info("[Controller] Server config unchanged")

            # Código opcional: sincronización de scheduler si existe
            if hasattr(mw, "scheduler"):
                mw.scheduler.cfg = mw.cfg

        except Exception:
            LOGGER.exception("Error aplicando cambios de servidor")

    def run_pre_start_script(self):
        """
        Ejecuta el script configurado para el arranque de la aplicación.

        Este método debe llamarse durante el inicio de la app, una vez
        cargada la configuración y antes de que el usuario interactúe.

        NOTE:
            Los errores de ejecución se registran, pero NO deben impedir
            que la aplicación continúe su arranque.
        """
        mw = self.main_window
        cfg = mw.cfg

        if not cfg.get('pre_start_script_enabled', False):
            return

        try:
            mw._run_script(
                script_path=cfg.get('pre_start_script', ''),
                args=cfg.get('pre_start_args', ''),
                wait=cfg.get('pre_start_wait', True),
                timeout_sec=cfg.get('pre_start_timeout_sec', 0),
                run_hidden=cfg.get('pre_start_run_hidden', True),
            )
        except Exception:
            LOGGER.exception("Error ejecutando script pre-inicio")

    def run_post_exit_script(self):
        """
        Ejecuta el script configurado para la salida de la aplicación.

        Este método debe llamarse durante el cierre de la app, antes
        de terminar el proceso.

        WARNING:
            Dependiendo de la configuración, este script puede bloquear
            temporalmente el cierre. Los errores se registran pero no deben
            provocar un fallo en la salida de la aplicación.
        """
        mw = self.main_window
        cfg = mw.cfg

        if not cfg.get('post_exit_script_enabled', False):
            return

        try:
            mw._run_script(
                script_path=cfg.get('post_exit_script', ''),
                args=cfg.get('post_exit_args', ''),
                wait=cfg.get('post_exit_wait', True),
                timeout_sec=cfg.get('post_exit_timeout_sec', 0),
                run_hidden=cfg.get('post_exit_run_hidden', True),
            )
        except Exception:
            LOGGER.exception("Error ejecutando script post-salida")