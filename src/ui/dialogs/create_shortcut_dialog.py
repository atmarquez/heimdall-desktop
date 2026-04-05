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
ui.dialogs.create_shortcut_dialog

Diálogo para crear accesos directos de Windows (.lnk) a ejecutables.

Este módulo implementa un diálogo guiado que permite al usuario:
- Definir el nombre del acceso directo.
- Seleccionar el ejecutable de destino.
- Opcionalmente añadir argumentos.
- Definir directorio de trabajo.
- Seleccionar un icono personalizado.

IMPORTANT:
- Este diálogo solo recopila datos y valida entradas.
- La creación real del acceso directo se realiza fuera de esta clase.
"""

# ------------------------------------------------------------
# ui/dialogs/create_shortcut_dialog.py -> Clase CreateShortcutDialog
# ------------------------------------------------------------


from PySide6 import QtWidgets, QtGui, QtCore
from PySide6.QtWidgets import (
    QWidget,
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QFormLayout,
    QFileDialog,
    QMessageBox,
    QHBoxLayout,
    QVBoxLayout,
)

from pathlib import Path
from ui.helpers import HelpableDialogMixin
from ui.help import open_help_page


class CreateShortcutDialog(HelpableDialogMixin, QDialog):
    """
    Diálogo para crear accesos directos de Windows (.lnk).

    Este diálogo pertenece a la interfaz gráfica y se integra con
    el sistema de ayuda contextual mediante HelpableDialogMixin.

    NOTE:
        La validación se realiza antes de aceptar el diálogo,
        pero la creación del .lnk se delega a capas superiores.
    """

    help_topic = 'create_shortcut'


    def __init__(self, parent=None):
        """
        Inicializa el diálogo de creación de accesos directos.

        Args:
            parent: Widget padre de Qt (opcional).
        """
        super().__init__(parent)
        self.setWindowTitle('Nuevo acceso directo')
        
        # Layout principal tipo formulario
        form = QFormLayout(self)
        
        # --------------------------------------------------
        # Nombre del acceso
        # ------------------------------------------------
        self.name_edit = QLineEdit(self)
        form.addRow('Nombre del acceso:', self.name_edit)

        # --------------------------------------------------
        # Programa destino
        # --------------------------------------------------
        prog_layout = QtWidgets.QHBoxLayout()
        self.target_edit = QLineEdit(self)
        btn_browse_target = QPushButton('Examinar…', self)

        def browse_target():
            """
            Abre un diálogo para seleccionar el ejecutable destino.
            """
            path, _ = QFileDialog.getOpenFileName(self, 'Seleccionar programa', str(Path.cwd()), 'Ejecutables (*.exe);;Todos (*.*)')
            if path:
                self.target_edit.setText(path)
                if not self.name_edit.text().strip():
                    self.name_edit.setText(Path(path).stem)
        btn_browse_target.clicked.connect(browse_target)
        prog_layout.addWidget(self.target_edit)
        prog_layout.addWidget(btn_browse_target)
        prog_w = QWidget()
        prog_w.setLayout(prog_layout)
        form.addRow('Programa (destino):', prog_w)
        
        # --------------------------------------------------
        # Argumentos
        # --------------------------------------------------
        self.args_edit = QLineEdit(self)
        form.addRow('Argumentos (opcional):', self.args_edit)
        
        # --------------------------------------------------
        # Directorio de trabajo
        # --------------------------------------------------
        wd_layout = QtWidgets.QHBoxLayout()
        self.wd_edit = QLineEdit(self)
        btn_browse_wd = QPushButton('Examinar…', self)

        def browse_wd():
            """
            Abre un diálogo para seleccionar el directorio de trabajo.
            """
            d = QFileDialog.getExistingDirectory(self, 'Seleccionar carpeta de trabajo', self.wd_edit.text() or str(Path.cwd()))
            if d:
                self.wd_edit.setText(d)
        btn_browse_wd.clicked.connect(browse_wd)
        wd_layout.addWidget(self.wd_edit)
        wd_layout.addWidget(btn_browse_wd)
        wd_w = QWidget()
        wd_w.setLayout(wd_layout)
        form.addRow('Iniciar en (opcional):', wd_w)
        
        # --------------------------------------------------
        # Icono del acceso
        # --------------------------------------------------
        icon_layout = QtWidgets.QHBoxLayout()
        self.icon_edit = QLineEdit(self)
        btn_browse_icon = QPushButton('Examinar…', self)

        def browse_icon():
            """
            Abre un diálogo para seleccionar un icono o archivo origen de icono.
            """
            path, _ = QFileDialog.getOpenFileName(self, 'Seleccionar icono', str(Path.cwd()), 'Iconos (*.ico);;Ejecutables (*.exe);;DLL (*.dll);;Todos (*.*)')
            if path:
                self.icon_edit.setText(path)
        btn_browse_icon.clicked.connect(browse_icon)
        icon_layout.addWidget(self.icon_edit)
        icon_layout.addWidget(btn_browse_icon)
        icon_w = QWidget()
        icon_w.setLayout(icon_layout)
        form.addRow('Icono (opcional):', icon_w)
        
        # --------------------------------------------------
        # Botonera inferior
        # --------------------------------------------------
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.validate_and_accept)
        btns.rejected.connect(self.reject)
        self._install_help_button(btns)
        form.addRow(btns)

    def validate_and_accept(self):
        """
        Valida los datos introducidos y acepta el diálogo.

        Comprueba:
        - Que exista un nombre.
        - Que exista un ejecutable de destino válido.
        """
        name = self.name_edit.text().strip()
        target = self.target_edit.text().strip()

        if not name or not target:
            QtWidgets.QMessageBox.warning(
                self,
                'Datos incompletos',
                'Debes indicar al menos el nombre y el programa (destino).'
            )
            return

        if not Path(target).exists():
            QtWidgets.QMessageBox.warning(
                self,
                'Destino no válido',
                'El archivo de destino no existe.'
            )
            return

        self.accept()

    def values(self):
        """
        Devuelve los valores del formulario.

        Returns:
            Diccionario con los datos necesarios para crear el acceso directo.
        """
        return {
            'name': self.name_edit.text().strip(),
            'target': self.target_edit.text().strip(),
            'args': self.args_edit.text().strip(),
            'workdir': self.wd_edit.text().strip(),
            'icon': self.icon_edit.text().strip(),
        }

