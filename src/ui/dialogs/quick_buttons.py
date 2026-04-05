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
# but WITHOUT ANY WARRANTY, without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""
ui.dialogs.quick_buttons

Diálogo de configuración de los “Botones rápidos” de Heimdall Desktop.

Este módulo implementa un diálogo que permite al usuario definir
hasta cinco accesos rápidos a carpetas frecuentes o personalizadas,
incluyendo:
- Activación/desactivación individual de cada botón.
- Título visible del botón.
- Ruta de la carpeta asociada.
- Icono personalizado opcional.

IMPORTANT:
- Este diálogo NO guarda configuración en disco.
- Devuelve una estructura de datos que será persistida por capas superiores.
"""

# ------------------------------------------------------------
# ui/dialogs/quick_buttons.py -> Clase QuickButtonsDialog
# ------------------------------------------------------------


from PySide6 import QtCore, QtGui, QtWidgets
from ui.helpers import HelpableDialogMixin
from pathlib import Path

from PySide6.QtWidgets import (
    QListWidget, QListWidgetItem, QDialog,
    QLineEdit, QLabel, QPushButton, QWidget, QCheckBox,
    QDialogButtonBox, QFileDialog, QMessageBox, QFormLayout
)

class QuickButtonsDialog(HelpableDialogMixin, QDialog):

    """
    Diálogo para definir botones rápidos que abren carpetas.

    Este diálogo permite configurar exactamente 5 botones rápidos.
    Internamente:
    - Se garantiza que siempre existen 5 entradas válidas.
    - Se hace merge con valores por defecto si la configuración está incompleta.
    """

    #: Tema de ayuda contextual
    help_topic = 'quick_buttons'

    def __init__(self, cfg, parent=None):
        """
        Inicializa el diálogo de configuración de botones rápidos.

        Args:
            cfg: Diccionario de configuración de la aplicación.
            parent: Widget padre (opcional).
        """
        super().__init__(parent)
        self.setWindowTitle('Botones rápidos')
        self.cfg = cfg
        
        # Estado interno: definición actual de quick buttons
        self.qbs = self._merge_with_defaults(cfg.get('quick_buttons'))
        
        form = QFormLayout(self)
        
        # Listas paralelas de widgets (una por botón)
        self.enable_cbs = []
        self.title_edits = []
        self.path_edits = []
        self.icon_edits = []
        
        # --------------------------------------------------
        # Construcción de las 5 filas de botones rápidos
        # --------------------------------------------------
        for i in range(5):
            row = QWidget(self)
            h = QtWidgets.QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(6)
            cb = QCheckBox('Mostrar', row)
            cb.setChecked(bool(self.qbs[i].get('enabled', True)))
            te = QLineEdit(row)
            te.setPlaceholderText(f'Título botón {i + 1}')
            te.setText(self.qbs[i].get('title', ''))
            h.addWidget(cb)
            h.addWidget(te, 1)
            form.addRow(f'Botón {i + 1}:', row)
            
            # ---------------------------
            # Ruta de la carpeta
            # --------------------------
            row2 = QWidget(self)
            h2 = QtWidgets.QHBoxLayout(row2)
            h2.setContentsMargins(0, 0, 0, 0)
            h2.setSpacing(6)
            pe = QLineEdit(row2)
            pe.setPlaceholderText('Ruta de carpeta…')
            pe.setText(self.qbs[i].get('path', ''))
            b_browse = QPushButton('Examinar…', row2)

            def _mk_browse(pe_ref=pe):
                """
                Crea un handler de selección de carpeta asociado
                a un QLineEdit concreto.

                NOTE:
                    Se usa binding por defecto para evitar capturas incorrectas
                    del valor de `pe` en el bucle.
                """
                return lambda: (lambda d: pe_ref.setText(d) if d else None)(QFileDialog.getExistingDirectory(self, 'Seleccionar carpeta', pe_ref.text() or str(Path.cwd())))
            b_browse.clicked.connect(_mk_browse())
            h2.addWidget(pe, 1)
            h2.addWidget(b_browse)
            form.addRow('Destino:', row2)

            # ---------------------------
            # Icono del botón
            # ---------------------------
            row3 = QWidget(self)
            h3 = QtWidgets.QHBoxLayout(row3)
            h3.setContentsMargins(0, 0, 0, 0)
            h3.setSpacing(6)
            ie = QLineEdit(row3)
            ie.setPlaceholderText('Ruta de icono (.ico/.png/.exe/.dll)…')
            ie.setText(self.qbs[i].get('icon', ''))
            b_icon = QPushButton('Icono…', row3)

            def _mk_browse_icon(ie_ref=ie):
                """
                Crea un handler para seleccionar un icono asociado
                a un QLineEdit concreto.
                """
                return lambda: (lambda path: ie_ref.setText(path) if path else None)(QFileDialog.getOpenFileName(self, 'Seleccionar icono', str(Path.cwd()), 'Iconos/Imágenes (*.ico *.png *.jpg *.bmp);;Ejecutables/DLL (*.exe *.dll);;Todos (*.*)')[0])
            b_icon.clicked.connect(_mk_browse_icon())
            h3.addWidget(ie, 1)
            h3.addWidget(b_icon)
            form.addRow('Icono:', row3)
            
            # Guardar referencias
            self.enable_cbs.append(cb)
            self.title_edits.append(te)
            self.path_edits.append(pe)
            self.icon_edits.append(ie)
        
        # --------------------------------------------------
        # Botonera inferior
        # --------------------------------------------------
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, self)
        btn_default = QPushButton('Por defecto', self)
        btns.addButton(btn_default, QtWidgets.QDialogButtonBox.HelpRole)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        self._install_help_button(btns)
        form.addRow(btns)
        self.load_from_qbs(self.qbs)

        def on_reset_defaults():
            """
            Restablece los 5 botones rápidos a los valores por defecto.

            WARNING:
                Esta acción descarta los cambios no guardados.
            """
            reply = QtWidgets.QMessageBox.question(self, 'Restablecer a valores por defecto', '¿Seguro que quieres restablecer los 5 botones rápidos a los valores por defecto?\n\nSe perderán los cambios no guardados.', QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
            if reply != QtWidgets.QMessageBox.Yes:
                return
            self.qbs = self._defaults()
            self.load_from_qbs(self.qbs)
        btn_default.clicked.connect(on_reset_defaults)

    def _defaults(self):
        """
        Devuelve la definición por defecto de los botones rápidos.

        Returns:
            Lista de 5 diccionarios de configuración por defecto.
        """
        home = Path.home()
        return [{'enabled': True, 'title': 'Documentos', 'path': str(home / 'Documents'), 'icon': ''}, {'enabled': True, 'title': 'Música', 'path': str(home / 'Music'), 'icon': ''}, {'enabled': True, 'title': 'Imágenes', 'path': str(home / 'Pictures'), 'icon': ''}, {'enabled': True, 'title': 'Vídeo', 'path': str(home / 'Videos'), 'icon': ''}, {'enabled': True, 'title': 'Descargas', 'path': str(home / 'Downloads'), 'icon': ''}]

    def _merge_with_defaults(self, qbs):
        """
        Fusiona una configuración existente con los valores por defecto.

        Args:
            qbs: Lista de definiciones de botones rápidos.

        Returns:
            Lista completa de 5 definiciones válidas.
        """
        base = self._defaults()
        if not qbs:
            return base
        out = []
        for i in range(5):
            d = dict(base[i])
            if i < len(qbs) and isinstance(qbs[i], dict):
                d.update({k: qbs[i].get(k, d.get(k)) for k in ('enabled', 'title', 'path', 'icon')})
            out.append(d)
        return out

    def load_from_qbs(self, qbs):
        """
        Carga en la interfaz el contenido de una lista de botones rápidos.

        Args:
            qbs: Lista de definiciones de botones rápidos.
        """
        data = self._merge_with_defaults(qbs)
        for i in range(5):
            qb = data[i]
            self.enable_cbs[i].setChecked(bool(qb.get('enabled', True)))
            self.title_edits[i].setText(qb.get('title', f'Botón {i + 1}'))
            self.path_edits[i].setText(qb.get('path', ''))
            self.icon_edits[i].setText(qb.get('icon', ''))

    def result_qbs(self):
        """
        Devuelve la configuración final de los botones rápidos.

        Returns:
            Lista de 5 diccionarios con la definición final
            de cada botón rápido.
        """
        out = []
        for i in range(5):
            out.append({'enabled': bool(self.enable_cbs[i].isChecked()), 'title': self.title_edits[i].text().strip() or f'Botón {i + 1}', 'path': self.path_edits[i].text().strip(), 'icon': self.icon_edits[i].text().strip()})
        return out

