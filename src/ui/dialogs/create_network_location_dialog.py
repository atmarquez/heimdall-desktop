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
Diálogo para crear ubicaciones de red.

Este módulo define el diálogo `CreateNetworkLocationDialog`, que permite
crear accesos a ubicaciones de red de forma unificada, al estilo del
Explorador de Windows.

Soporta:
- Rutas UNC (\\\\servidor\\recurso).
- URLs HTTP/HTTPS.
- FTP / SFTP.
- WebDAV.
- Otros esquemas compatibles con Explorer.

IMPORTANT:
    Este diálogo NO ejecuta accesos directamente.
    Se limita a crear accesos (.url o .lnk) en la ubicación indicada.
"""

from PySide6 import QtWidgets
from PySide6.QtWidgets import QDialog
from pathlib import Path

from core.shortcuts import (
    sanitize_filename,
    unique_path,
    create_lnk_via_vbs,
)


class CreateNetworkLocationDialog(QDialog):
    """
    Diálogo para crear ubicaciones de red.

    Emula el comportamiento del Explorador de Windows al crear
    accesos a ubicaciones de red, seleccionando automáticamente
    el tipo de acceso adecuado (.url o .lnk).
    """

    def __init__(self, parent=None):
        """
        Inicializa el diálogo de creación de ubicación de red.

        Args:
            parent (QWidget, optional):
                Widget padre.
        """
        super().__init__(parent)
        self.setWindowTitle('Nueva ubicación de red')
        self.resize(420, 180)

        layout = QtWidgets.QVBoxLayout(self)

        # ---------------------------------------------------------
        # Formulario principal
        # ---------------------------------------------------------
        form = QtWidgets.QFormLayout()

        self.name_edit = QtWidgets.QLineEdit(self)
        self.location_edit = QtWidgets.QLineEdit(self)
        self.location_edit.setPlaceholderText(
            '\\\\NAS\\Multimedia  |  ftp://servidor  |  https://intranet'
        )

        form.addRow('Nombre:', self.name_edit)
        form.addRow('Ubicación:', self.location_edit)

        layout.addLayout(form)

        # ---------------------------------------------------------
        # Información de ayuda
        # ---------------------------------------------------------
        self.info = QtWidgets.QLabel(
            'Se admiten rutas UNC, URLs, FTP, WebDAV y rutas especiales. '
            'El programa creará automáticamente el tipo de acceso adecuado.'
        )
        self.info.setWordWrap(True)
        layout.addWidget(self.info)

        # ---------------------------------------------------------
        # Botonera estándar
        # ---------------------------------------------------------
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok |
            QtWidgets.QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

    def values(self):
        """
        Devuelve los valores introducidos por el usuario.

        Returns:
            tuple[str, str]:
                (nombre, ubicación)
        """
        return (
            self.name_edit.text().strip(),
            self.location_edit.text().strip()
        )

    def create_location(self, dest_dir: Path):
        """
        Crea la ubicación de red en el directorio destino indicado.

        Dependiendo del esquema de la ubicación:
        - URLs -> se crea un archivo .url
        - Rutas UNC -> se crea un acceso directo (.lnk)
        - Otros esquemas -> fallback a acceso .lnk vía Explorer

        Args:
            dest_dir (Path):
                Directorio donde se creará el acceso.

        Returns:
            Path:
                Ruta del archivo creado (.url o .lnk).

        Raises:
            ValueError:
                Si faltan nombre o ubicación.
            RuntimeError:
                Si falla la creación del acceso directo.
        """
        name, location = self.values()
        if not name or not location:
            raise ValueError('Nombre y ubicación son obligatorios')

        # Normalizar nombre de archivo
        name = sanitize_filename(name)
        loc = location.strip()

        # ---------------------------------------------------------
        # Accesos basados en URL (http, ftp, webdav, etc.)
        # ---------------------------------------------------------
        if loc.lower().startswith((
            'http://', 'https://', 'ftp://',
            'file:', 'sftp://', 'webdav://'
        )):
            path = unique_path(dest_dir, name, '.url')
            path.write_text(
                f'[InternetShortcut]\nURL={loc}\n',
                encoding='utf-8'
            )
            return path

        # ---------------------------------------------------------
        # Rutas UNC (\\servidor\recurso)
        # ---------------------------------------------------------
        if loc.startswith('\\'):
            path = unique_path(dest_dir, name, '.lnk')
            ok, err = create_lnk_via_vbs(
                str(path),
                'explorer.exe',
                loc,
                '',
                'explorer.exe'
            )
            if not ok:
                raise RuntimeError(err)
            return path

        # ---------------------------------------------------------
        # Fallback: intentar abrir con Explorer
        # ---------------------------------------------------------
        path = unique_path(dest_dir, name, '.lnk')
        ok, err = create_lnk_via_vbs(
            str(path),
            'explorer.exe',
            loc,
            '',
            'explorer.exe'
        )
        if not ok:
            raise RuntimeError(err)

        return path
