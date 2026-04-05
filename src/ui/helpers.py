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
Helpers de UI reutilizables.

Este módulo contiene mixins y utilidades pensadas para ser reutilizadas
en distintos diálogos de la aplicación.

Actualmente incluye:
- HelpableDialogMixin: añade soporte de ayuda contextual (botón + F1)
  a cualquier diálogo Qt que lo herede.

IMPORTANT:
    Este módulo NO define diálogos completos.
    Está diseñado exclusivamente como soporte para otros widgets.
"""

from PySide6 import QtCore, QtGui, QtWidgets
from ui.help import open_help_page


class HelpableDialogMixin:
    """
    Mixin que añade ayuda contextual a diálogos Qt.

    Proporciona:
    - Botón "Ayuda" en el QDialogButtonBox.
    - Atajo de teclado F1.
    - Resolución automática del tema de ayuda.

    Uso típico:
        class MiDialogo(QDialog, HelpableDialogMixin):
            help_topic = "configuracion_avanzada"

    NOTE:
        Este mixin asume que la clase final es un QWidget/QDialog válido.
    """

    #: Tema de ayuda asociado al diálogo.
    #: Si está vacío, se deriva automáticamente del título de la ventana.
    help_topic: str = ''

    def _install_help_button(self, button_box: QtWidgets.QDialogButtonBox):
        """
        Instala el botón de ayuda y el atajo F1 en un diálogo.

        El método es seguro frente a llamadas múltiples y evita duplicados
        tanto por propiedad interna como por inspección de botones existentes.

        IMPORTANT:
            El estado de instalación se guarda en el button_box, no en el diálogo.
            Esto evita interferencias si un mismo diálogo recrea botones.

        Args:
            button_box (QDialogButtonBox):
                Barra de botones del diálogo donde se añadirá el botón de ayuda.
        """
        try:
            # ----------------------------------------------------------
            # Prevención de instalaciones duplicadas
            # ----------------------------------------------------------
            if button_box.property('_help_installed'):
                return

            # Evitar duplicados por nombre de objeto o texto visible
            for b in button_box.buttons():
                if (
                    b.objectName() == 'helpButton'
                    or (b.text() or '').strip().lower() == 'ayuda'
                ):
                    button_box.setProperty('_help_installed', True)
                    return

            # ----------------------------------------------------------
            # Creación del botón de ayuda
            # ----------------------------------------------------------
            help_btn = QtWidgets.QPushButton('Ayuda', self)
            help_btn.setObjectName('helpButton')
            help_btn.clicked.connect(self._on_help_clicked)

            # Inserción en el layout existente si es posible
            layout = button_box.layout()
            if layout is not None:
                layout.addWidget(help_btn)
            else:
                # Fallback: añadir como botón explícito del button box
                button_box.addButton(
                    help_btn,
                    QtWidgets.QDialogButtonBox.ActionRole
                )

            # ----------------------------------------------------------
            # Atajo de teclado F1 (asociado al diálogo)
            # ----------------------------------------------------------
            # NOTE:
            #   El shortcut se guarda en el propio diálogo, no en el button box,
            #   ya que el atajo debe vivir mientras exista el diálogo.
            if not hasattr(self, '_help_f1_shortcut'):
                self._help_f1_shortcut = QtGui.QShortcut(
                    QtGui.QKeySequence('F1'),
                    self
                )
                self._help_f1_shortcut.activated.connect(
                    self._on_help_clicked
                )

            button_box.setProperty('_help_installed', True)

        except Exception as e:
            # Código defensivo extremo: fallo al instalar ayuda
            # No debe impedir el uso normal del diálogo.
            print(f"Tipo: {type(e).__name__}, Mensaje: {e}")

    def _on_help_clicked(self):
        """
        Callback común para botón de ayuda y atajo F1.

        Resuelve el tema de ayuda y abre la página correspondiente.
        """
        topic = self.help_topic or self._derive_topic_from_title()
        open_help_page(topic)

    def _derive_topic_from_title(self) -> str:
        """
        Deriva automáticamente el tema de ayuda a partir del título del diálogo.

        El título se normaliza:
        - Se convierte a minúsculas.
        - Los espacios se sustituyen por guiones bajos.

        Returns:
            str: Tema de ayuda derivado.
        """
        import re
        t = (self.windowTitle() or 'ayuda').strip().lower()
        return re.sub(r'\s+', '_', t)