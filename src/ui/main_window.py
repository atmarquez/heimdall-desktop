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
Ventana principal del lanzador.

Este módulo define la clase `MainWindow`, que constituye el núcleo de la
interfaz gráfica de la aplicación.

Responsabilidades generales:
- Mostrar la lista de accesos y categorías.
- Gestionar el panel lateral (explorar, aplicaciones, menú inicio, búsqueda).
- Integrarse con la bandeja del sistema.
- Aplicar configuración visual y de comportamiento persistente.
- Coordinar acciones del usuario (crear, ejecutar, renombrar, eliminar).
- Delegar lógica de negocio al `AppController` y a otros servicios.

IMPORTANT:
    Este módulo es grande por diseño. Centraliza la experiencia de usuario
    completa del lanzador y actúa como orquestador de múltiples subsistemas
    (UI, sistema de archivos, scripts, servidor, scheduler).

NOTE:
    Aunque la clase contiene mucha lógica, se prioriza el código defensivo
    y la delegación externa siempre que es posible.
"""

# ------------------------------------------------------------
# Imports estándar y del sistema
# ------------------------------------------------------------

import os
import sys
import json
import shutil
import subprocess
import string
import ctypes
from ctypes import wintypes
from pathlib import Path
from typing import Optional, List, Tuple

# ------------------------------------------------------------
# Qt / PySide6
# ------------------------------------------------------------

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QIcon, QKeySequence, QShortcut, QAction, QActionGroup,
)

from PySide6.QtWidgets import (
    QMainWindow, QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QTreeWidgetItem, QLineEdit, QToolButton, QLabel,
    QFileDialog, QDialog, QFormLayout, QCheckBox, QPushButton,
    QMenu, QProgressBar, QToolBar, QFrame, QWidgetAction,
    QSpinBox, QRadioButton, QStyle
)

# ------------------------------------------------------------
# Configuración y servicios base
# ------------------------------------------------------------

from config.service import (
    load_config, save_config, default_app_title,
    app_dir, get_cfg_service
)

# ------------------------------------------------------------
# Núcleo de la aplicación
# ------------------------------------------------------------

from core.autostart import set_windows_autostart
from core.scheduler import TaskScheduler
from core.shortcuts import (
    sanitize_filename, unique_path, unique_dir,
    create_lnk_via_vbs, create_url_shortcut
)
from core.app_controller import AppController

# ------------------------------------------------------------
# UI interna y diálogos
# ------------------------------------------------------------

from ui.tree import AppTree, ROLE_PATH, ROLE_IS_DIR
from ui.dialogs.drop_import import DropImportDialog
from ui.dialogs.create_url_dialog import CreateUrlDialog
from ui.dialogs.create_shortcut_dialog import CreateShortcutDialog
from ui.dialogs.special_commands_dialog import SpecialCommandsDialog
from ui.config.dialog import ConfigDialog
from ui.dialogs.create_network_location_dialog import CreateNetworkLocationDialog

# Parches dinámicos del servidor HTTP
from ui.server.patches import apply_server_patches

# ------------------------------------------------------------
# Utilidades de shell y scripts
# ------------------------------------------------------------

from shell_utils import resolve_lnk, shell_execute
from core.scripts import clean_and_split_args_windows

# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------

from logutils.setup import get_logger
LOGGER = get_logger()

# ------------------------------------------------------------
# Extensiones permitidas (menú inicio, exploración, etc.)
# ------------------------------------------------------------

ALLOWED_EXTS = (
    '.lnk', '.exe', '.bat', '.cmd', '.vbs', '.url', '.website', '.vb'
)


class MainWindow(QMainWindow):
    """
    Ventana principal del lanzador.

    Esta clase implementa toda la experiencia principal de usuario:
    navegación de accesos, ejecución de aplicaciones, gestión de carpetas,
    integración con la bandeja del sistema y configuración visual.

    Características clave:
    - Vista jerárquica o plana de accesos.
    - Panel lateral con acciones rápidas.
    - Menús contextuales y atajos de teclado.
    - Persistencia de estado (ventana, vista, preferencias).
    - Integración con el controlador principal (`AppController`).

    WARNING:
        Debido a la cantidad de responsabilidades, esta clase es extensa.
        Cualquier refactorización debe hacerse con extremo cuidado.

    NOTE:
        El diseño prioriza robustez y experiencia de usuario frente
        a simplicidad estructural.
    """
    
    def __init__(self):
        """
        Inicializa la ventana principal de la aplicación.

        Este método construye completamente la interfaz gráfica,
        inicializa el estado interno, aplica la configuración persistente
        y conecta todos los elementos de interacción del usuario.

        Flujo general:
        1. Inicialización temprana del controlador y configuración.
        2. Aplicación de tema y barra de título.
        3. Construcción completa de la UI (toolbar, paneles, árbol, menús).
        4. Configuración de tray icon y atajos de teclado.
        5. Carga inicial de datos y estado persistente.
        6. Inicialización de servicios auxiliares (scheduler, scripts).

        IMPORTANT:
            Este método es largo por diseño. Centraliza la creación
            de la experiencia de usuario completa.

        Args:
            self: Instancia de MainWindow.

        Returns:
            None
        """
        # Flag interno para evitar guardar estado antes de tiempo
        self._ui_ready = False

        super().__init__()

        # ---------------------------------------------------------
        # Cargar configuración persistente
        # ---------------------------------------------------------
        self.cfg = load_config()

        # ---------------------------------------------------------
        # Crear controlador principal LO ANTES POSIBLE
        # ---------------------------------------------------------
        # IMPORTANT:
        #   El AppController coordina scripts, configuración en caliente
        #   y eventos de ciclo de vida.
        self.controller = AppController(self)

        # ---------------------------------------------------------
        # Aplicación inicial de tema y barra de título
        # ---------------------------------------------------------
        from themes.theme_manager import ThemeManager
        ThemeManager.apply_theme(QtWidgets.QApplication.instance(), self.cfg)
        ThemeManager.apply_titlebar(self, self.cfg)

        try:
            LOGGER.info('Aplicación iniciada.')
        except Exception:
            LOGGER.exception('[auto] Exception capturada en MainWindow::__init__')

        # ---------------------------------------------------------
        # Configuración básica de ventana
        # ---------------------------------------------------------
        self.setWindowTitle(
            self.cfg.get('app_title') or default_app_title()
        )
        self.resize(
            self.cfg.get('window', {}).get('width', 520),
            self.cfg.get('window', {}).get('height', 640)
        )
        self.setMinimumSize(320, 360)

        # Restaurar posición de la ventana (defensivo)
        try:
            _winpos = (
                self.cfg.get('window', {})
                if isinstance(self.cfg.get('window', {}), dict)
                else {}
            )
            _x, _y = (_winpos.get('x', None), _winpos.get('y', None))
            if isinstance(_x, (int, float)) and isinstance(_y, (int, float)):
                _x, _y = self._clamp_position_to_screens(
                    int(_x), int(_y),
                    self.width(), self.height()
                )
                self.move(_x, _y)
        except Exception:
            LOGGER.exception('[auto] Exception capturada en MainWindow::__init__')

        # ---------------------------------------------------------
        # Icono de aplicación
        # ---------------------------------------------------------
        self.app_icon_path = str(get_cfg_service().app_icon_path())
        self.setWindowIcon(QIcon(self.app_icon_path))

        # ---------------------------------------------------------
        # Estado interno
        # ---------------------------------------------------------
        self.icon_cache = {}
        self._start_menu_filter = ''
        self._internal_clipboard = {'paths': [], 'cut': False}

        # ---------------------------------------------------------
        # Estructura base de layouts
        # ---------------------------------------------------------
        central = QWidget(self)
        self.setCentralWidget(central)

        outer = QVBoxLayout(central)
        outer.setContentsMargins(6, 6, 6, 6)
        outer.setSpacing(6)

        # ---------------------------------------------------------
        # Toolbar superior (modo de vista)
        # ---------------------------------------------------------
        self.toolbar = QToolBar('Vista', self)
        self.addToolBar(QtCore.Qt.TopToolBarArea, self.toolbar)
        self.toolbar.setMovable(False)

        self.act_grouped = QAction('Ver por categorías', self)
        self.act_grouped.setCheckable(True)

        self.act_flat = QAction('Ver todos', self)
        self.act_flat.setCheckable(True)

        ag = QActionGroup(self)
        ag.setExclusive(True)
        ag.addAction(self.act_grouped)
        ag.addAction(self.act_flat)

        self.toolbar.addAction(self.act_grouped)
        self.toolbar.addAction(self.act_flat)
        self.toolbar.addSeparator()

        self.act_expand = QAction('Desplegar todo', self)
        self.act_collapse = QAction('Contraer todo', self)

        self.toolbar.addAction(self.act_expand)
        self.toolbar.addAction(self.act_collapse)

        self.act_grouped.triggered.connect(self.set_view_grouped)
        self.act_flat.triggered.connect(self.set_view_flat)
        self.act_expand.triggered.connect(self.expand_all)
        self.act_collapse.triggered.connect(self.collapse_all)

        # ---------------------------------------------------------
        # Cuerpo principal (panel izquierdo + derecho)
        # ---------------------------------------------------------
        body = QWidget(self)
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # ---------------------------------------------------------
        # Panel izquierdo: búsqueda + árbol de apps
        # ---------------------------------------------------------
        left = QWidget(objectName='leftPanel')
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 4)
        left_layout.setSpacing(6)

        self.search_edit = QLineEdit(objectName='searchEdit')
        self.search_edit.setPlaceholderText('Buscar…')
        self.search_edit.textChanged.connect(self.apply_filter)
        left_layout.addWidget(self.search_edit)

        self.tree = AppTree(self)
        self.tree.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(
            self.on_tree_context_menu
        )
        self.tree.itemActivated.connect(self.on_item_activated)
        left_layout.addWidget(self.tree, 1)

        # ---------------------------------------------------------
        # Barra inferior izquierda: estado y disco
        # ---------------------------------------------------------
        bottom = QWidget(objectName='bottomBar')
        bottom_layout = QtWidgets.QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(6, 2, 6, 2)

        self.status_label = QLabel('')
        bottom_layout.addWidget(self.status_label)

        self.disk_bar = QProgressBar(objectName='diskBar')
        self.disk_bar.setRange(0, 100)
        self.disk_bar.setFixedHeight(12)
        self.disk_bar.setInvertedAppearance(True)
        bottom_layout.addWidget(self.disk_bar)

        left_layout.addWidget(bottom)

        # ---------------------------------------------------------
        # Panel derecho: acciones rápidas
        # ---------------------------------------------------------
        right = QWidget(objectName='rightPanel')
        right.setFixedWidth(210)

        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(6)

        def side_button(text, icon_name, slot=None) -> QToolButton:
            """
            Crea un botón lateral estándar.

            Args:
                text (str): Texto del botón.
                icon_name (str): Nombre del icono estándar Qt.
                slot (callable, optional): Slot a conectar.

            Returns:
                QToolButton
            """
            btn = QToolButton()
            btn.setObjectName('sideBtn')
            btn.setToolButtonStyle(
                QtCore.Qt.ToolButtonTextBesideIcon
            )
            btn.setIcon(
                self.style().standardIcon(
                    getattr(QtWidgets.QStyle, icon_name)
                )
            )
            btn.setText(text)
            if slot:
                btn.clicked.connect(slot)
            return btn

        def vseparator() -> QFrame:
            """
            Crea un separador visual horizontal.

            Returns:
                QFrame
            """
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            line.setFixedHeight(12)
            return line

        # ---------------------------------------------------------
        # Botones rápidos y auto-inicio
        # ---------------------------------------------------------
        right_layout.addWidget(
            side_button('Explorar', 'SP_DirIcon', self.open_base_dir)
        )

        self.quick_box = QWidget(objectName='quickButtonsBox')
        self.quick_box_layout = QVBoxLayout(self.quick_box)
        self.quick_box_layout.setContentsMargins(0, 0, 0, 0)
        self.quick_box_layout.setSpacing(4)
        right_layout.addWidget(self.quick_box)

        self.rebuild_quick_buttons()

        # Aplicar auto-inicio con Windows (defensivo)
        try:
            self._apply_autostart_settings()
        except Exception:
            pass

        # ---------------------------------------------------------
        # Menú "Aplicaciones"
        # ---------------------------------------------------------
        right_layout.addWidget(vseparator())

        apps_btn = side_button('Aplicaciones', 'SP_DesktopIcon')
        apps_menu = QMenu(apps_btn)

        style = self.style()

        # ✅ Nuevo acceso web…
        act_web = QAction(
            style.standardIcon(QStyle.SP_FileLinkIcon),
            'Nuevo acceso web…',
            self
        )
        act_web.triggered.connect(self.create_web_shortcut)
        apps_menu.addAction(act_web)

        # ✅ Nuevo acceso directo…
        act_shortcut = QAction(
            style.standardIcon(QStyle.SP_FileIcon),
            'Nuevo acceso directo…',
            self
        )
        act_shortcut.triggered.connect(self.create_desktop_shortcut)
        apps_menu.addAction(act_shortcut)

        # Separador visual
        apps_menu.addSeparator()

        # ✅ Ubicaciones de red…
        apps_menu.addAction(
            style.standardIcon(QStyle.SP_DirLinkIcon),
            'Nueva ubicación de red…',
            lambda: self.create_network_location()
        )

        apps_menu.addSeparator()

        # ✅ Comandos especiales…
        act_special = QAction(
            style.standardIcon(QStyle.SP_FileDialogInfoView),
            'Comandos especiales…',
            self
        )
        act_special.triggered.connect(self.open_special_commands)
        apps_menu.addAction(act_special)

        apps_btn.setMenu(apps_menu)
        apps_btn.setPopupMode(QToolButton.InstantPopup)
        right_layout.addWidget(apps_btn)

        # ---------------------------------------------------------
        # Botón "Este equipo"
        # ---------------------------------------------------------
        computer_btn = side_button('Este equipo', 'SP_DriveHDIcon')
        computer_menu = QMenu(computer_btn)
        computer_btn.setMenu(computer_menu)
        computer_btn.setPopupMode(QToolButton.InstantPopup)

        def populate_computer_menu():
            """
            Construye dinámicamente el menú de unidades disponibles.
            Se evalúa en cada apertura para reflejar cambios del sistema.
            """
            computer_menu.clear()

            drives = self.list_windows_drives()
            if not drives:
                a = computer_menu.addAction('No se detectaron unidades')
                a.setEnabled(False)
                return

            for drive in drives:
                drive_clean = drive.rstrip("\\")

                label = self.get_display_label(drive)
                net_path = self.get_network_path(drive)

                if net_path:
                    # Unidad de red
                    # \\192.168.1.245\Datos → Datos (\\192.168.1.245)
                    server = net_path.split("\\")[2]
                    share = net_path.split("\\")[3]
                    text = f"{drive_clean} {share} (\\\\{server})"
                elif label:
                    # Unidad local con etiqueta
                    text = f"{drive_clean} {label}"
                else:
                    text = drive_clean

                icon = self.get_drive_icon(drive)

                act = computer_menu.addAction(icon, text)
                act.triggered.connect(
                    lambda _, d=drive: self.open_drive_in_explorer(d)
                )

        computer_menu.aboutToShow.connect(populate_computer_menu)
        right_layout.addWidget(computer_btn)

        # ---------------------------------------------------------
        # Menú Inicio
        # ---------------------------------------------------------
        start_btn = side_button('Menú Inicio', 'SP_DirHomeIcon')
        start_menu = QMenu(start_btn)
        start_btn.setMenu(start_menu)
        start_btn.setPopupMode(QToolButton.InstantPopup)
        start_menu.aboutToShow.connect(
            lambda m=start_menu: self.populate_start_menu(m)
        )
        right_layout.addWidget(start_btn)

        # ---------------------------------------------------------
        # Configuración
        # ---------------------------------------------------------
        cfg_btn = side_button(
            'Configuración',
            'SP_FileDialogDetailedView',
            self.open_config
        )
        cfg_btn.setObjectName('configBtn')
        right_layout.addWidget(cfg_btn)

        # ---------------------------------------------------------
        # Búsqueda
        # ---------------------------------------------------------
        right_layout.addWidget(vseparator())

        search_btn = side_button('Buscar', 'SP_FileDialogContentsView')
        search_menu = QMenu(search_btn)
        search_menu.addAction(
            'Buscar en la computadora…'
        ).triggered.connect(self.open_windows_search)
        search_menu.addAction(
            'Buscar en la web…'
        ).triggered.connect(self.open_web_search)

        search_btn.setMenu(search_menu)
        search_btn.setPopupMode(QToolButton.InstantPopup)
        right_layout.addWidget(search_btn)

        # ---------------------------------------------------------
        # Botones inferiores: Ayuda / Salir
        # ---------------------------------------------------------
        bottom_row = QWidget(right)
        bottom_row_layout = QtWidgets.QHBoxLayout(bottom_row)
        bottom_row_layout.setContentsMargins(0, 0, 0, 0)
        bottom_row_layout.setSpacing(6)

        help_btn = side_button(
            'Ayuda',
            'SP_MessageBoxInformation',
            self.show_help
        )
        help_btn.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        help_btn.setFixedHeight(32)

        exit_btn = side_button(
            'Salir',
            'SP_DialogCloseButton',
            self._confirm_and_quit
        )
        exit_btn.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        exit_btn.setFixedHeight(32)

        bottom_row_layout.addWidget(help_btn, 1)
        bottom_row_layout.addWidget(exit_btn, 1)

        right_layout.addStretch(1)
        right_layout.addWidget(bottom_row)

        # ---------------------------------------------------------
        # Integración final de paneles
        # ---------------------------------------------------------
        body_layout.addWidget(left, 1)
        body_layout.addWidget(right, 0)
        outer.addWidget(body)

        # ---------------------------------------------------------
        # Reaplicar tema y barra de título tras construir UI
        # ---------------------------------------------------------
        from themes.theme_manager import ThemeManager
        ThemeManager.apply_theme(
            QtWidgets.QApplication.instance(),
            self.cfg
        )
        ThemeManager.apply_titlebar(self, self.cfg)

        # Colores avanzados de barra de título (Windows)
        self._apply_titlebar_colors()

        # ---------------------------------------------------------
        # Bandeja del sistema (tray icon)
        # ---------------------------------------------------------
        self.tray = QtWidgets.QSystemTrayIcon(
            QIcon(self.app_icon_path),
            self
        )
        self.tray.setToolTip(
            self.cfg.get('app_title') or default_app_title()
        )
        self.tray.activated.connect(self.on_tray_activated)

        menu = QMenu()
        menu.addAction('Mostrar/Ocultar', self.toggle_show)
        menu.addSeparator()
        menu.addAction('Recargar', self.load_categories)
        menu.addSeparator()
        menu.addAction('Configuración…', self.open_config)
        menu.addSeparator()
        menu.addAction('Ayuda', lambda: open_help_page('index'))
        menu.addSeparator()
        menu.addAction('Salir', QApplication.instance().quit)

        self.tray.setContextMenu(menu)
        self.tray.show()

        # ---------------------------------------------------------
        # Atajos de teclado globales de la ventana
        # ---------------------------------------------------------
        QShortcut(QKeySequence('Return'), self, self.activate_selected)
        QShortcut(QKeySequence('Enter'), self, self.activate_selected)
        QShortcut(QKeySequence('Esc'), self, self.hide)
        QShortcut(QKeySequence('F5'), self, self.load_categories)
        QShortcut(QKeySequence('Ctrl+C'), self, self.copy_selection)
        QShortcut(QKeySequence('Ctrl+X'), self, self.cut_selection)
        QShortcut(QKeySequence('Ctrl+V'), self, self.paste_into_target)
        QShortcut(QKeySequence('Delete'), self, self.delete_current)
        QShortcut(QKeySequence('F2'), self, self.rename_current)
        QShortcut(QKeySequence('Ctrl+N'), self, self.create_subfolder_here)

        # ---------------------------------------------------------
        # Estado inicial de la vista
        # ---------------------------------------------------------
        self.sync_view_buttons()
        self.load_categories()
        self.update_disk_status()
        self.apply_startup_behavior()

        # ---------------------------------------------------------
        # Script de arranque de la aplicación
        # ---------------------------------------------------------
        self.controller.run_pre_start_script()

        # ---------------------------------------------------------
        # Cierre de aplicación
        # ---------------------------------------------------------
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._on_about_to_quit)

        # ---------------------------------------------------------
        # Inicialización del programador de tareas
        # ---------------------------------------------------------
        try:
            def _qt_timer_factory(
                callback,
                single_shot=False,
                delay_ms=30000
            ):
                t = QtCore.QTimer(self)
                t.setInterval(delay_ms)
                t.setSingleShot(bool(single_shot))
                t.timeout.connect(callback)
                t.start()
                return t

            self.scheduler = TaskScheduler(
                cfg=self.cfg,
                run_script_cb=self._run_script,
                save_cfg_cb=save_config,
                timer_factory=_qt_timer_factory,
            )
        except Exception:
            try:
                LOGGER.exception(
                    '[auto] Error iniciando programador de tareas'
                )
            except Exception:
                pass

            min_arg = any(
                (a or '').lower() == '--minimized'
                for a in sys.argv[1:]
            )
            if min_arg or self.cfg.get('start_minimized', True):
                QtCore.QTimer.singleShot(150, self.hide)
            else:
                self.position_and_show()

        # ---------------------------------------------------------
        # Fin de inicialización UI
        # ---------------------------------------------------------
        self._ui_ready = True

    def create_network_location(self):
        """
        Abre el diálogo de creación de ubicaciones de red y crea el acceso correspondiente.

        Este método:
        - Muestra un diálogo modal para introducir la ubicación.
        - Crea el acceso en el directorio adecuado.
        - Refresca el árbol y selecciona el nuevo elemento.

        WARNING:
            Cualquier error durante la creación se muestra al usuario,
            pero no se propaga como excepción.
        """
        dlg = CreateNetworkLocationDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return

        try:
            path = dlg.create_location(self.target_dir_for_new_url())
            self.load_categories()
            self.select_item_by_path(path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Error',
                f'No se pudo crear la ubicación de red:\n{e}'
            )

    def open_drive_in_explorer(self, drive_path: str):
        """
        Abre la unidad indicada en el Explorador de Windows.

        Args:
            drive_path: Ruta raíz de la unidad (por ejemplo: 'C:\\').

        NOTE:
            Este método depende de `os.startfile`, exclusivo de Windows.
        """
        try:
            os.startfile(drive_path)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Error',
                f'No se pudo abrir la unidad {drive_path}\n\n{e}'
            )

    def list_windows_drives(self):
        """
        Devuelve una lista de unidades disponibles en el sistema.

        Returns:
            Lista de rutas raíz de unidades detectadas.
            Ejemplo: ['C:\\', 'D:\\', 'Z:\\']

        NOTE:
            Solo válido en sistemas Windows.
        """
        drives = []
        try:
            for letter in string.ascii_uppercase:
                path = f"{letter}:\\"
                if os.path.exists(path):
                    drives.append(path)
        except Exception:
            pass
        return drives

    def get_drive_label_option_2(self, drive_path: str) -> str:
        """
        Devuelve el nombre (etiqueta) del volumen usando WinAPI.

        Args:
            drive_path: Ruta de la unidad (por ejemplo 'C:\\').

        Returns:
            Etiqueta del volumen o cadena vacía si no se puede obtener.
        """
        try:
            volume_name = ctypes.create_unicode_buffer(261)
            fs_name = ctypes.create_unicode_buffer(261)

            serial_number = wintypes.DWORD()
            max_component_len = wintypes.DWORD()
            file_system_flags = wintypes.DWORD()

            res = ctypes.windll.kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(drive_path),
                volume_name,
                ctypes.sizeof(volume_name),
                ctypes.byref(serial_number),
                ctypes.byref(max_component_len),
                ctypes.byref(file_system_flags),
                fs_name,
                ctypes.sizeof(fs_name),
            )

            if res:
                return volume_name.value.strip()
        except Exception:
            pass

        return ''

    def get_drive_label(self, drive):
        """
        Devuelve la etiqueta de una unidad usando WinAPI con fallback.

        Args:
            drive: Ruta de la unidad (por ejemplo 'D:\\').

        Returns:
            Etiqueta del volumen o cadena vacía.
        """
        vol_name_buf = ctypes.create_unicode_buffer(1024)
        fs_name_buf = ctypes.create_unicode_buffer(1024)

        res = ctypes.windll.kernel32.GetVolumeInformationW(
            drive,
            vol_name_buf,
            ctypes.sizeof(vol_name_buf),
            None,
            None,
            None,
            fs_name_buf,
            ctypes.sizeof(fs_name_buf),
        )

        if res:
            return vol_name_buf.value

        # Fallback alternativo
        return self.get_drive_label_option_2(drive)

    def get_display_label(self, drive):
        """
        Devuelve la etiqueta visible a mostrar para una unidad.

        Prioridad:
        1. Etiqueta real del volumen.
        2. Detectar instalación de Windows.
        3. Sin etiqueta (None).

        Args:
            drive: Ruta de la unidad.

        Returns:
            Cadena a mostrar o None.
        """
        label = self.get_drive_label(drive)
        if label:
            return label

        windows_dir = os.path.join(drive, "Windows")
        if os.path.isdir(windows_dir):
            return "Windows"

        return None

    def get_network_path(self, drive):
        """
        Devuelve la ruta UNC asociada a una unidad de red.

        Args:
            drive: Letra de unidad ('X:\\').

        Returns:
            Ruta de red UNC o None si no existe.
        """
        import ctypes

        buffer = ctypes.create_unicode_buffer(1024)
        size = ctypes.c_ulong(len(buffer))

        res = ctypes.windll.mpr.WNetGetConnectionW(
            drive[:2],  # "X:"
            buffer,
            ctypes.byref(size)
        )

        if res == 0:
            return buffer.value

        return None

    def get_drive_type(self, drive):
        """
        Devuelve el tipo de unidad según la API de Windows.

        Args:
            drive: Ruta de la unidad.

        Returns:
            Entero representando el tipo de unidad.
        """
        return ctypes.windll.kernel32.GetDriveTypeW(drive)

    def get_drive_icon(self, drive):
        """
        Devuelve el icono apropiado para una unidad según su tipo.

        Args:
            drive: Ruta de la unidad.

        Returns:
            QIcon correspondiente al tipo de unidad.
        """
        drive_type = self.get_drive_type(drive)
        style = QApplication.style()

        if drive_type == 3:      # DRIVE_FIXED
            return style.standardIcon(QStyle.SP_DriveHDIcon)
        elif drive_type == 4:    # DRIVE_REMOTE
            return style.standardIcon(QStyle.SP_DriveNetIcon)
        elif drive_type == 2:    # DRIVE_REMOVABLE
            return style.standardIcon(QStyle.SP_DriveFDIcon)
        elif drive_type == 5:    # DRIVE_CDROM
            return style.standardIcon(QStyle.SP_DriveCDIcon)
        else:
            return style.standardIcon(QStyle.SP_ComputerIcon)

    def apply_startup_behavior(self):
        """
        Aplica el comportamiento de inicio configurado por el usuario.

        Puede ajustar:
        - Modo de vista (agrupada o plana).
        - Expansión o colapso del árbol.
        """
        sb = self.cfg.get('startup_behavior', 'grouped')
        if sb == 'grouped':
            if self.cfg.get('view_mode') != 'grouped':
                self.set_view_grouped()
        elif sb == 'flat':
            if self.cfg.get('view_mode') != 'flat':
                self.set_view_flat()
        elif sb == 'expand_all':
            self.expand_all()
        elif sb == 'collapse_all':
            self.collapse_all()

    def _apply_titlebar_colors(self):
        """
        Aplica colores personalizados a la barra de título mediante DWM.

        NOTE:
            - El soporte depende de la versión de Windows.
            - En Windows 10 algunos ajustes se ignoran.
        """
        try:
            bg_hex = (self.cfg.get('titlebar_color') or '').strip()
            fg_hex = (self.cfg.get('titlebar_text_color') or '').strip()

            def _hx(h):
                if not h:
                    return None
                s = h.strip()
                if s.startswith('#'):
                    s = s[1:]
                if len(s) != 6:
                    return None
                try:
                    return (
                        int(s[0:2], 16),
                        int(s[2:4], 16),
                        int(s[4:6], 16),
                    )
                except Exception:
                    return None

            bg = _hx(bg_hex)
            fg = _hx(fg_hex)

            dark = None
            try:
                if bool(self.cfg.get('titlebar_align_dark_mode', False)):
                    dark = bool(win_is_dark_mode())
            except Exception:
                dark = None

            hwnd = int(self.winId())
            set_windows_titlebar_color(
                hwnd,
                rgb_tuple=bg,
                text_rgb_tuple=fg,
                dark_mode=dark,
            )

            try:
                import sys as __sys
                if __sys.getwindowsversion().build < 22000 and (bg or fg):
                    try:
                        LOGGER.info(
                            'Windows 10: colores de barra ignorados; '
                            'solo se aplica modo oscuro/claro.'
                        )
                    except Exception:
                        pass
            except Exception:
                pass

        except Exception:
            pass

    def base_dir(self) -> Path:
        """
        Devuelve la carpeta base donde se almacenan los accesos.

        Returns:
            Path absoluto del directorio base.
        """
        return Path(self.cfg.get('base_dir', '.\\apps')).expanduser()

    def update_disk_status(self):
        """
        Actualiza el estado de uso del disco en la barra de estado.
        """
        try:
            anchor = (
                self.base_dir().anchor
                or Path.cwd().anchor
                or Path('C:/').anchor
            )
            total, used, free = shutil.disk_usage(anchor)
            gb = 1024 ** 3
            percent_free = int(free / total * 100) if total else 0

            label = anchor.rstrip('\\/')
            self.status_label.setText(
                f'({label}) {free // gb}GB libre de {total // gb}GB ({percent_free}%)'
            )
            self.disk_bar.setValue(percent_free)

        except Exception:
            self.status_label.setText('')
            self.disk_bar.setValue(0)

    def open_base_dir(self):
        """
        Abre el directorio base de accesos en el Explorador.
        """
        os.startfile(os.fspath(self.base_dir()))

    def quick_buttons_defaults(self):
        """
        Devuelve la configuración por defecto de los botones rápidos.

        Returns:
            Lista de diccionarios con definiciones de botones.
        """
        home = Path.home()
        return [
            {'enabled': True, 'title': 'Documentos', 'path': str(home / 'Documents'), 'icon': ''},
            {'enabled': True, 'title': 'Música', 'path': str(home / 'Music'), 'icon': ''},
            {'enabled': True, 'title': 'Imágenes', 'path': str(home / 'Pictures'), 'icon': ''},
            {'enabled': True, 'title': 'Vídeo', 'path': str(home / 'Videos'), 'icon': ''},
            {'enabled': True, 'title': 'Descargas', 'path': str(home / 'Downloads'), 'icon': ''},
        ]

    def _expand_user_path(self, p: str):
        """
        Expande variables de entorno y rutas de usuario en una ruta.

        Convierte expresiones como:
        - '~'
        - '%USERPROFILE%'
        en rutas absolutas válidas.

        Args:
            p: Ruta original como cadena.

        Returns:
            Path expandido o None si no se proporciona ruta.
        """
        if not p:
            return None
        try:
            s = os.path.expandvars(os.path.expanduser(p))
            return Path(s)
        except Exception:
            # Fallback defensivo: devolver la ruta original
            return Path(p)

    def _icon_for_quick_button(self, icon_path_str: str):
        """
        Devuelve un icono válido para un botón rápido.

        Soporta:
        - Ejecutables (.exe)
        - Bibliotecas (.dll)
        - Accesos directos (.lnk)

        Args:
            icon_path_str: Ruta al recurso del icono.

        Returns:
            QIcon o None si no se puede obtener un icono válido.
        """
        icon_path_str = (icon_path_str or '').strip()
        if not icon_path_str:
            return None

        try:
            from PySide6 import QtCore, QtWidgets, QtGui

            ip = self._expand_user_path(icon_path_str)
            if not ip or not ip.exists():
                return None

            suf = ip.suffix.lower()
            if suf in ('.exe', '.dll', '.lnk'):
                provider = QtWidgets.QFileIconProvider()
                return provider.icon(QtCore.QFileInfo(str(ip)))

                # NOTA: código inalcanzable conservado a propósito
                return QtGui.QIcon(str(ip))

        except Exception:
            return None

    def open_quick_button(self, index: int):
        """
        Abre el destino asociado a un botón rápido.

        Args:
            index: Índice del botón rápido.
        """
        qbs = self.cfg.get('quick_buttons') or self.quick_buttons_defaults()
        if index < 0 or index >= len(qbs):
            return

        target = self._expand_user_path(qbs[index].get('path', ''))
        if target and target.exists():
            try:
                os.startfile(os.fspath(target))
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    'Error',
                    f'No se pudo abrir la carpeta:\n{e}',
                )
        else:
            QtWidgets.QMessageBox.information(
                self,
                'Información',
                'El destino configurado no existe.',
            )

    def rebuild_quick_buttons(self):
        """
        Reconstruye los botones rápidos del panel lateral.

        Este método:
        - Elimina botones existentes.
        - Carga configuración y valores por defecto.
        - Limita el número máximo de botones visibles.
        """
        if not hasattr(self, 'quick_box_layout'):
            return

        # Eliminar botones existentes
        while self.quick_box_layout.count():
            item = self.quick_box_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        qbs = self.cfg.get('quick_buttons') or self.quick_buttons_defaults()
        defaults = self.quick_buttons_defaults()

        # Combinar configuración y valores por defecto
        qbs = (qbs + defaults)[:5]

        for idx, qb in enumerate(qbs):
            if not qb.get('enabled', True):
                continue

            title = qb.get('title') or f'Botón {idx + 1}'
            btn = QToolButton()
            btn.setObjectName('sideBtn')
            btn.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)

            icon = self._icon_for_quick_button(qb.get('icon', ''))
            if icon is None:
                icon = self.style().standardIcon(
                    getattr(QtWidgets.QStyle, 'SP_DirIcon')
                )

            btn.setIcon(icon)
            btn.setText(title)
            btn.clicked.connect(lambda _, i=idx: self.open_quick_button(i))

            self.quick_box_layout.addWidget(btn)

    def show_help(self):
        """
        Muestra el cuadro de ayuda básica de la aplicación.
        """
        QtWidgets.QMessageBox.information(
            self,
            'Ayuda',
            "Coloca tus accesos en subcarpetas o en la raíz de la carpeta base.\n"
            "Doble clic o Enter para ejecutar. Usa Configuración para cambiar "
            "título, icono, carpetas y preferencias.\n"
            "Atajos: Enter (ejecutar), Esc (ocultar), F5 (recargar), "
            "F2 (renombrar), Supr (eliminar), Ctrl+C/Ctrl+X/Ctrl+V "
            "(copiar/cortar/pegar), Ctrl+N (nueva carpeta).\n"
            "Tip: Usa el panel derecho para crear accesos, abrir el "
            "menú Inicio o buscar localmente o en la web.\n"
        )

    def _confirm_and_quit(self):
        """
        Solicita confirmación al usuario y cierra la aplicación.
        """
        try:
            reply = QtWidgets.QMessageBox.question(
                self,
                'Salir',
                '¿Quieres salir de la aplicación?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if reply == QtWidgets.QMessageBox.Yes:
                app = QtWidgets.QApplication.instance()
                if app is not None:
                    app.quit()
        except Exception:
            # Fallback si QMessageBox falla
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.quit()

    def _restart_app(self):
        """
        Reinicia la aplicación lanzando un nuevo proceso y cerrando el actual.
        """
        try:
            if getattr(sys, 'frozen', False):
                exe = sys.executable
                subprocess.Popen([exe])
            else:
                script = os.fspath(Path(__file__).resolve())
                subprocess.Popen([sys.executable, script])
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Reinicio',
                f'No se pudo reiniciar automáticamente:\n{e}',
            )
        finally:
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.quit()

    def open_config(self):
        """
        Abre el diálogo de configuración y aplica los cambios.
        """
        # IMPORTANTE: cargar siempre la configuración actual desde disco
        self.cfg = load_config()
        old_cfg = self.cfg.copy()

        dlg = ConfigDialog(self.cfg, self)
        if dlg.exec() != QDialog.Accepted:
            return

        # Volver a cargar cambios persistidos
        self.cfg = load_config()

        self.controller.apply_config_live(old_cfg, self.cfg)

        try:
            self._apply_autostart_settings()
        except Exception:
            pass

    def _server_params_tuple(self, cfg):
        """
        Devuelve los parámetros del servidor en forma de tupla normalizada.

        Args:
            cfg: Diccionario de configuración.

        Returns:
            Tupla con los parámetros del servidor.
        """
        try:
            return (
                bool(cfg.get('server_enabled', False)),
                int(cfg.get('server_port', 8080) or 8080),
                bool(cfg.get('server_local_only', True)),
                int(cfg.get('server_throttle_window_sec', 30) or 30),
                int(cfg.get('server_throttle_base_ms', 100) or 100),
                int(cfg.get('server_throttle_max_ms', 1000) or 1000),
                int(cfg.get('server_throttle_threshold', 3) or 3),
                bool(cfg.get('server_tls_enabled', False)),
                str(cfg.get('server_tls_certfile', '') or ''),
                str(cfg.get('server_tls_keyfile', '') or ''),
                str(
                    cfg.get(
                        'server_tls_min_version',
                        'TLS1.2'
                    ) or 'TLS1.2'
                ).upper(),
            )
        except Exception:
            # Fallback seguro con valores por defecto
            return (
                False, 8080, True, 30,
                100, 1000, 3,
                False, '', '', 'TLS1.2'
            )

    def _refresh_ui_from_cfg(self):
        """
        Sincroniza la interfaz gráfica con la configuración actual.
        """
        self.sync_view_buttons()
        self.load_categories()
        self.update_disk_status()
        self.rebuild_quick_buttons()

    def toggle_show(self):
        """
        Alterna entre mostrar y ocultar la ventana principal.
        """
        if self.isVisible():
            self.hide()
        else:
            self.setWindowState(QtCore.Qt.WindowNoState)
            self.show()
            self.raise_()
            self.activateWindow()

    def _minimize_to_tray(self):
        """
        Minimiza la ventana a la bandeja del sistema.
        """
        # Limpiar estado minimizado antes de ocultar
        self.setWindowState(QtCore.Qt.WindowNoState)

        if not self.cfg.get('tray_notice_shown', False):
            QtWidgets.QMessageBox.information(
                self,
                "Bandeja del sistema",
                "La aplicación seguirá ejecutándose en la bandeja del sistema.\n"
                "Puedes cerrarla desde el icono de la bandeja."
            )
            self.cfg['tray_notice_shown'] = True
            save_config(self.cfg)

        self.hide()

    def position_and_show(self):
        """
        Posiciona la ventana según la configuración y la muestra.
        """
        win_d = (
            self.cfg.get('window', {})
            if isinstance(self.cfg.get('window', {}), dict)
            else {}
        )
        x = win_d.get('x', None)
        y = win_d.get('y', None)

        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            x, y = self._clamp_position_to_screens(
                int(x),
                int(y),
                self.width(),
                self.height(),
            )
            self.move(x, y)
        else:
            how = self.cfg.get('show_on_tray_click', 'bottom-right')
            if how == 'bottom-right':
                screen = QApplication.primaryScreen().availableGeometry()
                geom = self.frameGeometry()
                self.move(
                    screen.right() - geom.width() - 10,
                    screen.bottom() - geom.height() - 10,
                )
            else:
                pos = QtGui.QCursor.pos()
                self.move(
                    max(0, pos.x() - self.width()),
                    max(0, pos.y() - self.height()),
                )

        self.show()
        self.raise_()
        self.activateWindow()

    def _clamp_position_to_screens(
        self,
        x: int,
        y: int,
        w: int = None,
        h: int = None,
    ) -> tuple:
        """
        Ajusta una posición para que esté dentro de las pantallas visibles.

        Args:
            x: Coordenada X.
            y: Coordenada Y.
            w: Ancho de la ventana.
            h: Alto de la ventana.

        Returns:
            Tupla (x, y) ajustada.
        """
        try:
            w = int(w if w is not None else self.width())
            h = int(h if h is not None else self.height())

            screens = QtGui.QGuiApplication.screens()
            rects = (
                [s.availableGeometry() for s in screens]
                if screens
                else [QApplication.primaryScreen().availableGeometry()]
            )

            if not rects:
                return (max(0, x), max(0, y))

            for r in rects:
                if r.contains(QtCore.QPoint(x, y)):
                    nx = min(max(x, r.left()), r.right() - w)
                    ny = min(max(y, r.top()), r.bottom() - h)
                    return (nx, ny)

            best = None
            for r in rects:
                nx = min(max(x, r.left()), r.right() - w)
                ny = min(max(y, r.top()), r.bottom() - h)
                dx = x - nx
                dy = y - ny
                dist2 = dx * dx + dy * dy
                if best is None or dist2 < best[0]:
                    best = (dist2, nx, ny)

            return (best[1], best[2]) if best else (max(0, x), max(0, y))

        except Exception:
            return (max(0, x), max(0, y))

    def resizeEvent(self, e: QtGui.QResizeEvent):
        """
        Captura cambios de tamaño y guarda dimensiones en configuración.
        """
        super().resizeEvent(e)

        # ⛔ Evitar guardar estado durante el arranque inicial
        if not getattr(self, "_ui_ready", False):
            return

        try:
            if self.windowState() & QtCore.Qt.WindowMinimized:
                return
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en MainWindow::resizeEvent'
            )

        sz = self.size()
        w = max(320, int(sz.width()))
        h = max(360, int(sz.height()))

        if w != sz.width() or h != sz.height():
            self.resize(w, h)

        win_d = (
            self.cfg.get('window', {})
            if isinstance(self.cfg.get('window', {}), dict)
            else {}
        )
        win_d.update({'width': w, 'height': h})
        self.cfg['window'] = win_d

        try:
            save_config(self.cfg)
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en MainWindow::resizeEvent'
            )

    def moveEvent(self, e: QtGui.QMoveEvent):
        """
        Captura los movimientos de la ventana y guarda su posición en la configuración.

        Este método se ejecuta cada vez que la ventana cambia de posición
        y se encarga de persistir las coordenadas (x, y) para restaurarlas
        en futuros arranques.

        Args:
            e: Evento Qt asociado al movimiento de la ventana.

        IMPORTANT:
            - No se guarda la posición durante la fase de arranque inicial.
            - No se guarda la posición si la ventana está minimizada.
            - La posición siempre se ajusta a las pantallas disponibles
              para evitar ventanas fuera de pantalla.
        """
        super().moveEvent(e)

        # ⛔ No guardar posición durante el arranque inicial de la UI
        if not getattr(self, "_ui_ready", False):
            return

        # ⛔ No guardar posición si la ventana está minimizada
        if self.windowState() & QtCore.Qt.WindowMinimized:
            return

        pos = self.pos()
        try:
            x, y = int(pos.x()), int(pos.y())
        except Exception:
            # Coordenadas inválidas → salir silenciosamente
            return

        # Ajustar la posición para que quede dentro de las pantallas visibles
        x, y = self._clamp_position_to_screens(
            x,
            y,
            self.width(),
            self.height()
        )

        # Guardar la posición en la configuración
        win_d = (
            self.cfg.get('window', {})
            if isinstance(self.cfg.get('window', {}), dict)
            else {}
        )
        win_d['x'] = x
        win_d['y'] = y
        self.cfg['window'] = win_d

        # Persistir cambios en disco
        save_config(self.cfg)

    def changeEvent(self, event: QtCore.QEvent):
        """
        Maneja cambios de estado de la ventana (versión con minimizar a bandeja).

        Este manejador intercepta el evento de minimizado y,
        en lugar de mostrar la ventana minimizada, la envía
        directamente a la bandeja del sistema.

        Args:
            event: Evento de cambio de estado de la ventana.
        """
        if event.type() == QtCore.QEvent.WindowStateChange:
            if self.windowState() & QtCore.Qt.WindowMinimized:
                # Diferir la minimización real para evitar glitches de Qt
                QtCore.QTimer.singleShot(0, self._minimize_to_tray)
                event.accept()
                return
        super().changeEvent(event)

    def closeEvent(self, event: QtGui.QCloseEvent):
        """
        Maneja el evento de cierre de la ventana.

        Dependiendo de la configuración:
        - Si está activado minimizar a bandeja, se oculta la ventana.
        - Si no, se permite el cierre normal de la aplicación.

        Args:
            event: Evento de cierre de Qt.
        """
        if self.cfg.get('minimize_to_tray', True):
            event.ignore()
            self._minimize_to_tray()
        else:
            event.accept()

    def changeEvent(self, event: QtCore.QEvent):
        """
        Maneja cambios de estado de la ventana (versión con ocultar directo).

        Esta variante intercepta el evento de minimizado
        y simplemente oculta la ventana sin lógica adicional.

        NOTE:
            Este método coexiste con otra definición de changeEvent
            en la clase y se mantiene así por compatibilidad
            y comportamiento histórico del proyecto.
        """
        if event.type() == QtCore.QEvent.WindowStateChange:
            if self.windowState() & QtCore.Qt.WindowMinimized:
                QtCore.QTimer.singleShot(0, self.hide)
                event.accept()
                return
        super().changeEvent(event)

    def on_tray_activated(self, reason):
        """
        Maneja la activación del icono de la bandeja del sistema.

        Al hacer clic o doble clic:
        - Se alterna la visibilidad de la ventana principal.

        Args:
            reason: Motivo de activación del icono de bandeja (Qt).
        """
        if reason in (
            QtWidgets.QSystemTrayIcon.Trigger,
            QtWidgets.QSystemTrayIcon.DoubleClick
        ):
            self.toggle_show()

    def activate_selected(self):
        """
        Ejecuta el elemento actualmente seleccionado en el árbol,
        si este corresponde a un archivo/acceso y no a una carpeta.
        """
        it = self.tree.currentItem()
        if it and it.data(0, ROLE_PATH) and (not bool(it.data(0, ROLE_IS_DIR))):
            self.on_item_activated(it)

    def apply_filter(self, text):
        """
        Aplica un filtro de texto al árbol de accesos.

        Dependiendo del modo de vista:
        - En modo agrupado se aplica de forma recursiva.
        - En modo plano se filtran solo los elementos visibles.

        Args:
            text: Texto de filtro introducido por el usuario.
        """
        t = (text or '').lower()

        def filter_rec(it: QTreeWidgetItem) -> bool:
            """
            Aplica el filtro de forma recursiva a un elemento y sus hijos.

            Args:
                it: Elemento del árbol.

            Returns:
                True si el elemento o alguno de sus hijos coincide.
            """
            name = it.text(0).lower()
            match = t in name if t else True

            if it.childCount() == 0:
                it.setHidden(not match)
                return match

            visible_any = False
            for j in range(it.childCount()):
                if filter_rec(it.child(j)):
                    visible_any = True

            it.setHidden(not (match or visible_any))
            return match or visible_any

        if self.cfg.get('view_mode', 'grouped') == 'grouped':
            for i in range(self.tree.topLevelItemCount()):
                filter_rec(self.tree.topLevelItem(i))
        else:
            for i in range(self.tree.topLevelItemCount()):
                it = self.tree.topLevelItem(i)
                name = it.text(0).lower()
                match = t in name if t else True
                it.setHidden(not match)

    def set_view_grouped(self):
        """
        Cambia la vista al modo agrupado (por carpetas).
        """
        self.cfg['view_mode'] = 'grouped'
        save_config(self.cfg)
        self.sync_view_buttons()
        self.load_categories()

    def set_view_flat(self):
        """
        Cambia la vista al modo plano (lista única).
        """
        self.cfg['view_mode'] = 'flat'
        save_config(self.cfg)
        self.sync_view_buttons()
        self.load_categories()

    def sync_view_buttons(self):
        """
        Sincroniza el estado visual de los botones de vista
        con la configuración actual.
        """
        v = self.cfg.get('view_mode', 'grouped')
        self.act_grouped.setChecked(v == 'grouped')
        self.act_flat.setChecked(v == 'flat')

    def expand_all(self):
        """
        Expande todos los nodos del árbol.
        """
        self.tree.expandAll()

    def collapse_all(self):
        """
        Colapsa todos los nodos del árbol.
        """
        self.tree.collapseAll()

    def qicon_for_path(self, file_path: Path, resolved_target: Optional[str]):
        """
        Devuelve el icono apropiado para un archivo o su destino real.

        Usa caché interna para:
        - Evitar llamadas repetidas a la API del sistema.
        - Mejorar rendimiento en árboles grandes.

        Args:
            file_path: Ruta del archivo representado.
            resolved_target: Ruta real resuelta si es un acceso directo.

        Returns:
            QIcon representativo del archivo o recurso.
        """
        key = (resolved_target or str(file_path)).lower()
        icon = self.icon_cache.get(key)
        if icon is not None:
            return icon

        provider = QtWidgets.QFileIconProvider()

        try:
            if file_path.is_dir():
                icon = provider.icon(QtWidgets.QFileIconProvider.Folder)
            else:
                suf = file_path.suffix.lower()

                if suf == '.lnk':
                    icon = None
                    try:
                        info = resolve_lnk(str(file_path))
                        icon_loc = None
                        if isinstance(info, dict):
                            for k in ('icon', 'icon_location', 'iconpath', 'icon_path', 'iconlocation'):
                                v = info.get(k)
                                if v:
                                    icon_loc = str(v)
                                    break

                        if icon_loc:
                            raw = icon_loc.strip().strip('"')
                            if ',' in raw:
                                raw = raw.split(',', 1)[0].strip()
                            raw = os.path.expandvars(raw)
                            from pathlib import Path as _P
                            ip = _P(raw)
                            if ip.exists():
                                if ip.suffix.lower() in ('.ico', '.png', '.jpg', '.jpeg', '.bmp', '.svg'):
                                    icon = QtGui.QIcon(str(ip))
                                else:
                                    icon = provider.icon(QtCore.QFileInfo(str(ip)))
                    except Exception:
                        LOGGER.exception(
                            '[auto] Exception capturada en MainWindow::qicon_for_path'
                        )

                    if icon is None:
                        try:
                            icon = provider.icon(
                                QtCore.QFileInfo(str(file_path))
                            )
                        except Exception:
                            icon = None

                    if icon is None and resolved_target and os.path.exists(resolved_target):
                        try:
                            icon = provider.icon(
                                QtCore.QFileInfo(resolved_target)
                            )
                        except Exception:
                            icon = None

                elif resolved_target and os.path.exists(resolved_target):
                    icon = provider.icon(
                        QtCore.QFileInfo(resolved_target)
                    )
                else:
                    icon = provider.icon(
                        QtCore.QFileInfo(str(file_path))
                    )

        except Exception:
            icon = provider.icon(
                QtCore.QFileInfo(str(file_path))
            )

        self.icon_cache[key] = icon
        return icon

    def _is_display_file(self, p: Path) -> bool:
        """
        Determina si un archivo debe mostrarse en el árbol.

        Reglas:
        - Solo archivos (no carpetas).
        - Se excluyen archivos ocultos y '.keep'.

        Args:
            p: Ruta del archivo.

        Returns:
            True si el archivo debe mostrarse.
        """
        if not p.is_file():
            return False
        name = p.name
        if name == '.keep' or name.startswith('.'):
            return False
        return True

    def _add_dir_node_rec(self, dir_path: Path, parent: Optional[QTreeWidgetItem]):
        """
        Añade recursivamente un nodo de directorio y su contenido al árbol.

        Este método:
        - Crea un nodo para el directorio actual.
        - Añade archivos visibles como hijos.
        - Recorre subdirectorios de forma recursiva.

        Args:
            dir_path: Ruta del directorio a procesar.
            parent: Nodo padre del árbol o None si es nivel raíz.

        NOTE:
            Se usa recursión explícita para mantener control total
            del orden, iconos y metadatos.
        """
        provider = QtWidgets.QFileIconProvider()

        node = QTreeWidgetItem([dir_path.name])
        node.setData(0, ROLE_PATH, str(dir_path))
        node.setData(0, ROLE_IS_DIR, True)
        node.setFirstColumnSpanned(True)
        node.setIcon(0, provider.icon(QtWidgets.QFileIconProvider.Folder))

        if parent is None:
            self.tree.addTopLevelItem(node)
        else:
            parent.addChild(node)

        try:
            entries = sorted(
                [p for p in dir_path.iterdir() if self._is_display_file(p)],
                key=lambda p: p.name.lower(),
            )
        except Exception:
            entries = []

        for f in entries:
            resolved = None
            if f.suffix.lower() == '.lnk':
                try:
                    info = resolve_lnk(str(f))
                    if info and info.get('target'):
                        resolved = info['target']
                except Exception:
                    LOGGER.exception(
                        '[auto] Exception capturada en MainWindow::_add_dir_node_rec'
                    )

            icon = self.qicon_for_path(f, resolved)
            item = QTreeWidgetItem([self.readable_name_for_file(f)])
            item.setData(0, ROLE_PATH, str(f))
            item.setData(0, ROLE_IS_DIR, False)
            item.setIcon(0, icon)
            node.addChild(item)

        try:
            subdirs = sorted(
                [p for p in dir_path.iterdir() if p.is_dir()],
                key=lambda p: p.name.lower(),
            )
        except Exception:
            subdirs = []

        for sub in subdirs:
            self._add_dir_node_rec(sub, node)

    def _walk_all_files(self, base: Path) -> List[Path]:
        """
        Recorre recursivamente todos los archivos visibles desde una carpeta base.

        Args:
            base: Directorio base a recorrer.

        Returns:
            Lista de rutas de archivos que deben mostrarse.
        """
        result = []
        for root, dirs, files in os.walk(base):
            root_p = Path(root)
            for fn in sorted(files, key=str.lower):
                p = root_p / fn
                if self._is_display_file(p):
                    result.append(p)
        return result

    def readable_name_for_file(self, f: Path) -> str:
        """
        Devuelve un nombre legible para mostrar un archivo en el árbol.

        Para archivos .url:
        - Intenta extraer el dominio de la URL y añadirlo al nombre.

        Args:
            f: Ruta del archivo.

        Returns:
            Nombre a mostrar en el árbol.
        """
        name = f.stem

        if f.suffix.lower() == '.url':
            try:
                for line in f.read_text(
                    encoding='utf-8',
                    errors='ignore'
                ).splitlines():
                    if line.strip().lower().startswith('url='):
                        from urllib.parse import urlparse
                        url = line.split('=', 1)[1].strip()
                        netloc = urlparse(url).netloc
                        if netloc:
                            if netloc.lower().startswith('www.'):
                                netloc = netloc[4:]
                            return f'{name} ({netloc})'
            except Exception:
                LOGGER.exception(
                    '[auto] Exception capturada en MainWindow::readable_name_for_file'
                )

        return name

    def load_categories(self):
        """
        Carga y reconstruye el árbol principal según la configuración actual.

        Dependiendo del modo de vista:
        - grouped: estructura por carpetas.
        - flat: lista plana de todos los accesos.
        """
        self.tree.clear()
        self.icon_cache.clear()

        base = self.base_dir()
        base.mkdir(parents=True, exist_ok=True)

        mode = self.cfg.get('view_mode', 'grouped')

        if mode == 'grouped':
            try:
                root_files = sorted(
                    [p for p in base.iterdir() if self._is_display_file(p)],
                    key=lambda p: p.name.lower(),
                )
            except Exception:
                root_files = []

            for f in root_files:
                resolved = None
                if f.suffix.lower() == '.lnk':
                    info = resolve_lnk(str(f))
                    if info and info.get('target'):
                        resolved = info['target']

                icon = self.qicon_for_path(f, resolved)
                it = QTreeWidgetItem([self.readable_name_for_file(f)])
                it.setData(0, ROLE_PATH, str(f))
                it.setData(0, ROLE_IS_DIR, False)
                it.setIcon(0, icon)
                self.tree.addTopLevelItem(it)

            try:
                cats = sorted(
                    [p for p in base.iterdir() if p.is_dir()],
                    key=lambda p: p.name.lower(),
                )
            except Exception:
                cats = []

            for sub in cats:
                self._add_dir_node_rec(sub, None)

            self.tree.expandToDepth(0)

        else:
            for f in self._walk_all_files(base):
                resolved = None
                if f.suffix.lower() == '.lnk':
                    info = resolve_lnk(str(f))
                    if info and info.get('target'):
                        resolved = info['target']

                icon = self.qicon_for_path(f, resolved)
                it = QTreeWidgetItem([self.readable_name_for_file(f)])
                it.setData(0, ROLE_PATH, str(f))
                it.setData(0, ROLE_IS_DIR, False)
                it.setIcon(0, icon)
                self.tree.addTopLevelItem(it)

    def on_item_activated(self, item: QTreeWidgetItem):
        """
        Maneja la activación (doble clic / Enter) de un elemento del árbol.

        - Si es una carpeta, la expande o colapsa.
        - Si es un acceso, lo ejecuta.

        Args:
            item: Elemento activado.
        """
        path = item.data(0, ROLE_PATH)
        is_dir = bool(item.data(0, ROLE_IS_DIR))

        if not path or is_dir:
            item.setExpanded(not item.isExpanded())
            return

        self.launch_path(Path(path))

    def launch_path(self, p: Path):
        """
        Lanza un archivo o acceso usando el sistema operativo.

        Tras el lanzamiento puede minimizar la aplicación
        según la configuración.

        Args:
            p: Ruta a lanzar.
        """
        try:
            LOGGER.info(f'Lanzando: {p}')
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en MainWindow::launch_path'
            )

        try:
            os.startfile(str(p))
            if self.cfg.get('launch_and_minimize', True):
                self.hide()
        except Exception:
            try:
                shell_execute(str(p))
                if self.cfg.get('launch_and_minimize', True):
                    self.hide()
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    'Error al ejecutar',
                    f'No se pudo lanzar\n{e}',
                )

    def clipboard_text(self) -> str:
        """
        Devuelve el texto actual del portapapeles.

        Returns:
            Cadena de texto del portapapeles (sin espacios).
        """
        cb = QtGui.QGuiApplication.clipboard()
        return cb.text().strip() if cb else ''

    def looks_like_url(self, s: str) -> bool:
        """
        Determina si una cadena tiene aspecto de URL.

        Args:
            s: Cadena a evaluar.

        Returns:
            True si parece una URL válida.
        """
        s = (s or '').strip()
        return bool(
            s and s.lower().startswith(
                ('http://', 'https://', 'ftp://', 'mailto:', 'file:')
            )
        )

    def suggest_name_from_url_or_text(self, s: str) -> str:
        """
        Sugiere un nombre legible a partir de una URL o texto.

        Args:
            s: URL o texto de entrada.

        Returns:
            Nombre sugerido.
        """
        from urllib.parse import urlparse

        s = (s or '').strip()
        if not s:
            return ''

        if self.looks_like_url(s):
            try:
                netloc = urlparse(s).netloc or ''
                netloc = netloc.split(':', 1)[0]
                if netloc.lower().startswith('www.'):
                    netloc = netloc[4:]
                return netloc or 'Acceso web'
            except Exception:
                return 'Acceso web'

        return s

    def target_dir_for_new_url(self) -> Path:
        """
        Devuelve el directorio destino para crear un nuevo acceso web.

        La lógica es:
        - Si no hay selección: directorio base.
        - Si la selección es una carpeta: esa carpeta.
        - Si la selección es un archivo: su carpeta contenedora.

        Returns:
            Path del directorio destino.
        """
        base = self.base_dir()
        it = self.tree.currentItem()
        if not it:
            return base

        p = it.data(0, ROLE_PATH)
        is_dir = bool(it.data(0, ROLE_IS_DIR))
        if p:
            p = Path(str(p))
            return p if is_dir else p.parent

        return base

    def select_item_by_path(self, target_path: Path):
        """
        Selecciona y enfoca en el árbol el elemento cuya ruta coincide.

        La búsqueda se realiza de forma recursiva en todo el árbol.

        Args:
            target_path: Ruta absoluta del elemento a seleccionar.
        """
        target_s = str(target_path)

        def match_and_select(item: QTreeWidgetItem) -> bool:
            """
            Busca recursivamente un item coincidente y lo selecciona.

            Args:
                item: Nodo actual del árbol.

            Returns:
                True si se ha encontrado y seleccionado el elemento.
            """
            if item.data(0, ROLE_PATH) == target_s:
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
                return True

            for j in range(item.childCount()):
                if match_and_select(item.child(j)):
                    return True

            return False

        for i in range(self.tree.topLevelItemCount()):
            if match_and_select(self.tree.topLevelItem(i)):
                return

    def start_menu_dirs(self):
        """
        Devuelve las rutas del menú Inicio de Windows disponibles.

        Incluye:
        - Menú Inicio del usuario actual.
        - Menú Inicio global (todos los usuarios).

        Returns:
            Lista de directorios existentes del menú Inicio.
        """
        dirs = []

        appdata = os.environ.get('APPDATA')
        if appdata:
            dirs.append(
                Path(appdata) / 'Microsoft/Windows/Start Menu/Programs'
            )

        programdata = os.environ.get('ProgramData')
        if programdata:
            dirs.append(
                Path(programdata) / 'Microsoft/Windows/Start Menu/Programs'
            )

        return [d for d in dirs if d.exists()]

    def populate_start_menu(self, menu: QMenu):
        """
        Construye completamente el menú Inicio integrado.

        Este método:
        - Garantiza que exista el campo de búsqueda.
        - Reconstruye el contenido según el filtro actual.

        Args:
            menu: Menú Qt que representa el menú Inicio.
        """
        self._ensure_start_menu_search(menu)
        self._rebuild_start_menu_content(menu, self._start_menu_filter)

    def _ensure_start_menu_search(self, menu: QMenu):
        """
        Asegura que el menú Inicio tenga un campo de búsqueda superior.

        Args:
            menu: Menú Qt del menú Inicio.
        """
        actions = menu.actions()
        if actions and isinstance(actions[0], QWidgetAction):
            return

        search_edit = QLineEdit(menu)
        search_edit.setPlaceholderText('Filtrar…')
        search_edit.setClearButtonEnabled(True)

        if self._start_menu_filter:
            search_edit.setText(self._start_menu_filter)

        search_edit.textChanged.connect(
            lambda s, m=menu: QtCore.QTimer.singleShot(
                0,
                lambda: self._on_start_menu_filter_changed(m, s)
            )
        )

        wa = QWidgetAction(menu)
        wa.setDefaultWidget(search_edit)
        menu.addAction(wa)
        menu.addSeparator()

    def _on_start_menu_filter_changed(self, menu: QMenu, text: str):
        """
        Maneja el cambio del filtro del menú Inicio.

        Args:
            menu: Menú Qt del menú Inicio.
            text: Nuevo texto del filtro.
        """
        self._start_menu_filter = text
        self._rebuild_start_menu_content(menu, text, refocus=True)

    def _rebuild_start_menu_content(
        self,
        menu: QMenu,
        filter_text: str = '',
        refocus: bool = False
    ):
        """
        Reconstruye el contenido del menú Inicio según el filtro.

        Args:
            menu: Menú Qt del menú Inicio.
            filter_text: Texto de filtrado.
            refocus: Si True, devuelve el foco al campo de búsqueda.
        """
        for a in menu.actions()[2:]:
            sm = a.menu() if hasattr(a, 'menu') else None
            if sm:
                sm.clear()
            menu.removeAction(a)

        provider = QtWidgets.QFileIconProvider()
        ft = (filter_text or '').strip().lower()

        def add_dir_to_menu(dir_path: Path, parent_menu: QMenu) -> int:
            """
            Añade recursivamente una carpeta del menú Inicio al menú Qt.

            Args:
                dir_path: Carpeta a recorrer.
                parent_menu: Menú padre Qt.

            Returns:
                Número de accesos añadidos.
            """
            count = 0
            try:
                entries = sorted(
                    dir_path.iterdir(),
                    key=lambda p: (0 if p.is_dir() else 1, p.name.lower())
                )
            except Exception:
                return 0

            for entry in entries:
                if entry.is_dir():
                    sub = QMenu(entry.name, parent_menu)
                    c = add_dir_to_menu(entry, sub)
                    if c > 0:
                        parent_menu.addMenu(sub)
                        count += c

            for entry in entries:
                if entry.is_file():
                    suf = entry.suffix.lower()
                    if suf in ALLOWED_EXTS or suf in ('.url', '.website'):
                        label = entry.stem
                        if ft and ft not in label.lower():
                            continue

                        resolved = None
                        if suf == '.lnk':
                            try:
                                info = resolve_lnk(str(entry))
                                if info and info.get('target'):
                                    resolved = info['target']
                            except Exception:
                                LOGGER.exception(
                                    '[auto] Exception capturada en MainWindow::_rebuild_start_menu_content::add_dir_to_menu'
                                )

                        if resolved and os.path.exists(resolved):
                            icon = provider.icon(
                                QtCore.QFileInfo(resolved)
                            )
                        else:
                            icon = provider.icon(
                                QtCore.QFileInfo(str(entry))
                            )

                        act = parent_menu.addAction(icon, label)
                        act.triggered.connect(
                            lambda _, p=str(entry): self.launch_path(Path(p))
                        )
                        count += 1

            return count

        total = 0
        dirs = self.start_menu_dirs()

        for idx, d in enumerate(dirs):
            section_label = (
                'Este usuario' if idx == 0 else 'Todos los usuarios'
            )
            temp = QMenu(menu)
            c = add_dir_to_menu(d, temp)

            if c > 0:
                menu.addSection(section_label)
                for a in temp.actions():
                    menu.addAction(a)
                total += c

            if idx < len(dirs) - 1:
                menu.addSeparator()

        if total == 0:
            a = menu.addAction('No se encontraron accesos con ese filtro')
            a.setEnabled(False)

        if refocus and menu.actions():
            first = menu.actions()[0]
            if (
                isinstance(first, QWidgetAction) and
                isinstance(first.defaultWidget(), QLineEdit)
            ):
                se: QLineEdit = first.defaultWidget()
                se.setFocus(QtCore.Qt.FocusReason.OtherFocusReason)
                se.setCursorPosition(len(se.text()))

    def create_web_shortcut(self):
        """
        Crea un acceso web (.url) en el directorio seleccionado.

        Soporta dos modos:
        - Modo rápido: Shift + URL válida en portapapeles.
        - Modo normal: diálogo de creación.
        """
        cb_text = self.clipboard_text()
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        quick = bool(modifiers & QtCore.Qt.ShiftModifier)

        prefill_url = cb_text if self.looks_like_url(cb_text) else ''
        prefill_name = ''

        if prefill_url:
            prefill_name = self.suggest_name_from_url_or_text(prefill_url)
        elif cb_text:
            prefill_name = self.suggest_name_from_url_or_text(cb_text)

        dest_dir = self.target_dir_for_new_url()

        # --- Modo rápido (Shift + URL en portapapeles) ---
        if quick and prefill_url:
            name = sanitize_filename(prefill_name or 'Acceso web')

            try:
                path = create_url_shortcut(
                    dest_dir=dest_dir,
                    name=name,
                    url=prefill_url,
                )
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    'Error',
                    f'No se pudo crear el acceso web:\n{e}'
                )
                return

            self.load_categories()
            self.select_item_by_path(path)
            return

        # --- Modo normal (diálogo) ---
        suggested = ''
        it = self.tree.currentItem()
        if it:
            data = it.data(0, ROLE_PATH)
            suggested = (
                Path(str(data)).stem
                if data and not bool(it.data(0, ROLE_IS_DIR))
                else it.text(0)
            )

        dlg = CreateUrlDialog(
            self,
            suggested_name=suggested,
            prefill_url=prefill_url,
            prefill_name=prefill_name
        )

        if dlg.exec() != QDialog.Accepted:
            return

        name, url = dlg.values()
        name = sanitize_filename(name)

        try:
            path = create_url_shortcut(
                dest_dir=dest_dir,
                name=name,
                url=url,
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Error',
                f'No se pudo crear el acceso web:\n{e}'
            )
            return

        self.load_categories()
        self.select_item_by_path(path)

    def create_desktop_shortcut(self):
        """
        Abre un diálogo para crear un acceso directo (.lnk) en la carpeta base.

        El flujo es:
        - Mostrar diálogo de creación.
        - Validar y crear carpeta base si es necesario.
        - Generar el acceso directo mediante VBS.
        - Recargar la vista y seleccionar el nuevo acceso.

        IMPORTANT:
            Este método depende de funcionalidades específicas de Windows.
        """
        dlg = CreateShortcutDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return

        vals = dlg.values()
        base = self.base_dir()

        try:
            base.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Error',
                f'No se pudo crear la carpeta base:\n{e}',
            )
            return

        name = sanitize_filename(vals['name'])
        lnk_path = unique_path(base, name, '.lnk')

        ok, err = create_lnk_via_vbs(
            lnk_path=str(lnk_path),
            target=vals['target'],
            args=vals['args'] or '',
            workdir=(
                vals['workdir']
                or str(Path(vals['target']).parent)
            ),
            icon=vals['icon'] or vals['target'],
        )

        if not ok:
            QtWidgets.QMessageBox.warning(
                self,
                'Error',
                f'No se pudo crear el acceso directo:\n{err}',
            )
            return

        self.load_categories()
        self.select_item_by_path(lnk_path)

    def create_shortcut_to_target(
        self,
        target: Path,
        dest_dir: Path
    ) -> Optional[Path]:
        """
        Crea un acceso directo (.lnk) que apunta a un archivo o carpeta.

        Args:
            target: Ruta del recurso objetivo.
            dest_dir: Carpeta donde crear el acceso.

        Returns:
            Ruta del acceso creado o None si ocurre algún error.

        WARNING:
            Esta operación solo está disponible en Windows.
        """
        try:
            import platform

            if platform.system().lower() != 'windows':
                QtWidgets.QMessageBox.warning(
                    self,
                    'No compatible',
                    'La creación de accesos .lnk solo está disponible en Windows.',
                )
                return None

            dest_dir.mkdir(parents=True, exist_ok=True)
            name = sanitize_filename(target.name)
            lnk_path = unique_path(dest_dir, name, '.lnk')

            workdir = (
                str(target.parent)
                if target.is_file()
                else str(target)
            )

            ok, err = create_lnk_via_vbs(
                str(lnk_path),
                str(target),
                '',
                workdir,
                str(target),
            )

            if not ok:
                QtWidgets.QMessageBox.warning(
                    self,
                    'Error',
                    f'No se pudo crear el acceso directo:\n{err}',
                )
                return None

            return lnk_path

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Error',
                f'No se pudo crear el acceso directo:\n{e}',
            )
            return None

    def execute_special_command(self, cmd: str, category: str = ''):
        """
        Ejecuta un comando especial de Windows según su tipo.

        Soporta:
        - shell:
        - shell:::
        - ms-settings:
        - control
        - .msc
        - URLs y comandos genéricos

        Args:
            cmd: Comando a ejecutar.
            category: Categoría asociada (si existe).
        """
        try:
            cmd = (cmd or '').strip()
            cat = (category or '').strip()

            if not cmd:
                return

            import subprocess, shlex, os

            if cmd.lower().startswith('shell:::') or cat.startswith('CLSID'):
                subprocess.Popen(
                    ['explorer.exe', cmd],
                    shell=False
                )
                return

            if cmd.lower().startswith('shell:'):
                os.startfile(cmd)
                return

            if cmd.lower().endswith('.msc') or cat.startswith('.msc'):
                os.startfile(cmd)
                return

            if (
                cmd.lower().startswith('ms-settings:')
                or (':' in cmd and not cmd.lower().startswith('control'))
            ):
                os.startfile(cmd)
                return

            if cmd.lower().startswith('control') or cat.startswith('control'):
                if cmd.lower() == 'control':
                    subprocess.Popen(
                        ['control.exe'],
                        shell=False
                    )
                else:
                    subprocess.Popen(
                        ['control.exe']
                        + shlex.split(cmd[len('control'):].strip()),
                        shell=False
                    )
                return

            os.startfile(cmd)

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Abrir comando',
                f'No se pudo ejecutar:\n{cmd}\n\n{e}',
            )

    def create_shortcut_for_special_command(
        self,
        cmd: str,
        category: str = ''
    ):
        """
        Crea un acceso en la carpeta base hacia un comando especial.

        El tipo de acceso (.lnk o .url) depende del tipo de comando.

        Args:
            cmd: Comando especial.
            category: Categoría asociada.

        Returns:
            Ruta del acceso creado o None si falla.
        """
        try:
            dest_dir = self.target_dir_for_new_url()
            safe = sanitize_filename(
                cmd.replace(':', ' - ')
                   .replace('\\', ' - ')
                   .replace('/', ' - ')
            )

            import os

            if cmd.lower().startswith(
                (
                    'shell:',
                    'ms-settings:',
                    'mailto:',
                    'microsoft-edge:',
                    'ms-store:',
                    'ms-photos:',
                    'ms-people:',
                    'search-ms:',
                )
            ):
                path = unique_path(dest_dir, safe, '.url')
                try:
                    path.write_text(
                        f'[InternetShortcut]\r\nURL={cmd}\r\n',
                        encoding='utf-8',
                        errors='ignore',
                    )
                except Exception as e:
                    QtWidgets.QMessageBox.warning(
                        self,
                        'Crear acceso',
                        f'No se pudo crear el acceso (.url):\n{e}',
                    )
                    return None
                return path

            if cmd.lower().startswith('shell:::') or (category or '').startswith('CLSID'):
                lnk = unique_path(dest_dir, safe, '.lnk')
                ok, err = create_lnk_via_vbs(
                    str(lnk),
                    'explorer.exe',
                    cmd,
                    '',
                    'explorer.exe',
                )
                if not ok:
                    QtWidgets.QMessageBox.warning(
                        self,
                        'Crear acceso',
                        f'No se pudo crear el acceso (.lnk):\n{err}',
                    )
                    return None
                return lnk

            if cmd.lower().endswith('.msc') or (category or '').startswith('.msc'):
                target = cmd
                lnk = unique_path(dest_dir, safe, '.lnk')
                ok, err = create_lnk_via_vbs(
                    str(lnk),
                    target,
                    '',
                    '',
                    target,
                )
                if not ok:
                    QtWidgets.QMessageBox.warning(
                        self,
                        'Crear acceso',
                        f'No se pudo crear el acceso (.lnk):\n{err}',
                    )
                    return None
                return lnk

            if cmd.lower().startswith('control') or (category or '').startswith('control'):
                import shlex
                args = cmd[len('control'):].strip()
                lnk = unique_path(dest_dir, safe, '.lnk')
                ok, err = create_lnk_via_vbs(
                    str(lnk),
                    'control.exe',
                    args,
                    '',
                    'control.exe',
                )
                if not ok:
                    QtWidgets.QMessageBox.warning(
                        self,
                        'Crear acceso',
                        f'No se pudo crear el acceso (.lnk):\n{err}',
                    )
                    return None
                return lnk

            if '://' in cmd or cmd.lower().startswith('file:'):
                path = unique_path(dest_dir, safe, '.url')
                try:
                    path.write_text(
                        f'[InternetShortcut]\r\nURL={cmd}\r\n',
                        encoding='utf-8',
                        errors='ignore',
                    )
                except Exception as e:
                    QtWidgets.QMessageBox.warning(
                        self,
                        'Crear acceso',
                        f'No se pudo crear el acceso (.url):\n{e}',
                    )
                    return None
                return path

            else:
                lnk = unique_path(dest_dir, safe, '.lnk')
                ok, err = create_lnk_via_vbs(
                    str(lnk),
                    cmd,
                    '',
                    '',
                    cmd,
                )
                if not ok:
                    QtWidgets.QMessageBox.warning(
                        self,
                        'Crear acceso',
                        f'No se pudo crear el acceso (.lnk):\n{err}',
                    )
                    return None
                return lnk

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Crear acceso',
                f'Error creando acceso:\n{e}',
            )
            return None

    def open_special_commands(self):
        """
        Abre el diálogo de comandos especiales de Windows.
        """
        json_path = os.fspath(
            app_dir() / 'windows_special_commands.json'
        )
        dlg = SpecialCommandsDialog(
            self,
            json_path=json_path,
        )
        dlg.exec()

    def _apply_autostart_settings(self):
        """
        Aplica la configuración de auto‑inicio con Windows según la configuración actual.
        """
        try:
            enabled = bool(self.cfg.get('autostart_enabled', False))
            method = (
                'registry'
                if str(self.cfg.get('autostart_method', 'registry')) == 'registry'
                else 'startup'
            )
            minimized = bool(
                self.cfg.get('autostart_minimized', True)
            )

            ok, err = set_windows_autostart(
                enabled=enabled,
                method=method,
                minimized=minimized,
            )

            try:
                if ok:
                    LOGGER.info(
                        f"Auto-inicio con Windows: "
                        f"{'activado' if enabled else 'desactivado'} "
                        f"- metodo={method} - minimized={minimized}"
                    )
                else:
                    LOGGER.error(
                        f"Auto-inicio con Windows: error "
                        f"- metodo={method} - detalle={err}"
                    )
            except Exception:
                pass

        except Exception:
            pass

    def open_windows_search(self):
        """
        Abre la búsqueda integrada de Windows.
        """
        try:
            os.startfile('search-ms:')
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Error',
                f'No se pudo abrir la búsqueda de Windows:\n{e}',
            )

    def open_web_search(self):
        """
        Abre la búsqueda web configurada por el usuario.
        """
        url = (
            (self.cfg.get('web_search_url') or '').strip()
            or 'https://www.bing.com'
        )

        if not (
            url.startswith('http://')
            or url.startswith('https://')
            or url.startswith('file:')
        ):
            url = 'https://' + url

        try:
            os.startfile(url)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Error',
                f'No se pudo abrir la URL configurada:\n{e}',
            )

    def _open_shortcut_target_folder(self, item: QTreeWidgetItem):
        """
        Abre la carpeta que contiene el destino de un acceso directo.

        Args:
            item: Elemento del árbol que representa un .lnk.
        """
        p_str = item.data(0, ROLE_PATH)
        if not p_str:
            return

        p = Path(str(p_str))
        if p.suffix.lower() != '.lnk' or not p.exists():
            return

        try:
            info = resolve_lnk(str(p))
            target = info.get('target') if info else None
            if not target:
                QtWidgets.QMessageBox.information(
                    self,
                    'Información',
                    'No se pudo resolver el destino del acceso directo.',
                )
                return

            target_path = Path(target)
            folder = (
                target_path.parent
                if target_path.suffix
                else target_path
            )

            if folder.exists():
                os.startfile(os.fspath(folder))
            else:
                QtWidgets.QMessageBox.information(
                    self,
                    'Información',
                    'La carpeta de destino no existe.',
                )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Error',
                f'No se pudo abrir el destino:\n{e}',
            )

    def on_tree_context_menu(self, pos: QtCore.QPoint):
        """
        Muestra el menú contextual del árbol en la posición indicada.

        Args:
            pos: Posición del cursor dentro del widget árbol.
        """
        global_pos = self.tree.viewport().mapToGlobal(pos)
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        can_paste = bool(self._internal_clipboard['paths'])

        if item:
            p = item.data(0, ROLE_PATH)
            is_dir = bool(item.data(0, ROLE_IS_DIR))

            if not is_dir:
                menu.addAction(
                    'Ejecutar',
                    lambda it=item: self.on_item_activated(it),
                )
                menu.addAction('Renombrar…', self.rename_current)
                menu.addAction('Eliminar…', self.delete_current)
                menu.addSeparator()
                menu.addAction(
                    'Abrir carpeta contenedora',
                    lambda: self._open_folder(Path(p).parent),
                )

            try:
                if p and Path(str(p)).suffix.lower() == '.lnk':
                    menu.addAction(
                        'Abrir destino',
                        lambda it=item: self._open_shortcut_target_folder(it),
                    )
            except Exception:
                LOGGER.exception(
                    '[auto] Exception capturada en MainWindow::on_tree_context_menu'
                )

            menu.addSeparator()

            if is_dir:
                menu.addAction(
                    'Abrir carpeta',
                    lambda: self._open_folder(Path(p)),
                )
                menu.addAction(
                    'Renombrar categoría…',
                    self.rename_current,
                )
                menu.addAction(
                    'Eliminar categoría…',
                    self.delete_current,
                )
                menu.addSeparator()
                menu.addAction(
                    'Abrir carpeta contenedora',
                    lambda: self._open_folder(Path(p).parent),
                )
                menu.addSeparator()
                menu.addAction(
                    'Crear subcarpeta…',
                    self.create_subfolder_here,
                )

            menu.addSeparator()
            menu.addAction('Copiar', self.copy_selection)
            menu.addAction('Cortar', self.cut_selection)

            act_paste = menu.addAction(
                'Pegar',
                self.paste_into_target,
            )
            act_paste.setEnabled(can_paste)

        else:
            menu.addAction(
                'Crear subcarpeta en carpeta base…',
                self._create_subfolder_at_root,
            )
            menu.addSeparator()

            act_paste = menu.addAction(
                'Pegar en carpeta base',
                self._paste_into_dir(self.base_dir()),
            )
            act_paste.setEnabled(can_paste)

        menu.exec(global_pos)

    def _open_folder(self, path: Path):
        """
        Abre una carpeta en el Explorador de Windows.

        Args:
            path: Ruta del directorio a abrir.
        """
        try:
            os.startfile(os.fspath(path))
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Error',
                f'No se pudo abrir la carpeta:\n{e}',
            )

    def _current_item_path(self) -> Tuple[Optional[Path], bool]:
        """
        Devuelve la ruta y tipo del elemento actualmente seleccionado.

        Returns:
            Tupla (ruta, es_directorio).
        """
        it = self.tree.currentItem()
        if not it:
            return (None, False)

        p = it.data(0, ROLE_PATH)
        is_dir = bool(it.data(0, ROLE_IS_DIR))
        return (Path(str(p)) if p else None, is_dir)

    def rename_current(self):
        """
        Renombra el elemento seleccionado (archivo o categoría).
        """
        p, is_dir = self._current_item_path()
        if not p:
            return

        if is_dir:
            new_text, ok = QtWidgets.QInputDialog.getText(
                self,
                'Renombrar categoría',
                'Nuevo nombre:',
                text=p.name,
            )
            if not ok:
                return

            new_name = sanitize_filename(new_text.strip())
            if not new_name:
                return

            dest = p.parent / new_name
            if dest.exists():
                QtWidgets.QMessageBox.warning(
                    self,
                    'Nombre en uso',
                    f'Ya existe una carpeta con ese nombre:\n{dest}',
                )
                return

            try:
                p.rename(dest)
                self.load_categories()
                self.select_item_by_path(dest)
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    'Error',
                    f'No se pudo renombrar la categoría:\n{e}',
                )

        else:
            stem = p.stem
            new_text, ok = QtWidgets.QInputDialog.getText(
                self,
                'Renombrar',
                'Nuevo nombre (sin extensión):',
                text=stem,
            )
            if not ok:
                return

            new_stem = sanitize_filename(new_text.strip())
            if not new_stem:
                return

            dest = unique_path(
                p.parent,
                new_stem,
                p.suffix,
            )

            try:
                p.rename(dest)
                self.load_categories()
                self.select_item_by_path(dest)
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    'Error',
                    f'No se pudo renombrar:\n{e}',
                )

    def delete_current(self):
        """
        Elimina el elemento actualmente seleccionado.

        Comportamiento:
        - Si es una carpeta, solicita confirmación y elimina TODO su contenido.
        - Si es un archivo, elimina únicamente el acceso seleccionado.

        WARNING:
            La eliminación de carpetas es irreversible.
        """
        p, is_dir = self._current_item_path()
        if not p:
            return

        if is_dir:
            reply = QtWidgets.QMessageBox.question(
                self,
                'Eliminar categoría',
                f'¿Eliminar la carpeta y TODO su contenido?\n\n{p}',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            try:
                shutil.rmtree(p)
                self.load_categories()
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    'Error',
                    f'No se pudo eliminar la categoría:\n{e}',
                )
        else:
            reply = QtWidgets.QMessageBox.question(
                self,
                'Eliminar',
                f'¿Eliminar el acceso?\n\n{p.name}',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            try:
                p.unlink()
                self.load_categories()
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    'Error',
                    f'No se pudo eliminar:\n{e}',
                )

    def create_subfolder_here(self):
        """
        Crea una subcarpeta dentro del elemento actualmente seleccionado.

        Si no hay selección válida, se crea en la carpeta base.
        """
        it = self.tree.currentItem()
        if it:
            p = it.data(0, ROLE_PATH)
            is_dir = bool(it.data(0, ROLE_IS_DIR))
            dir_path = (
                Path(str(p))
                if p and is_dir
                else Path(str(p)).parent
                if p
                else self.base_dir()
            )
        else:
            dir_path = self.base_dir()

        self._create_subfolder_in_dir(dir_path)

    def _create_subfolder_at_root(self):
        """
        Crea una subcarpeta directamente en la carpeta base.
        """
        self._create_subfolder_in_dir(self.base_dir())

    def _create_subfolder_in_dir(self, dir_path: Path):
        """
        Crea una subcarpeta dentro de un directorio concreto.

        Args:
            dir_path: Directorio donde crear la subcarpeta.
        """
        name, ok = QtWidgets.QInputDialog.getText(
            self,
            'Crear subcarpeta',
            'Nombre de la subcarpeta:',
        )
        if not ok:
            return

        new_name = sanitize_filename(name.strip())
        if not new_name:
            return

        target = dir_path / new_name
        try:
            target.mkdir(parents=True, exist_ok=False)
            self.load_categories()
            self.select_item_by_path(target)
        except FileExistsError:
            QtWidgets.QMessageBox.warning(
                self,
                'Ya existe',
                f'La carpeta ya existe:\n{target}',
            )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Error',
                f'No se pudo crear la carpeta:\n{e}',
            )

    def _collect_selected_paths(self) -> List[Tuple[Path, bool]]:
        """
        Devuelve las rutas actualmente seleccionadas en el árbol.

        Returns:
            Lista de tuplas (ruta, es_directorio).
        """
        items = self.tree.selectedItems() or []
        out: List[Tuple[Path, bool]] = []

        for it in items:
            p = it.data(0, ROLE_PATH)
            if not p:
                continue
            p = Path(str(p))
            is_dir = bool(it.data(0, ROLE_IS_DIR))
            out.append((p, is_dir))

        return out

    def copy_selection(self):
        """
        Copia la selección actual al portapapeles interno.
        """
        paths = self._collect_selected_paths()
        if not paths:
            return
        self._internal_clipboard = {'paths': paths, 'cut': False}

    def cut_selection(self):
        """
        Marca la selección actual para cortar (mover).
        """
        paths = self._collect_selected_paths()
        if not paths:
            return
        self._internal_clipboard = {'paths': paths, 'cut': True}

    def _paste_into_dir(self, target_dir: Path):
        """
        Devuelve una función que pega la selección en un directorio concreto.

        Args:
            target_dir: Directorio destino.
        """
        def _do():
            self._perform_paste(target_dir)
        return _do

    def paste_into_target(self):
        """
        Pega el contenido del portapapeles interno en el destino actual.
        """
        it = self.tree.currentItem()
        if it:
            p = it.data(0, ROLE_PATH)
            is_dir = bool(it.data(0, ROLE_IS_DIR))
            target_dir = (
                Path(str(p))
                if p and is_dir
                else Path(str(p)).parent
                if p
                else self.base_dir()
            )
        else:
            target_dir = self.base_dir()

        self._perform_paste(target_dir)

    def _perform_paste(self, target_dir: Path):
        """
        Ejecuta la operación de copiar o mover desde el portapapeles interno.

        Args:
            target_dir: Directorio destino.
        """
        clip = self._internal_clipboard
        if not clip['paths']:
            return

        moved: List[Path] = []
        is_cut = bool(clip['cut'])

        for p, is_dir in clip['paths']:
            try:
                if is_dir:
                    if (
                        target_dir.resolve() == p.resolve()
                        or str(target_dir.resolve()).startswith(str(p.resolve()) + os.sep)
                    ):
                        continue

                    dst = unique_dir(target_dir, p.name)
                    if is_cut:
                        shutil.move(os.fspath(p), os.fspath(dst))
                    else:
                        shutil.copytree(p, dst)
                    moved.append(dst)
                else:
                    dst = unique_path(target_dir, p.stem, p.suffix)
                    target_dir.mkdir(parents=True, exist_ok=True)
                    if is_cut:
                        shutil.move(os.fspath(p), os.fspath(dst))
                    else:
                        shutil.copy2(p, dst)
                    moved.append(dst)

            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self,
                    'Error',
                    f'No se pudo completar la operación:\n{p}\n→ {target_dir}\n\n{e}',
                )

        if moved:
            if is_cut:
                self._internal_clipboard = {'paths': [], 'cut': False}
            self.load_categories()
            try:
                self.select_item_by_path(moved[-1])
            except Exception:
                LOGGER.exception(
                    '[auto] Exception capturada en MainWindow::_perform_paste'
                )

    def _item_is_file(self, it: Optional[QTreeWidgetItem]) -> bool:
        """
        Indica si un item representa un archivo.
        """
        return bool(
            it and it.data(0, ROLE_PATH)
            and not bool(it.data(0, ROLE_IS_DIR))
        )

    def _item_is_category(self, it: Optional[QTreeWidgetItem]) -> bool:
        """
        Indica si un item representa una categoría (carpeta).
        """
        return bool(
            it and it.data(0, ROLE_PATH)
            and bool(it.data(0, ROLE_IS_DIR))
        )

    def _run_script(
        self,
        script_path: str,
        args: str = "",
        wait: bool = True,
        timeout_sec: int = 0,
        run_hidden: bool = True,
    ):
        """
        Wrapper fino para ejecutar scripts externos.

        Delegado directamente a core.scripts.run_script
        para mantener compatibilidad con todo el código existente.
        """
        from core.scripts import run_script

        return run_script(
            script_path=script_path,
            args=args,
            wait=wait,
            timeout_sec=timeout_sec,
            run_hidden=run_hidden,
        )

    def _confirm_and_quit(self):
        """
        Solicita confirmación y cierra la aplicación.
        """
        reply = QtWidgets.QMessageBox.question(
            self,
            'Salir',
            '¿Seguro que deseas salir de la aplicación?',
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply == QtWidgets.QMessageBox.Yes:
            app = QtWidgets.QApplication.instance()
            if app is not None:
                app.quit()

    def _on_about_to_quit(self):
        """
        Maneja el evento de cierre inminente de la aplicación.

        Ejecuta tareas de limpieza y scripts de salida.
        """
        try:
            try:
                LOGGER.info('Aplicación saliendo…')
            except Exception:
                LOGGER.exception(
                    '[auto] Exception capturada en MainWindow::_on_about_to_quit'
                )

            # Ejecutar script post-salida
            self.controller.run_post_exit_script()

        except Exception as e:
            try:
                sys.stderr.write(
                    f'[post_exit_script] Excepción: {e}\n'
                )
            except Exception:
                LOGGER.exception(
                    '[auto] Exception capturada en MainWindow::_on_about_to_quit'
                )

    def ask_drop_import_choice(self, count: int) -> str | None:
        """
        Pregunta al usuario cómo importar elementos arrastrados.

        Args:
            count: Número de elementos a importar.

        Returns:
            Elección del usuario o None si cancela.
        """
        dlg = DropImportDialog(self, count=count)
        if dlg.exec() != QDialog.Accepted:
            return None
        return dlg.choice()

apply_server_patches(MainWindow)
# Qué hace y por qué está aquí -> apply_server_patches(MainWindow)
# - Aplica parches dinámicos relacionados con el servidor integrado directamente sobre la clase MainWindow.
# - Permite añadir o modificar comportamiento sin acoplar la lógica del servidor al módulo principal de la UI.
# - Es una técnica consciente para:
#   * Mantener separación de responsabilidades.
#   * Evitar dependencias circulares.
#   * Facilitar mantenimiento o desactivación futura del servidor.
# IMPORTANTE:
# - Esta llamada debe ejecutarse tras definir completamente la clase.
# - No debe moverse dentro de la clase ni dentro de métodos.
# - Forma parte intencional del flujo de inicialización.

