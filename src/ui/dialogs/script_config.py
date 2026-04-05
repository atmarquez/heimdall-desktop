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
Diálogo de configuración de scripts.

Este módulo define el diálogo `ScriptConfigDialog`, utilizado para
configurar la ejecución de scripts de inicio y salida de la aplicación.

Permite establecer:
- Ruta del script.
- Argumentos.
- Comportamiento de espera.
- Tiempo máximo de ejecución (timeout).
- Ejecución en modo oculto (Windows).

IMPORTANT:
    Este diálogo no ejecuta scripts.
    Solo recoge y valida la configuración de ejecución.
"""

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QPushButton,
    QWidget, QCheckBox, QSpinBox,
    QDialogButtonBox, QFileDialog
)
from pathlib import Path

from ui.helpers import HelpableDialogMixin


class ScriptConfigDialog(HelpableDialogMixin, QDialog):
    """
    Diálogo para configurar scripts de inicio o salida.

    Permite al usuario definir cómo se ejecutará un script:
    - Qué script ejecutar.
    - Con qué argumentos.
    - Si debe esperarse a su finalización.
    - Cuánto tiempo máximo puede ejecutarse.
    - Si debe ejecutarse oculto (Windows).

    NOTE:
        Integra ayuda contextual mediante `HelpableDialogMixin`.
    """

    #: Tema de ayuda asociado a este diálogo.
    help_topic = 'script_config'

    def __init__(self, parent=None, title='Configurar script', values=None):
        """
        Inicializa el diálogo de configuración de script.

        Args:
            parent (QWidget, optional):
                Widget padre.
            title (str):
                Título del diálogo.
            values (dict, optional):
                Valores iniciales del script (preconfiguración).
        """
        super().__init__(parent)
        self.setWindowTitle(title)

        # Copia defensiva de los valores iniciales
        self.values_dict = (values or {}).copy()

        form = QFormLayout(self)

        # ---------------------------------------------------------
        # Ruta del script
        # ---------------------------------------------------------
        self.path_edit = QLineEdit(self)
        self.path_edit.setText(
            self.values_dict.get('script', '')
        )

        btn_browse = QPushButton('Examinar…', self)

        def browse():
            """
            Abre un diálogo para seleccionar el script a ejecutar.

            NOTE:
                El filtro muestra los tipos de script más habituales,
                pero permite seleccionar cualquier archivo.
            """
            path, _ = QFileDialog.getOpenFileName(
                self,
                title,
                str(Path.cwd()),
                'Scripts (*.bat *.cmd *.ps1 *.py *.vbs *.exe);;Todos (*.*)'
            )
            if path:
                self.path_edit.setText(path)

        btn_browse.clicked.connect(browse)

        h = QtWidgets.QHBoxLayout()
        h.addWidget(self.path_edit)
        h.addWidget(btn_browse)

        w = QWidget()
        w.setLayout(h)
        form.addRow('Ruta del script:', w)

        # ---------------------------------------------------------
        # Argumentos
        # ---------------------------------------------------------
        self.args_edit = QLineEdit(self)
        self.args_edit.setText(
            self.values_dict.get('args', '')
        )
        form.addRow('Argumentos:', self.args_edit)

        # ---------------------------------------------------------
        # Opciones de ejecución
        # ---------------------------------------------------------
        self.wait_cb = QCheckBox(
            'Esperar a que termine',
            self
        )
        self.wait_cb.setChecked(
            bool(self.values_dict.get('wait', True))
        )
        form.addRow('', self.wait_cb)

        self.timeout_sb = QSpinBox(self)
        self.timeout_sb.setRange(0, 3600)
        self.timeout_sb.setValue(
            int(self.values_dict.get('timeout', 20) or 0)
        )
        form.addRow(
            'Timeout (s, 0 = sin límite):',
            self.timeout_sb
        )

        self.hidden_cb = QCheckBox(
            'Ejecutar oculto (Windows)',
            self
        )
        self.hidden_cb.setChecked(
            bool(self.values_dict.get('hidden', True))
        )
        form.addRow('', self.hidden_cb)

        # ---------------------------------------------------------
        # Botonera estándar + ayuda
        # ---------------------------------------------------------
        btns = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)

        # Hook adicional en botón OK (defensivo)
        try:
            ok_btn = btns.button(QDialogButtonBox.Ok)
            if ok_btn is not None:
                ok_btn.clicked.connect(self._on_apply_clicked)
        except Exception:
            # Código defensivo: fallo silencioso
            pass

        btns.rejected.connect(self.reject)

        # Inserta botón Ayuda y atajo F1
        self._install_help_button(btns)

        form.addRow(btns)

    def result_values(self):
        """
        Devuelve los valores configurados en el diálogo.

        Returns:
            dict:
                Diccionario con claves:
                - script (str)
                - args (str)
                - wait (bool)
                - timeout (int)
                - hidden (bool)
        """
        return {
            'script': self.path_edit.text().strip(),
            'args': self.args_edit.text().strip(),
            'wait': self.wait_cb.isChecked(),
            'timeout': int(self.timeout_sb.value()),
            'hidden': self.hidden_cb.isChecked(),
        }