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
ui.config.about

Pestaña “Acerca de…” dentro del diálogo de Configuración de Heimdall Desktop.

Este módulo implementa una pestaña informativa que muestra:
- Icono y nombre de la aplicación.
- Metadatos (versión, autor, build).
- Descripción general.
- Enlaces útiles del proyecto.
- Resumen de la licencia GPLv3.
- Acciones para consultar, copiar o abrir el texto completo de la licencia.

IMPORTANTE:
- Este módulo es puramente de interfaz gráfica.
- No contiene lógica de negocio.
- Está diseñado para ser autoexplicativo y de bajo mantenimiento.
"""

import app_meta
import os
from PySide6 import QtWidgets, QtCore, QtGui
from config.service import (
    get_cfg_service,
    app_dir,
)


class AboutTab(QtWidgets.QWidget):
    """
    Pestaña “Acerca de…” del panel de Configuración.

    Esta clase construye una vista informativa con:
    - Información general del proyecto.
    - Metadatos de compilación.
    - Enlaces externos.
    - Resumen y acceso al texto de la licencia GPLv3.

    NOTE:
        Toda la interfaz se construye en `_build_ui`
        para mantener el constructor limpio.
    """

    def __init__(self, parent_tabs):
        """
        Inicializa la pestaña “Acerca de…”.

        Args:
            parent_tabs: Widget contenedor (tab widget de configuración).
        """
        super().__init__(parent_tabs)
        self._build_ui()

    def _build_ui(self):
        """
        Construye completamente la interfaz gráfica de la pestaña.

        Este método:
        - Crea layouts y widgets.
        - Carga información desde app_meta.
        - Configura enlaces externos, donaciones y acciones de licencia.

        IMPORTANT:
            Se usa un único layout vertical para facilitar
            futuras modificaciones o ampliaciones.
        """
        layout = QtWidgets.QVBoxLayout(self)
        layout.setAlignment(QtCore.Qt.AlignTop)

        # ==========================================================
        # Icono de la aplicación
        # ==========================================================
        icon_label = QtWidgets.QLabel(self)
        icon_path = get_cfg_service().app_icon_path()
        icon = QtGui.QIcon(str(icon_path)) if icon_path else QtGui.QIcon()
        pixmap = icon.pixmap(64, 64)
        icon_label.setPixmap(pixmap)
        icon_label.setAlignment(QtCore.Qt.AlignHCenter)
        layout.addWidget(icon_label)

        # ==========================================================
        # Título y metadatos
        # ==========================================================
        title = QtWidgets.QLabel(
            f"<h2>{app_meta.APP_NAME}</h2>",
            self
        )
        title.setAlignment(QtCore.Qt.AlignHCenter)
        title.setTextFormat(QtCore.Qt.RichText)
        layout.addWidget(title)

        meta = QtWidgets.QLabel(
            f"""
            <b>Versión:</b> {app_meta.APP_VERSION}<br>
            <b>Build:</b> {app_meta.APP_BUILD}<br>
            <b>Autor:</b> {app_meta.APP_AUTHOR}<br>
            <b>Contacto:</b> <a href='{app_meta.APP_EMAIL}'>{app_meta.APP_EMAIL}</a><br>
            <b>Copyright:</b> {app_meta.APP_COPYRIGHT}
            """
        )
        meta.setAlignment(QtCore.Qt.AlignHCenter)
        layout.addWidget(meta)

        # ==========================================================
        # Descripción
        # ==========================================================
        desc = QtWidgets.QLabel(app_meta.APP_DESCRIPTION)
        desc.setWordWrap(True)
        desc.setAlignment(QtCore.Qt.AlignHCenter)
        layout.addWidget(desc)

        # ==========================================================
        # Enlaces útiles
        # ==========================================================
        links_group = QtWidgets.QGroupBox("Enlaces útiles")
        links_layout = QtWidgets.QVBoxLayout(links_group)
        links_layout.setSpacing(6)

        def link(text: str, url: str) -> QtWidgets.QLabel:
            lbl = QtWidgets.QLabel(f'<a href="{url}">{text}</a>')
            lbl.setOpenExternalLinks(True)
            return lbl

        links_layout.addWidget(link("🌐 Página del proyecto", app_meta.APP_URL_PROJECT))
        links_layout.addWidget(link("📄 Repositorio", app_meta.APP_URL_REPO))
        links_layout.addWidget(link("🐞 Reportar errores", app_meta.APP_URL_ISSUES))
        links_layout.addWidget(link("📘 Documentación", app_meta.APP_URL_DOCS))
        links_layout.addWidget(link("⚖ Texto oficial de la GPLv3", app_meta.APP_URL_GPL))

        # ==========================================================
        # Donaciones (PayPal)
        # ==========================================================
        donate_group = QtWidgets.QGroupBox("Apoya el proyecto")
        donate_layout = QtWidgets.QVBoxLayout(donate_group)

        donate_text = QtWidgets.QLabel(
            "Heimdall Desktop es software libre.\n"
            "Si te resulta útil, puedes apoyar su desarrollo\n"
            "con una donación voluntaria. También 🍺."
        )
        donate_text.setWordWrap(True)
        donate_text.setAlignment(QtCore.Qt.AlignHCenter)

        btn_donate = QtWidgets.QPushButton("❤️ Donar con PayPal")
        btn_donate.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))

        def open_donation_page():
            QtGui.QDesktopServices.openUrl(
                QtCore.QUrl(app_meta.APP_URL_DONATE)
            )

        btn_donate.clicked.connect(open_donation_page)

        donate_layout.addStretch()
        donate_layout.addWidget(donate_text)
        donate_layout.addWidget(btn_donate, alignment=QtCore.Qt.AlignHCenter)
        donate_layout.addStretch()

        # ==========================================================
        # Enlaces + Donaciones (MISMA FILA)
        # ==========================================================
        links_row = QtWidgets.QWidget(self)
        links_row_layout = QtWidgets.QHBoxLayout(links_row)
        links_row_layout.setContentsMargins(0, 0, 0, 0)
        links_row_layout.setSpacing(12)

        links_row_layout.addWidget(links_group, 2)   # más ancho
        links_row_layout.addWidget(donate_group, 1)  # más estrecho

        layout.addWidget(links_row)

        # ==========================================================
        # Licencia (resumen)
        # ==========================================================
        license_group = QtWidgets.QGroupBox("Licencia")
        license_layout = QtWidgets.QVBoxLayout(license_group)

        license_summary = QtWidgets.QTextBrowser()
        license_summary.setReadOnly(True)
        license_summary.setFrameShape(QtWidgets.QFrame.NoFrame)
        license_summary.setOpenExternalLinks(False)
        license_summary.setStyleSheet("background: transparent;")

        license_summary.setText(
            "Este programa es software libre, distribuido bajo la licencia "
            "<b>GNU General Public License versión 3 (GPLv3)</b>."
            "Puedes usarlo, estudiarlo, modificarlo y redistribuirlo bajo los términos "
            "de dicha licencia.<br>"
            "Este programa se distribuye con la esperanza de que sea útil, pero "
            "<b>SIN NINGUNA GARANTÍA</b>; sin siquiera la garantía implícita de "
            "COMERCIABILIDAD o IDONEIDAD PARA UN PROPÓSITO PARTICULAR."
            "Consulta el texto completo de la licencia usando las acciones de abajo."
            "<br>"
            "This program is free software: you can redistribute it and/or modify "
            "it under the terms of the <b>GNU General Public License<b> as published by "
            "the Free Software Foundation, either version 3 of the License, or "
            "(at your option) any later version.<br>"
            "This program is distributed in the hope that it will be useful, "
            "but WITHOUT ANY WARRANTY; without even the implied warranty of "
            "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. "
            "See the GNU General Public License for more details."
        )
        
        license_layout.addWidget(license_summary)
        layout.addWidget(license_group)

        # ==========================================================
        # Acciones de licencia
        # ==========================================================
        actions_group = QtWidgets.QGroupBox("Acciones")
        actions_layout = QtWidgets.QHBoxLayout(actions_group)

        license_path = app_dir() / "LICENSE.txt"

        def load_license_text() -> str:
            """Carga el texto completo de la licencia desde LICENSE.txt."""
            return license_path.read_text(encoding="utf-8")

        def show_full_license():
            """
            Muestra el texto completo de la licencia en un diálogo modal.
            """
            dlg = QtWidgets.QDialog(self)
            dlg.setWindowTitle("Licencia GPLv3 completa")
            dlg.resize(720, 520)

            vbox = QtWidgets.QVBoxLayout(dlg)
            text = QtWidgets.QTextEdit()
            text.setReadOnly(True)

            try:
                text.setPlainText(load_license_text())
            except Exception as e:
                text.setPlainText(f"No se pudo cargar LICENSE.txt\n\n{e}")

            vbox.addWidget(text)

            buttons = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.Close
            )
            buttons.rejected.connect(dlg.reject)
            vbox.addWidget(buttons)

            dlg.exec()

        def copy_license():
            """
            Copia el texto completo de la licencia al portapapeles.
            """
            try:
                QtGui.QGuiApplication.clipboard().setText(
                    load_license_text()
                )
                QtWidgets.QMessageBox.information(
                    self,
                    "Licencia",
                    "El texto de la licencia se ha copiado al portapapeles.",
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error",
                    f"No se pudo copiar la licencia:\n{e}",
                )

        def open_license_file():
            """
            Abre el archivo LICENSE.txt con la aplicación por defecto.
            """
            try:
                os.startfile(os.fspath(license_path))
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error",
                    f"No se pudo abrir LICENSE.txt:\n{e}",
                )

        btn_view = QtWidgets.QPushButton("Ver licencia completa")
        btn_copy = QtWidgets.QPushButton("Copiar texto de la licencia")
        btn_open = QtWidgets.QPushButton("Abrir LICENSE.txt")

        btn_view.clicked.connect(show_full_license)
        btn_copy.clicked.connect(copy_license)
        btn_open.clicked.connect(open_license_file)

        # Desactivar acciones si no existe LICENSE.txt
        if not license_path.exists():
            btn_view.setEnabled(False)
            btn_copy.setEnabled(False)
            btn_open.setEnabled(False)

        actions_layout.addWidget(btn_view)
        actions_layout.addWidget(btn_copy)
        actions_layout.addWidget(btn_open)

        layout.addWidget(actions_group)

        # ==========================================================
        # Espaciador final
        # =================
        layout.addStretch()