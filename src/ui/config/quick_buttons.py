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
ui.config.quick_buttons

Pestaña de configuración de “Botones rápidos” de Heimdall Desktop.

Este módulo implementa una pestaña simple cuya responsabilidad es:
- Mostrar información básica sobre los botones rápidos.
- Abrir el diálogo dedicado a su configuración.
- Integrarse con el sistema general de configuración.

IMPORTANTE:
- La edición real de los botones rápidos se realiza en un diálogo aparte.
- Esta pestaña actúa únicamente como lanzador de dicho diálogo.
- No mantiene estado visual persistente propio.
"""

# ------------------------------------------------------------
# ui/config/quick_buttons.py -> Clase QuickButtonsConfigTab
# ------------------------------------------------------------
# Pestaña “Botones rápidos” dentro de "Configuración"

from PySide6 import QtWidgets
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton

from ui.dialogs.quick_buttons import QuickButtonsDialog


class QuickButtonsConfigTab(QWidget):
    """
    Pestaña de configuración de los botones rápidos.

    Esta clase proporciona una interfaz mínima que permite:
    - Mostrar una breve descripción del propósito de los botones rápidos.
    - Abrir un diálogo específico para editarlos.

    NOTE:
        La lógica completa de edición y validación se encuentra
        en `QuickButtonsDialog`. Esta pestaña solo lo invoca.
    """

    def __init__(self, cfg: dict, parent=None):
        """
        Inicializa la pestaña de configuración de botones rápidos.

        Args:
            cfg: Diccionario de configuración actual de la aplicación.
            parent: Widget padre (normalmente el diálogo de Configuración).
        """
        super().__init__(parent)
        self.cfg = cfg
        self._build_ui()

    def _build_ui(self):
        """
        Construye la interfaz gráfica de la pestaña.

        La UI se compone de:
        - Un texto explicativo.
        - Un botón para abrir el diálogo de configuración.
        """
        layout = QVBoxLayout(self)

        hint = QLabel(
            'Configura accesos rápidos a carpetas comunes o personalizadas.',
            self
        )
        layout.addWidget(hint)

        btn_qb = QPushButton('Configurar botones rápidos…', self)
        btn_qb.clicked.connect(self._open_quick_buttons_dialog)
        layout.addWidget(btn_qb)

        # Espaciador inferior para mantener la UI alineada arriba
        layout.addStretch(1)

    def _open_quick_buttons_dialog(self):
        """
        Abre el diálogo de configuración de botones rápidos.

        Si el usuario acepta los cambios, la configuración resultante
        se guarda directamente en el diccionario `cfg`.
        """
        dlg = QuickButtonsDialog(self.cfg, self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self.cfg['quick_buttons'] = dlg.result_qbs()

    def populate_from_cfg(self):
        """
        Sincroniza la interfaz con la configuración actual.

        NOTE:
            Esta pestaña no tiene estado visual persistente,
            por lo que no es necesario realizar ninguna acción.
        """
        pass

    def apply_to_cfg(self, cfg: dict):
        """
        Aplica la configuración de la pestaña al diccionario cfg.

        NOTE:
            La configuración ya se escribe cuando se acepta el diálogo,
            por lo que aquí no se realizan cambios adicionales.
        """
        return cfg