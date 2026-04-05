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
Utilidades de apertura de la ayuda integrada.

Este módulo proporciona funciones auxiliares para abrir páginas de ayuda
en formato HTML desde el sistema de archivos local, utilizando los
mecanismos estándar de Qt.

La ayuda se considera un recurso local y dependiente del idioma
(actualmente español).

IMPORTANT:
    Este módulo no renderiza ayuda internamente.
    Delega siempre en el navegador o visor predeterminado del sistema.

NOTE:
    El diseño es deliberadamente simple para minimizar dependencias
    y evitar acoplamiento con la UI principal.
"""

from PySide6 import QtCore, QtGui, QtWidgets
from pathlib import Path
from config.service import app_dir


def open_help_page(topic: str, fallback: str = 'index'):
    """
    Abre la página de ayuda HTML correspondiente a un tema dado.

    El método intenta abrir primero la página asociada a `topic`.
    Si no existe, intenta abrir la página de respaldo indicada por
    `fallback`. Si ninguna está disponible, muestra un mensaje informativo.

    Flujo de resolución:
    1. Construir ruta base de ayuda (idioma actual).
    2. Intentar abrir `{topic}.html`.
    3. Si no existe, intentar abrir `{fallback}.html`.
    4. Si tampoco existe, mostrar mensaje informativo al usuario.
    5. Ante errores inesperados, mostrar advertencia.

    Args:
        topic (str):
            Identificador del tema de ayuda (sin extensión).
        fallback (str, optional):
            Tema alternativo a usar si el principal no existe.
            Por defecto: 'index'.

    Returns:
        None
    """
    try:
        # Directorio base de la ayuda local (por idioma)
        base = app_dir() / 'resources' / 'help' / 'es'
        path = base / f'{topic}.html'

        # ----------------------------------------------------------
        # Si la página solicitada no existe, usar fallback
        # ----------------------------------------------------------
        if not path.exists():
            fb = base / f'{fallback}.html'
            if fb.exists():
                QtGui.QDesktopServices.openUrl(
                    QtCore.QUrl.fromLocalFile(str(fb))
                )
                return

            # Código defensivo: ni la página principal ni la de fallback existen
            QtWidgets.QMessageBox.information(
                None,
                'Ayuda',
                f'No se encontró la ayuda para: {topic}'
            )
            return

        # ----------------------------------------------------------
        # Apertura normal de la página solicitada
        # ----------------------------------------------------------
        QtGui.QDesktopServices.openUrl(
            QtCore.QUrl.fromLocalFile(str(path))
        )

    except Exception as e:
        # Código defensivo: fallo inesperado al abrir la ayuda
        try:
            QtWidgets.QMessageBox.warning(
                None,
                'Ayuda',
                f'No se pudo abrir la ayuda ({topic}): {e}'
            )
        except Exception:
            # Último nivel defensivo: evitar lanzar excepciones desde la UI
            pass