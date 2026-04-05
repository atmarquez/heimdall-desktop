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
ui.config.dialog

Diálogo principal de Configuración de Heimdall Desktop.

Este módulo define la clase `ConfigDialog`, que implementa el diálogo
central de configuración basado en pestañas.

Responsabilidades principales:
- Orquestar las pestañas de configuración (Generales, Apariencia, etc.).
- Gestionar la aplicación y guardado de cambios.
- Integrarse con el sistema de ayuda contextual.
- Emitir notificaciones cuando la configuración cambia.

IMPORTANTE:
- Este diálogo NO aplica directamente los cambios visuales en caliente.
- Solo consolida la configuración y la persiste.
- La aplicación real de algunos ajustes se delega al MainWindow.
"""

# ------------------------------------------------------------
# ui/config/dialog.py -> Clase ConfigDialog
# ------------------------------------------------------------
# Diálogo de "Configuración"

from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import QDialog

from ui.helpers import HelpableDialogMixin
from ui.help import open_help_page

from config.service import save_config

from ui.config.general import GeneralConfigTab
from ui.config.appearance import AppearanceConfigTab
from ui.config.quick_buttons import QuickButtonsConfigTab
from ui.config.scripts import ScriptConfigTab
from ui.config.import_export import ImportExportConfigTab
from ui.config.server import ServerConfigTab
from ui.config.log import LogConfigTab
from ui.config.about import AboutTab

from ui.server.summaries import (
    server_opts_summary,
    tls_opts_summary,
)


class ConfigDialog(HelpableDialogMixin, QDialog):
    """
    Diálogo principal de configuración con estructura por pestañas.

    Este diálogo centraliza todas las opciones configurables
    de la aplicación y las agrupa en pestañas especializadas.

    Pestañas incluidas:
    - Generales
    - Apariencia
    - Botones rápidos
    - Scripts
    - Avanzado (Importar / Exportar)
    - Servidor
    - Log
    - Acerca de…

    NOTE:
        La clase hereda de `HelpableDialogMixin` para integrar
        ayuda contextual dependiente de la pestaña activa.
    """

    #: Señal emitida cuando se aplican cambios de configuración
    applied = QtCore.Signal(dict)

    def _topic_for_current_tab(self) -> str:
        """
        Devuelve el identificador de ayuda asociado a la pestaña actual.

        Este método se usa para determinar qué página de ayuda
        debe abrirse al pulsar el botón de ayuda.

        Returns:
            Identificador de topic de ayuda.
        """
        try:
            txt = (
                self.tabs.tabText(self.tabs.currentIndex())
                or ''
            ).strip().lower()
        except Exception:
            txt = ''

        mapping = {
            'generales': 'config_general',
            'apariencia': 'config_apariencia',
            'botones rápidos': 'config_botones_rapidos',
            'scripts': 'config_scripts',
            'avanzado': 'config_avanzado',
            'auditoría': 'config_auditoria',
            'servidor': 'config_servidor',
            'log': 'config_log',
        }

        return mapping.get(txt, 'config_general')

    def _on_help_clicked(self):
        """
        Abre la página de ayuda correspondiente a la pestaña activa.

        Usa un fallback a la página principal si ocurre algún error.
        """
        try:
            open_help_page(self._topic_for_current_tab())
        except Exception:
            open_help_page('index')

    def __init__(self, cfg, parent=None):
        """
        Inicializa el diálogo de configuración.

        Args:
            cfg: Diccionario de configuración actual de la aplicación.
            parent: Widget padre (normalmente MainWindow).
        """
        super().__init__(parent)

        self.cfg = cfg

        # Layout principal (UNO SOLO)
        main_layout = QtWidgets.QVBoxLayout(self)

        # Tabs (UNA SOLA VEZ)
        self.tabs = QtWidgets.QTabWidget(self)
        main_layout.addWidget(self.tabs)

        # --------------------------------------------------
        # Pestañas de configuración
        # --------------------------------------------------
        self.general_tab = GeneralConfigTab(self.cfg, self)
        self.general_tab.populate_from_cfg()
        self.tabs.addTab(self.general_tab, 'Generales')

        self.appearance_tab = AppearanceConfigTab(self.cfg, self)
        self.appearance_tab.populate_from_cfg()
        self.tabs.addTab(self.appearance_tab, 'Apariencia')

        self.quick_buttons_tab = QuickButtonsConfigTab(self.cfg, self)
        self.quick_buttons_tab.populate_from_cfg()
        self.tabs.addTab(self.quick_buttons_tab, 'Botones rápidos')

        self.scripts_tab = ScriptConfigTab(self.cfg, self)
        self.scripts_tab.populate_from_cfg()
        self.tabs.addTab(self.scripts_tab, 'Scripts')

        # Pestaña Avanzado (Import / Export)
        self.import_export_tab = ImportExportConfigTab(self)
        self.import_export_tab.populate_from_cfg()
        self.import_export_tab.config_imported.connect(
            self._on_config_imported
        )
        self.tabs.addTab(self.import_export_tab, 'Avanzado')

        self.server_tab = ServerConfigTab(
            self,
            self.cfg,
            server_opts_summary_fn=server_opts_summary,
            tls_opts_summary_fn=tls_opts_summary,
        )
        self.tabs.addTab(self.server_tab.widget, 'Servidor')

        self.log_tab = LogConfigTab(self.tabs, self.cfg)
        self.tabs.addTab(self.log_tab, 'Log')

        self.about_tab = AboutTab(self.tabs)
        self.tabs.addTab(self.about_tab, 'Acerca de…')

        # --------------------------------------------------
        # Botonera inferior
        # --------------------------------------------------
        self._button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok
            | QtWidgets.QDialogButtonBox.Cancel
        )
        main_layout.addWidget(self._button_box)

        self._button_box.accepted.connect(self._on_apply_clicked)
        self._button_box.accepted.connect(self.accept)
        self._button_box.rejected.connect(self.reject)

        apply_btn = self._button_box.addButton(
            'Aplicar cambios',
            QtWidgets.QDialogButtonBox.ApplyRole
        )
        apply_btn.clicked.connect(self._on_apply_clicked)

        # Botón de ayuda contextual
        self._install_help_button(self._button_box)

        self.setWindowTitle('Configuración')

    def _on_config_imported(self, cfg: dict):
        """
        Aplica inmediatamente una configuración importada.

        Args:
            cfg: Diccionario de configuración importado.
        """
        try:
            self.cfg = cfg
            save_config(cfg)
            self.applied.emit(cfg)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Error",
                f"No se pudo aplicar la configuración importada:\n{e}",
            )

    def _request_restart(self):
        """
        **TEMPORAL**

        Solicita el reinicio de la aplicación.

        NOTE:
            Este método se mantendrá hasta que el reinicio
            sea gestionado exclusivamente desde MainWindow.
        """
        try:
            self.parent()._restart_app()
        except Exception:
            QtWidgets.QMessageBox.information(
                self,
                'Reinicio',
                'Guarda los cambios y reinicia manualmente la aplicación.'
            )

    def _on_apply_clicked(self):
        """
        Aplica los cambios actuales de todas las pestañas.

        Este método:
        - Recoge valores de cada pestaña.
        - Actualiza el diccionario de configuración.
        - Guarda la configuración persistente.
        - Emite la señal `applied`.
        """
        try:
            self.general_tab.apply_to_cfg(self.cfg)
            self.appearance_tab.apply_to_cfg(self.cfg)
            self.quick_buttons_tab.apply_to_cfg(self.cfg)
            self.scripts_tab.apply_to_cfg(self.cfg)
            self.import_export_tab.apply_to_cfg(self.cfg)

            if hasattr(self, "server_tab"):
                self.server_tab.apply_to_cfg(self.cfg)

            if hasattr(self, "log_tab"):
                self.log_tab.apply_to_cfg(self.cfg)

            save_config(self.cfg)
            self.applied.emit(self.cfg)

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Aplicar cambios",
                f"No se pudieron aplicar los cambios:\n{e}"
            )