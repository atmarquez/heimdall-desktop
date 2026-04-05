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
Pestaña de configuración General.

Este módulo define la clase `GeneralConfigTab`, correspondiente a la
pestaña “General” del diálogo de Configuración.

Responsabilidades:
- Selección de la carpeta base de categorías.
- Configuración del título de la aplicación.
- Comportamiento al iniciar, lanzar apps y cerrar.
- Posicionamiento de la ventana al interactuar con la bandeja.
- Configuración de la búsqueda web.
- Gestión del inicio automático con Windows.

IMPORTANT:
    Esta pestaña controla opciones de comportamiento global
    que afectan directamente a la experiencia de usuario.
"""

from PySide6 import QtWidgets
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QPushButton,
    QCheckBox, QComboBox, QLabel, QHBoxLayout
)

from config.service import default_app_title
from core.autostart import current_autostart_diagnostic


class GeneralConfigTab(QWidget):
    """
    Pestaña “General” del diálogo de Configuración.

    Permite al usuario ajustar opciones generales de funcionamiento
    de la aplicación, así como su integración con el sistema operativo.

    NOTE:
        Esta clase no aplica cambios directamente.
        Se limita a editar el diccionario de configuración (`cfg`).
    """

    def __init__(self, cfg: dict, parent=None):
        """
        Inicializa la pestaña General.

        Args:
            cfg (dict):
                Diccionario de configuración actual.
            parent (QWidget, optional):
                Widget padre.
        """
        super().__init__(parent)
        self.cfg = cfg
        self._build_ui()
        self.populate_from_cfg()

    def _build_ui(self):
        """
        Construye los controles visuales de la pestaña.
        """
        general_tab = self
        gen_form = QFormLayout(general_tab)

        # ---------------------------------------------------------
        # Carpeta base de categorías
        # ---------------------------------------------------------
        self.base_dir_edit = QLineEdit(general_tab)
        self.base_dir_edit.setText(self.cfg.get('base_dir', '.\\apps'))

        btn_browse_base = QPushButton('Examinar…', general_tab)
        btn_browse_base.clicked.connect(self.on_browse)

        h1 = QHBoxLayout()
        h1.addWidget(self.base_dir_edit)
        h1.addWidget(btn_browse_base)

        w1 = QWidget()
        w1.setLayout(h1)
        gen_form.addRow('Carpeta base de categorías:', w1)

        # ---------------------------------------------------------
        # Nombre de categoría raíz
        # ---------------------------------------------------------
        self.root_cat_edit = QLineEdit(general_tab)
        self.root_cat_edit.setText(
            self.cfg.get('root_category_name', 'Sin categoría')
        )
        gen_form.addRow(
            'Nombre para accesos en raíz:',
            self.root_cat_edit
        )

        # ---------------------------------------------------------
        # Título de la aplicación
        # ---------------------------------------------------------
        self.title_edit = QLineEdit(general_tab)
        self.title_edit.setText(
            self.cfg.get('app_title') or default_app_title()
        )
        gen_form.addRow(
            'Título de la aplicación:',
            self.title_edit
        )

        # ---------------------------------------------------------
        # Opciones de comportamiento
        # ---------------------------------------------------------
        self.cb_start_min = QCheckBox(
            'Iniciar minimizado a la bandeja',
            general_tab
        )
        self.cb_start_min.setChecked(
            self.cfg.get('start_minimized', True)
        )
        gen_form.addRow('', self.cb_start_min)

        self.cb_minimize = QCheckBox(
            'Minimizar a la bandeja al cerrar',
            general_tab
        )
        self.cb_minimize.setChecked(
            self.cfg.get('minimize_to_tray', True)
        )
        gen_form.addRow('', self.cb_minimize)

        self.cb_launch_min = QCheckBox(
            'Ocultar al lanzar una aplicación',
            general_tab
        )
        self.cb_launch_min.setChecked(
            self.cfg.get('launch_and_minimize', True)
        )
        gen_form.addRow('', self.cb_launch_min)

        # ---------------------------------------------------------
        # Comportamiento de inicio
        # ---------------------------------------------------------
        self.startup_combo = QComboBox(general_tab)
        self.startup_combo.addItems(
            ['grouped', 'flat', 'expand_all', 'collapse_all']
        )

        curr = self.cfg.get('startup_behavior', 'grouped')
        try:
            idx = ['grouped', 'flat', 'expand_all', 'collapse_all'].index(curr)
        except ValueError:
            idx = 0
        self.startup_combo.setCurrentIndex(idx)
        gen_form.addRow('Al iniciar:', self.startup_combo)

        # ---------------------------------------------------------
        # Posición al pulsar icono de bandeja
        # ---------------------------------------------------------
        self.position_combo = QComboBox(general_tab)
        self.position_combo.addItems(['bottom-right', 'cursor'])
        idx = (
            0
            if self.cfg.get('show_on_tray_click', 'bottom-right') == 'bottom-right'
            else 1
        )
        self.position_combo.setCurrentIndex(idx)
        gen_form.addRow(
            'Mostrar al pulsar el icono de bandeja:',
            self.position_combo
        )

        # ---------------------------------------------------------
        # URL de búsqueda web
        # ---------------------------------------------------------
        self.web_search_edit = QLineEdit(general_tab)
        self.web_search_edit.setPlaceholderText('https://…')
        self.web_search_edit.setText(
            self.cfg.get('web_search_url', 'https://www.bing.com')
        )
        gen_form.addRow(
            'URL para "Buscar en la web":',
            self.web_search_edit
        )

        # ---------------------------------------------------------
        # Inicio automático con Windows
        # ---------------------------------------------------------
        self.cb_autostart = QCheckBox(
            'Iniciar con Windows',
            general_tab
        )
        self.autostart_status_label = QLabel(
            '(diagnosticando...)',
            general_tab
        )

        _w_auto = QWidget(general_tab)
        _h_auto = QHBoxLayout(_w_auto)
        _h_auto.setContentsMargins(0, 0, 0, 0)
        _h_auto.addWidget(self.cb_autostart)
        _h_auto.addWidget(self.autostart_status_label, 1)

        gen_form.addRow('', _w_auto)

        self.autostart_method_combo = QComboBox(general_tab)
        self.autostart_method_combo.addItems(
            ['Registro (HKCU\\Run)', 'Carpeta Inicio (Startup)']
        )
        gen_form.addRow('Método:', self.autostart_method_combo)

        self.autostart_min_cb = QCheckBox(
            'Arrancar minimizado (--minimized)',
            general_tab
        )
        gen_form.addRow('', self.autostart_min_cb)

        # ---------------------------------------------------------
        # Cargar valores iniciales de autostart
        # ---------------------------------------------------------
        try:
            self.cb_autostart.setChecked(
                bool(self.cfg.get('autostart_enabled', False))
            )
            _meth = str(self.cfg.get('autostart_method', 'registry'))
            self.autostart_method_combo.setCurrentIndex(
                0 if _meth == 'registry' else 1
            )
            self.autostart_min_cb.setChecked(
                bool(self.cfg.get('autostart_minimized', True))
            )
        except Exception:
            pass

        # Diagnóstico del estado real del autostart
        try:
            self.autostart_status_label.setText(
                f"Actualmente: {current_autostart_diagnostic()}"
            )
        except Exception:
            self.autostart_status_label.setText(
                'Actualmente: Desconocido'
            )

    def populate_from_cfg(self):
        """
        Rellena los controles a partir de la configuración actual (`cfg`).
        """
        self.base_dir_edit.setText(
            self.cfg.get('base_dir', '.\\apps')
        )
        self.root_cat_edit.setText(
            self.cfg.get('root_category_name', 'Sin categoría')
        )
        self.title_edit.setText(
            self.cfg.get('app_title') or default_app_title()
        )

        self.cb_start_min.setChecked(
            self.cfg.get('start_minimized', True)
        )
        self.cb_minimize.setChecked(
            self.cfg.get('minimize_to_tray', True)
        )
        self.cb_launch_min.setChecked(
            self.cfg.get('launch_and_minimize', True)
        )

        sb = self.cfg.get('startup_behavior', 'grouped')
        try:
            self.startup_combo.setCurrentIndex(
                ['grouped', 'flat', 'expand_all', 'collapse_all'].index(sb)
            )
        except ValueError:
            self.startup_combo.setCurrentIndex(0)

        idx = (
            0
            if self.cfg.get('show_on_tray_click', 'bottom-right') == 'bottom-right'
            else 1
        )
        self.position_combo.setCurrentIndex(idx)

        self.web_search_edit.setText(
            self.cfg.get('web_search_url', 'https://www.bing.com')
        )

        # Autostart
        self.cb_autostart.setChecked(
            bool(self.cfg.get('autostart_enabled', False))
        )
        method = str(self.cfg.get('autostart_method', 'registry'))
        self.autostart_method_combo.setCurrentIndex(
            0 if method == 'registry' else 1
        )
        self.autostart_min_cb.setChecked(
            bool(self.cfg.get('autostart_minimized', True))
        )

        try:
            self.autostart_status_label.setText(
                f"Actualmente: {current_autostart_diagnostic()}"
            )
        except Exception:
            self.autostart_status_label.setText(
                "Actualmente: Desconocido"
            )

    def apply_to_cfg(self, cfg: dict):
        """
        Aplica los valores actuales de la UI al diccionario de configuración.

        Args:
            cfg (dict):
                Diccionario de configuración a actualizar.

        Returns:
            dict: Configuración resultante.
        """
        cfg['base_dir'] = self.base_dir_edit.text().strip()
        cfg['root_category_name'] = (
            self.root_cat_edit.text().strip() or 'Sin categoría'
        )
        cfg['app_title'] = (
            self.title_edit.text().strip() or default_app_title()
        )

        cfg['start_minimized'] = self.cb_start_min.isChecked()
        cfg['minimize_to_tray'] = self.cb_minimize.isChecked()
        cfg['launch_and_minimize'] = self.cb_launch_min.isChecked()

        cfg['startup_behavior'] = [
            'grouped', 'flat', 'expand_all', 'collapse_all'
        ][self.startup_combo.currentIndex()]

        cfg['show_on_tray_click'] = (
            'bottom-right'
            if self.position_combo.currentIndex() == 0
            else 'cursor'
        )

        cfg['web_search_url'] = (
            self.web_search_edit.text().strip() or 'https://www.bing.com'
        )

        cfg['autostart_enabled'] = self.cb_autostart.isChecked()
        cfg['autostart_method'] = (
            'registry'
            if self.autostart_method_combo.currentIndex() == 0
            else 'startup'
        )
        cfg['autostart_minimized'] = self.autostart_min_cb.isChecked()

        return cfg

    def on_browse(self):
        """
        Abre un diálogo para seleccionar la carpeta base de categorías.
        """
        dir_ = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            'Seleccionar carpeta base',
            self.base_dir_edit.text() or ''
        )
        if dir_:
            self.base_dir_edit.setText(dir_)