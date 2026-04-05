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
Pestaña de importación y exportación de configuración.

Este módulo define la clase `ImportExportConfigTab`, correspondiente a la
pestaña “Avanzado” (Importar / Exportar) del diálogo de Configuración.

Responsabilidad única y explícita:
- Exportar la configuración (`cfg`) actual a un archivo JSON.
- Importar una configuración completa desde un archivo JSON.

IMPORTANT:
    Esta pestaña NO modifica directamente la configuración activa.
    La importación se realiza de forma interactiva y debe ser confirmada
    posteriormente por el usuario (Aplicar / Aceptar).

NOTE:
    El diseño evita sobrescrituras accidentales y prioriza la seguridad
    del estado interno de la aplicación.
"""

from pathlib import Path
import json

from PySide6 import QtWidgets
from PySide6 import QtCore


class ImportExportConfigTab(QtWidgets.QWidget):
    """
    Pestaña para importar y exportar la configuración de la aplicación.

    Funcionalidades:
    - Exportación completa de la configuración actual a JSON.
    - Importación de un JSON válido como nueva configuración candidata.

    WARNING:
        La importación reemplaza la configuración cargada en el diálogo,
        pero NO se guarda automáticamente en disco.
    """

    #: Señal emitida cuando se importa un diccionario de configuración válido.
    config_imported = QtCore.Signal(dict)

    def __init__(self, parent=None):
        """
        Inicializa la pestaña de Importar / Exportar.

        Args:
            parent (QWidget, optional):
                Widget padre.
        """
        super().__init__(parent)

        layout = QtWidgets.QVBoxLayout(self)

        info = QtWidgets.QLabel(
            "Herramientas para exportar o importar la configuración completa de la aplicación."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        buttons = QtWidgets.QWidget(self)
        buttons_layout = QtWidgets.QHBoxLayout(buttons)
        buttons_layout.setContentsMargins(0, 0, 0, 0)

        self.btn_export = QtWidgets.QPushButton(
            "Exportar configuración…", buttons
        )
        self.btn_import = QtWidgets.QPushButton(
            "Importar configuración…", buttons
        )

        buttons_layout.addWidget(self.btn_export)
        buttons_layout.addWidget(self.btn_import)

        layout.addWidget(buttons)
        layout.addStretch(1)

        # ---------------------------------------------------------
        # Estado interno
        # ---------------------------------------------------------
        # NOTE:
        #   Se guarda únicamente una referencia a cfg.
        #   No se modifica directamente en esta pestaña.
        self._cfg = None

        self.btn_export.clicked.connect(self._on_export_clicked)
        self.btn_import.clicked.connect(self._on_import_clicked)

    # ------------------------------------------------------------
    # API pública (coherente con el resto de pestañas)
    # ------------------------------------------------------------

    def load_from_cfg(self, cfg: dict):
        """
        Carga la configuración actual.

        IMPORTANT:
            Este método NO modifica la configuración.
            Solo guarda la referencia para exportación.

        Args:
            cfg (dict):
                Diccionario de configuración actual.
        """
        self._cfg = cfg

    def apply_to_cfg(self, cfg: dict):
        """
        Esta pestaña no aplica cambios automáticamente.

        NOTE:
            La importación se realiza de forma interactiva mediante señal.
            El guardado efectivo depende del diálogo de Configuración.

        Args:
            cfg (dict):
                Configuración actual.

        Returns:
            dict: Configuración sin modificar.
        """
        return cfg

    # ------------------------------------------------------------
    # Implementación interna
    # ------------------------------------------------------------

    def _default_config_path(self) -> Path:
        """
        Devuelve la ruta por defecto propuesta para exportar/importar.

        Returns:
            Path: Ruta sugerida para el archivo JSON.
        """
        return Path.cwd() / "config.json"

    def _on_export_clicked(self):
        """
        Maneja la exportación de la configuración a un archivo JSON.
        """
        if not isinstance(self._cfg, dict):
            QtWidgets.QMessageBox.warning(
                self,
                "Exportar configuración",
                "No hay configuración cargada."
            )
            return

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Exportar configuración",
            str(self._default_config_path()),
            "JSON (*.json);;Todos (*.*)",
        )

        if not path:
            return

        try:
            # Escritura segura mediante archivo temporal
            tmp = Path(path + ".tmp")
            tmp.write_text(
                json.dumps(self._cfg, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            tmp.replace(Path(path))

            QtWidgets.QMessageBox.information(
                self,
                "Exportación completada",
                f"Configuración exportada a:\n{path}",
            )

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Error al exportar",
                f"No se pudo exportar la configuración:\n{e}",
            )

    def _on_import_clicked(self):
        """
        Maneja la importación de un archivo JSON como configuración.
        """
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Importar configuración",
            str(self._default_config_path()),
            "JSON (*.json);;Todos (*.*)",
        )

        if not path:
            return

        reply = QtWidgets.QMessageBox.question(
            self,
            "Importar configuración",
            "Esto reemplazará la configuración actual en el diálogo.\n"
            "¿Deseas continuar?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )

        if reply != QtWidgets.QMessageBox.Yes:
            return

        try:
            data = json.loads(
                Path(path).read_text(encoding="utf-8")
            )

            if not isinstance(data, dict):
                raise ValueError(
                    "El archivo no contiene un objeto de configuración válido."
                )

            # Emisión de señal para que el diálogo gestione la aplicación real
            self.config_imported.emit(data)

            QtWidgets.QMessageBox.information(
                self,
                "Importación completada",
                "Configuración cargada correctamente.\n"
                "Pulsa 'Aplicar' o 'Aceptar' para guardarla.",
            )

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Error al importar",
                f"No se pudo importar la configuración:\n{e}",
            )

    def populate_from_cfg(self):
        """
        Método requerido por la interfaz común de pestañas.

        NOTE:
            Esta pestaña no muestra valores dinámicos,
            por lo que no requiere implementación.
        """
        pass