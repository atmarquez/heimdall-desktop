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
ui.dialogs.create_url_dialog

Diálogo para crear accesos web (.url) con nombre y dirección URL.

Este módulo implementa un diálogo sencillo pero robusto que permite:
- Definir un nombre legible para el acceso web.
- Introducir o pegar una URL válida.
- Validar la entrada antes de aceptar el diálogo.

IMPORTANTE:
- Este diálogo SOLO recopila y valida datos.
- La creación real del archivo .url se realiza fuera de esta clase.
"""

# ------------------------------------------------------------
# ui/dialogs/create_url_dialog.py -> Clase CreateUrlDialog
# ------------------------------------------------------------

from PySide6 import QtGui, QtWidgets
from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton, QFormLayout

from ui.helpers import HelpableDialogMixin
from ui.help import open_help_page


class CreateUrlDialog(HelpableDialogMixin, QDialog):
    """
    Diálogo para crear un acceso web (.url).

    Este diálogo forma parte de la interfaz gráfica y se integra
    con el sistema de ayuda contextual mediante HelpableDialogMixin.

    Permite:
    - Introducir el nombre del acceso.
    - Introducir o pegar la URL.
    - Validar que los datos sean consistentes antes de aceptar.

    NOTE:
        La validación es deliberadamente sencilla para no bloquear
        URLs especiales (mailto:, file:, etc.).
    """

    #: Identificador del tema de ayuda contextual
    help_topic = 'create_url'

    def __init__(
        self,
        parent=None,
        suggested_name='',
        prefill_url='',
        prefill_name=''
    ):
        """
        Inicializa el diálogo de creación de acceso web.

        Args:
            parent: Widget padre de Qt (opcional).
            suggested_name: Nombre sugerido basado en el contexto.
            prefill_url: URL inicial a rellenar automáticamente.
            prefill_name: Nombre inicial a rellenar automáticamente.
        """
        super().__init__(parent)
        self.setWindowTitle('Nuevo acceso web')

        form = QFormLayout(self)

        # --------------------------------------------------
        # Campo: Nombre del acceso
        # --------------------------------------------------
        self.name_edit = QLineEdit(self)
        self.name_edit.setText(prefill_name or suggested_name)

        # --------------------------------------------------
        # Campo: URL
        # --------------------------------------------------
        self.url_edit = QLineEdit(self)
        self.url_edit.setPlaceholderText('https://ejemplo.com')
        if prefill_url:
            self.url_edit.setText(prefill_url)

        # --------------------------------------------------
        # Botón: pegar desde portapapeles
        # --------------------------------------------------
        paste_btn = QPushButton('Pegar desde portapapeles', self)

        def paste_from_clipboard():
            """
            Pega el texto del portapapeles en el campo URL.

            Si el widget padre proporciona un método para sugerir
            nombres a partir de una URL, se utiliza automáticamente
            cuando el campo de nombre está vacío.
            """
            cb = QtGui.QGuiApplication.clipboard()
            txt = cb.text().strip() if cb else ''
            if txt:
                self.url_edit.setText(txt)
                if parent and hasattr(parent, 'suggest_name_from_url_or_text'):
                    suggested = parent.suggest_name_from_url_or_text(txt)
                    if suggested and (not self.name_edit.text().strip()):
                        self.name_edit.setText(suggested)

        paste_btn.clicked.connect(paste_from_clipboard)

        # --------------------------------------------------
        # Disposición del formulario
        # --------------------------------------------------
        form.addRow('Nombre:', self.name_edit)
        form.addRow('URL:', self.url_edit)
        form.addRow('', paste_btn)

        # --------------------------------------------------
        # Botonera inferior
        # --------------------------------------------------
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok
            | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.validate_and_accept)
        btns.rejected.connect(self.reject)

        # Botón de ayuda contextual
        self._install_help_button(btns)

        form.addRow(btns)

    def validate_and_accept(self):
        """
        Valida los datos introducidos y acepta el diálogo.

        Comprobaciones realizadas:
        - El nombre no puede estar vacío.
        - La URL no puede estar vacía.
        - La URL debe incluir un esquema válido.
        """
        name = self.name_edit.text().strip()
        url = self.url_edit.text().strip()

        if not name or not url:
            QtWidgets.QMessageBox.warning(
                self,
                'Datos incompletos',
                'Introduce un nombre y una URL.'
            )
            return

        if not (
            '://' in url
            or url.startswith('mailto:')
            or url.startswith('file:')
        ):
            QtWidgets.QMessageBox.warning(
                self,
                'URL no válida',
                'La URL debe incluir el esquema, por ejemplo: https://sitio.com'
            )
            return

        self.accept()

    def values(self):
        """
        Devuelve los valores introducidos en el formulario.

        Returns:
            Tupla (nombre, url) con los valores finales.
        """
        return (
            self.name_edit.text().strip(),
            self.url_edit.text().strip()
        )

