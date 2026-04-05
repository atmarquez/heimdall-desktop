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
Diálogo de importación mediante arrastrar y soltar.

Este módulo define el diálogo `DropImportDialog`, que se muestra cuando
el usuario arrastra archivos o carpetas a la aplicación y es necesario
decidir cómo incorporarlos.

Opciones disponibles:
- Crear un acceso directo (.lnk) apuntando al elemento original.
- Copiar el elemento dentro de la carpeta de destino.

IMPORTANT:
    Este diálogo NO ejecuta la operación directamente.
    Solo recoge la decisión del usuario.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QRadioButton
)
from PySide6 import QtWidgets

from ui.helpers import HelpableDialogMixin


class DropImportDialog(HelpableDialogMixin, QDialog):
    """
    Diálogo mostrado al arrastrar archivos o carpetas.

    Permite al usuario elegir entre:
    - Crear un acceso directo al elemento original.
    - Copiar físicamente el elemento en la carpeta destino.

    NOTE:
        Integra ayuda contextual mediante `HelpableDialogMixin`.
    """

    #: Tema de ayuda asociado a este diálogo.
    help_topic = 'drop_import'

    def __init__(self, parent=None, count=1):
        """
        Inicializa el diálogo de importación por arrastre.

        Args:
            parent (QWidget, optional):
                Widget padre.
            count (int):
                Número de elementos arrastrados.
        """
        super().__init__(parent)
        self.setWindowTitle('Importar elementos')

        layout = QVBoxLayout(self)

        # ---------------------------------------------------------
        # Mensaje dinámico según número de elementos
        # ---------------------------------------------------------
        msg = QLabel(
            '¿Cómo quieres agregar el elemento?'
            if count == 1
            else f'¿Cómo quieres agregar los {count} elementos?'
        )
        layout.addWidget(msg)

        # ---------------------------------------------------------
        # Opciones disponibles
        # ---------------------------------------------------------
        self.rb_shortcut = QRadioButton(
            'Crear acceso directo (.lnk) hacia el elemento original'
        )
        self.rb_copy = QRadioButton(
            'Copiar el elemento en la carpeta de destino'
        )

        # Opción por defecto
        self.rb_shortcut.setChecked(True)

        layout.addWidget(self.rb_shortcut)
        layout.addWidget(self.rb_copy)

        # ---------------------------------------------------------
        # Botonera estándar + ayuda
        # ---------------------------------------------------------
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok |
            QtWidgets.QDialogButtonBox.Cancel,
            parent=self
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        # Inserta botón Ayuda y atajo F1
        self._install_help_button(btns)

        layout.addWidget(btns)

    def choice(self) -> str:
        """
        Devuelve la opción elegida por el usuario.

        Returns:
            str:
                - 'shortcut' si se eligió crear acceso directo.
                - 'copy' si se eligió copiar el elemento.
        """
        return 'shortcut' if self.rb_shortcut.isChecked() else 'copy'
