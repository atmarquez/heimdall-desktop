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
ui.config.appearance

Pestaña de configuración de Apariencia de Heimdall Desktop.

Este módulo implementa la pestaña “Apariencia” dentro del diálogo de
Configuración de la aplicación.

Responsabilidades principales:
- Permitir al usuario personalizar el título visible de la aplicación.
- Seleccionar el tema visual (claro, oscuro, sistema, alto contraste, etc.).
- Configurar opciones visuales relacionadas con la UI.
- Emitir señales cuando los cambios requieren aplicarse en caliente.

IMPORTANTE:
- Este módulo es exclusivamente de interfaz gráfica (UI).
- No contiene lógica de negocio ni persistencia directa:
  los valores se delegan a capas superiores (controlador / config service).
- Está diseñado para ser independiente de la plataforma, salvo
  en lo estrictamente visual.

Clase principal expuesta:
- AppearanceConfigTab
"""

# ------------------------------------------------------------
# ui/config/appearance.py -> Clase AppearanceConfigTab
# ------------------------------------------------------------
# Pestaña “Apariencia” dentro de "Configuración"

from PySide6 import QtWidgets, QtGui
from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLineEdit, QPushButton,
    QComboBox, QCheckBox, QSpinBox, QLabel, QHBoxLayout
)

from PySide6.QtCore import Signal

from config.service import default_app_title

from themes.theme_manager import (
    THEME_SYSTEM,
    THEME_LIGHT,
    THEME_DARK,
    THEME_HIGH_CONTRAST,
    THEME_HOST_SYSTEM,
)

class AppearanceConfigTab(QWidget):
    """
    Pestaña de configuración de Apariencia.

    Esta pestaña permite al usuario configurar aspectos visuales
    de la aplicación, incluyendo:
    - Tema visual (claro, oscuro, sistema, alto contraste, etc.).
    - Icono de la aplicación.
    - Tamaño y posición inicial de la ventana.
    - Comportamiento y colores de la barra de título.

    NOTE:
        Esta clase NO guarda configuración en disco directamente.
        Se limita a:
        - Leer valores desde un diccionario de configuración.
        - Reflejar dichos valores en la UI.
        - Volcar los cambios nuevamente al diccionario.

    La persistencia y aplicación real de los cambios se delega
    a capas superiores (controlador / servicio de configuración).
    """

    #: Señal emitida cuando un cambio requiere reinicio de la aplicación.
    restart_requested = Signal()

    def __init__(self, cfg: dict, parent=None):
        """
        Inicializa la pestaña de Apariencia.

        Args:
            cfg: Diccionario de configuración actual de la aplicación.
            parent: Widget padre (normalmente el diálogo de Configuración).

        IMPORTANT:
            El estado interno se inicializa ANTES de construir la UI
            para evitar efectos secundarios al cargar valores.
        """
        super().__init__(parent)
        self.cfg = cfg

        # ✅ Estado interno (ANTES de tocar UI)
        # Ruta del icono seleccionada actualmente (puede diferir del cfg
        # hasta que se aplique explícitamente).
        self._icon_path = None

        # Construcción de la interfaz y carga de valores iniciales
        self._build_ui()
        self.populate_from_cfg()

    def populate_from_cfg(self):
        """
        Rellena la interfaz de usuario con los valores del diccionario de configuración.

        Este método:
        - Carga el icono configurado.
        - Selecciona el tema actual.
        - Establece tamaño y posición de la ventana.
        - Aplica opciones visuales de la barra de título.

        NOTE:
            Este método NO modifica la configuración original,
            únicamente sincroniza la UI con ella.
        """
        if self._icon_path is None:
            self._icon_path = self.cfg.get('app_icon_path', '')
            self.icon_edit.setText(self._icon_path)

        current_theme = self.cfg.get('theme', 'system')
        idx = (
            self._theme_keys.index(current_theme)
            if current_theme in self._theme_keys
            else 0
        )
        self.theme_combo.setCurrentIndex(idx)

        win = self.cfg.get('window', {})
        self.win_w_sb.setValue(int(win.get('width', 520)))
        self.win_h_sb.setValue(int(win.get('height', 640)))
        self.win_x_sb.setValue(int(win.get('x', 100)))
        self.win_y_sb.setValue(int(win.get('y', 100)))

        self.tb_align_dark_cb.setChecked(
            bool(self.cfg.get('titlebar_align_dark_mode', False))
        )

    def apply_to_cfg(self, cfg: dict):
        """
        Aplica los valores actuales de la UI al diccionario de configuración.

        Este método:
        - Actualiza el icono, tema y ajustes de barra de título.
        - Sobrescribe tamaño y posición de la ventana.
        - Devuelve el diccionario modificado.

        Args:
            cfg: Diccionario de configuración a modificar.

        Returns:
            El mismo diccionario `cfg`, actualizado con los valores
            actuales de la pestaña.

        IMPORTANT:
            Este método NO guarda en disco ni aplica cambios visuales.
            Solo prepara los datos para que otra capa los procese.
        """
        cfg['app_icon_path'] = (self._icon_path or '').strip()
        cfg['theme'] = self.theme_combo.currentData()

        cfg['titlebar_align_dark_mode'] = self.tb_align_dark_cb.isChecked()
        cfg['titlebar_color'] = self._tb_bg_btn.property('_hex') or ''
        cfg['titlebar_text_color'] = self._tb_fg_btn.property('_hex') or ''

        win = cfg.get('window', {})
        win['width'] = int(self.win_w_sb.value())
        win['height'] = int(self.win_h_sb.value())
        win['x'] = int(self.win_x_sb.value())
        win['y'] = int(self.win_y_sb.value())
        cfg['window'] = win

        return cfg
        
    def _build_ui(self):
        """
        Construye la interfaz gráfica de la pestaña Apariencia.

        Este método es responsable de:
        - Crear todos los controles visuales de la pestaña.
        - Inicializar valores desde la configuración actual.
        - Conectar señales entre campos relacionados.
        - Gestionar opciones específicas de Windows (barra de título).

        IMPORTANT:
            - Este método NO escribe en la configuración.
            - Solo inicializa y enlaza la interfaz gráfica.
            - Los valores se vuelcan posteriormente mediante `apply_to_cfg`.
        """        
        appearance_tab = self
        app_form = QFormLayout(appearance_tab)
        self.icon_edit = QLineEdit(appearance_tab)
                
        # --------------------------------------------------
        # Icono de la aplicación
        # --------------------------------------------------
        self.icon_edit.setText(self.cfg.get('app_icon_path') or '')
        btn_icon = QPushButton('Buscar icono…', appearance_tab)
        btn_icon.clicked.connect(self.choose_icon)
        h2 = QtWidgets.QHBoxLayout()
        h2.addWidget(self.icon_edit)
        h2.addWidget(btn_icon)
        w2 = QWidget()
        w2.setLayout(h2)
        app_form.addRow('Icono de la aplicación:', w2)
                
        # --------------------------------------------------
        # Selector de tema visual
        # --------------------------------------------------
        self.theme_combo = QtWidgets.QComboBox(appearance_tab)
        theme_labels = {THEME_SYSTEM: 'Por defecto del sistema (QSS externo)', THEME_LIGHT: 'Claro', THEME_DARK: 'Oscuro', THEME_HIGH_CONTRAST: 'Alto contraste', THEME_HOST_SYSTEM: 'Sistema operativo invitado (Windows)'}
        self._theme_keys = [THEME_HOST_SYSTEM, THEME_LIGHT, THEME_DARK, THEME_HIGH_CONTRAST, THEME_SYSTEM]
        for k in self._theme_keys:
            self.theme_combo.addItem(theme_labels[k], userData=k)
        current_theme = self.cfg.get('theme', THEME_SYSTEM)
        idx = self._theme_keys.index(current_theme) if current_theme in self._theme_keys else self._theme_keys.index(THEME_SYSTEM)
        self.theme_combo.setCurrentIndex(idx)
        
        
        # --------------------------------------------------
        # Inicialización defensiva de barra de título (Windows)
        # --------------------------------------------------
        try:
            if hasattr(self, '_tb_bg_btn'):
                self._tb_bg_btn._apply_hex(self.cfg.get('titlebar_color', '') or '')
            if hasattr(self, '_tb_fg_btn'):
                self._tb_fg_btn._apply_hex(self.cfg.get('titlebar_text_color', '') or '')
            if hasattr(self, 'tb_align_dark_cb'):
                self.tb_align_dark_cb.setChecked(bool(self.cfg.get('titlebar_align_dark_mode', False)))
        except Exception:
            pass
        app_form.addRow('Tema visual:', self.theme_combo)
        
        
        # --------------------------------------------------
        # Colores de barra de título (Windows)
        # ------------------------------------------------
        def _mk_color_btn(initial_hex: str):
            """
            Crea un botón selector de color asociado a un valor hexadecimal.

            Args:
                initial_hex: Color inicial en formato '#RRGGBB'.

            Returns:
                QPushButton configurado con selector de color.
            """
            btn = QPushButton('', appearance_tab)
            btn.setFixedWidth(36)
            btn.setFixedHeight(20)
            def _apply_hex(h):
                """
                Aplica un color hexadecimal visualmente al botón.
                """                
                if h and isinstance(h, str) and h.startswith('#') and len(h) == 7:
                    btn.setStyleSheet(f'QPushButton {{ background: {h}; border: 1px solid #888; }}')
                    btn.setProperty('_hex', h)
                else:
                    btn.setStyleSheet('')
                    btn.setProperty('_hex', '')
            _apply_hex(initial_hex)
            def _pick():
                """
                Abre un selector de color y actualiza el botón.
                """                
                from PySide6 import QtGui as _QtGui
                curr = btn.property('_hex') or '#000000'
                col = _QtGui.QColor(curr)
                chosen = QtWidgets.QColorDialog.getColor(col, self, 'Elegir color')
                if chosen.isValid():
                    _apply_hex(chosen.name(_QtGui.QColor.HexRgb))
            btn.clicked.connect(_pick)
            btn._apply_hex = _apply_hex
            return btn

        _init_bg = self.cfg.get('titlebar_color', '') or ''
        _init_fg = self.cfg.get('titlebar_text_color', '') or ''
        self._tb_bg_btn = _mk_color_btn(_init_bg)
        self._tb_fg_btn = _mk_color_btn(_init_fg)

        # Deshabilitar selectores en Windows 10 (solo modo oscuro/claro disponible)       
        # --------------------------------------------------
        # Compatibilidad Windows 10 / 11
        # --------------------------------------------------
        try:
            import sys as _sys
            _is_win11 = (_sys.getwindowsversion().build >= 22000)
        except Exception:
            _is_win11 = False
        self._tb_bg_btn.setEnabled(_is_win11)
        self._tb_fg_btn.setEnabled(_is_win11)
        if not _is_win11:
            self._tb_bg_btn.setToolTip('Windows 10: color de barra no soportado (solo modo oscuro/claro).')
            self._tb_fg_btn.setToolTip('Windows 10: color de texto no soportado (solo modo oscuro/claro).')

        btn_reset_bg = QPushButton('Restablecer', appearance_tab)
        btn_reset_bg.clicked.connect(lambda: self._tb_bg_btn._apply_hex(''))
        btn_reset_fg = QPushButton('Restablecer', appearance_tab)
        btn_reset_fg.clicked.connect(lambda: self._tb_fg_btn._apply_hex(''))

        # --------------------------------------------------
        # Fila color barra de título
        # --------------------------------------------------
        row_tb_bg = QWidget(appearance_tab)
        lay_tb_bg = QtWidgets.QHBoxLayout(row_tb_bg)
        lay_tb_bg.setContentsMargins(0,0,0,0)
        lay_tb_bg.addWidget(self._tb_bg_btn)
        lay_tb_bg.addWidget(btn_reset_bg)
        app_form.addRow('Color barra de título:', row_tb_bg)

        # --------------------------------------------------
        # Fila color texto barra de título
        # --------------------------------------------------
        row_tb_fg = QWidget(appearance_tab)
        lay_tb_fg = QtWidgets.QHBoxLayout(row_tb_fg)
        lay_tb_fg.setContentsMargins(0,0,0,0)
        lay_tb_fg.addWidget(self._tb_fg_btn)
        lay_tb_fg.addWidget(btn_reset_fg)
        app_form.addRow('Color texto barra de título:', row_tb_fg)

        # Mensaje aclaratorio para Windows 10 respecto al color de barra de título
        # --------------------------------------------------
        # Aviso explicativo para Windows 10
        # --------------------------------------------------
        try:
            import sys as _sys
            _is_win11 = (_sys.getwindowsversion().build >= 22000)
        except Exception:
            _is_win11 = False
        self.win10_titlebar_msg = QLabel("En Windows 10 no se soporta el color de barra de título.\nOpciones disponibles en Windows 10:\n  • Alinear con modo oscuro del sistema (activa/desactiva marco oscuro).\n  • Resto de apariencia vía tema (QSS/Host System).", appearance_tab)
        self.win10_titlebar_msg.setWordWrap(True)
        self.win10_titlebar_msg.setStyleSheet('color: #b00;')
        self.win10_titlebar_msg.setVisible(not _is_win11)
        app_form.addRow('', self.win10_titlebar_msg)
        
        # --------------------------------------------------
        # Alineación con modo oscuro del sistema
        # --------------------------------------------------
        self.tb_align_dark_cb = QCheckBox('Alinear con modo oscuro del sistema (tema Host System)', appearance_tab)
        try:
            self.tb_align_dark_cb.setChecked(bool(self.cfg.get('titlebar_align_dark_mode', False)))
        except Exception:
            self.tb_align_dark_cb.setChecked(False)
        app_form.addRow('', self.tb_align_dark_cb)
        
        # --------------------------------------------------
        # Tamaño de ventana (ancho / alto)
        # --------------------------------------------------
        self.win_w_edit = QLineEdit(appearance_tab)
        self.win_w_edit.setValidator(QtGui.QIntValidator(100, 10000, self.win_w_edit))
        self.win_w_sb = QSpinBox(appearance_tab)
        self.win_w_sb.setRange(320, 10000)
        self.win_w_sb.setSingleStep(10)
        self.win_h_edit = QLineEdit(appearance_tab)
        self.win_h_edit.setValidator(QtGui.QIntValidator(100, 10000, self.win_h_edit))
        self.win_h_sb = QSpinBox(appearance_tab)
        self.win_h_sb.setRange(360, 10000)
        self.win_h_sb.setSingleStep(10)
        _win_cfg = self.cfg.get('window', {}) if isinstance(self.cfg.get('window', {}), dict) else {}
        _w = int(_win_cfg.get('width', 520) or 520)
        _h = int(_win_cfg.get('height', 640) or 640)
        _w = max(_w, 320)
        _h = max(_h, 360)
        self.win_w_edit.setText(str(_w))
        self.win_h_edit.setText(str(_h))
        self.win_w_sb.setValue(_w)
        self.win_h_sb.setValue(_h)
        _row_w = QWidget(appearance_tab)
        _lay_w = QtWidgets.QHBoxLayout(_row_w)
        _lay_w.setContentsMargins(0, 0, 0, 0)
        _lay_w.addWidget(self.win_w_edit, 1)
        _lay_w.addWidget(self.win_w_sb)
        app_form.addRow('Ancho de la interfaz (px):', _row_w)
        _row_h = QWidget(appearance_tab)
        _lay_h = QtWidgets.QHBoxLayout(_row_h)
        _lay_h.setContentsMargins(0, 0, 0, 0)
        _lay_h.addWidget(self.win_h_edit, 1)
        _lay_h.addWidget(self.win_h_sb)
        app_form.addRow('Alto de la interfaz (px):', _row_h)

        # --------------------------------------------------
        # Sincronización ancho
        # --------------------------------------------------
        def _sync_w_from_edit():
            """Descripción: Realiza 'w from edit'.

Args:
    (sin parámetros)

Returns:
    None."""
            try:
                val = int(self.win_w_edit.text() or '0')
            except Exception as e:
                val = 320
            if val < 320:
                val = 320
            self.win_w_sb.blockSignals(True)
            self.win_w_sb.setValue(val)
            self.win_w_sb.blockSignals(False)

        def _sync_h_from_edit():
            """Descripción: Realiza 'h from edit'.

Args:
    (sin parámetros)

Returns:
    None."""
            try:
                val = int(self.win_h_edit.text() or '0')
            except Exception as e:
                val = 360
            if val < 360:
                val = 360
            self.win_h_sb.blockSignals(True)
            self.win_h_sb.setValue(val)
            self.win_h_sb.blockSignals(False)

        def _sync_w_from_sb(v):
            """Descripción: Realiza 'w from sb'.

Args:
    v: Valor genérico.

Returns:
    None."""
            self.win_w_edit.blockSignals(True)
            self.win_w_edit.setText(str(v))
            self.win_w_edit.blockSignals(False)

        def _sync_h_from_sb(v):
            """Descripción: Realiza 'h from sb'.

Args:
    v: Valor genérico.

Returns:
    None."""
            self.win_h_edit.blockSignals(True)
            self.win_h_edit.setText(str(v))
            self.win_h_edit.blockSignals(False)
        self.win_w_edit.textEdited.connect(lambda _=None: _sync_w_from_edit())
        self.win_h_edit.textEdited.connect(lambda _=None: _sync_h_from_edit())
        self.win_w_sb.valueChanged.connect(_sync_w_from_sb)
        self.win_h_sb.valueChanged.connect(_sync_h_from_sb)
        self.win_x_edit = QLineEdit(appearance_tab)
        self.win_x_edit.setValidator(QtGui.QIntValidator(-10000, 10000, self.win_x_edit))
        self.win_x_sb = QSpinBox(appearance_tab)
        self.win_x_sb.setRange(-10000, 10000)
        self.win_x_sb.setSingleStep(10)
        self.win_y_edit = QLineEdit(appearance_tab)
        self.win_y_edit.setValidator(QtGui.QIntValidator(-10000, 10000, self.win_y_edit))
        self.win_y_sb = QSpinBox(appearance_tab)
        self.win_y_sb.setRange(-10000, 10000)
        self.win_y_sb.setSingleStep(10)
        _win_cfg_pos = self.cfg.get('window', {}) if isinstance(self.cfg.get('window', {}), dict) else {}
        _parent = self.parent() if hasattr(self, 'parent') else None
        try:
            _px = int(_win_cfg_pos.get('x', _parent.pos().x() if _parent else 100) or 0)
            _py = int(_win_cfg_pos.get('y', _parent.pos().y() if _parent else 100) or 0)
        except Exception as e:
            _px, _py = (100, 100)
        self.win_x_edit.setText(str(_px))
        self.win_x_sb.setValue(_px)
        self.win_y_edit.setText(str(_py))
        self.win_y_sb.setValue(_py)
        _row_x = QWidget(appearance_tab)
        _lay_x = QtWidgets.QHBoxLayout(_row_x)
        _lay_x.setContentsMargins(0, 0, 0, 0)
        _lay_x.addWidget(self.win_x_edit, 1)
        _lay_x.addWidget(self.win_x_sb)
        app_form.addRow('Posición X de la interfaz (px):', _row_x)
        _row_y = QWidget(appearance_tab)
        _lay_y = QtWidgets.QHBoxLayout(_row_y)
        _lay_y.setContentsMargins(0, 0, 0, 0)
        _lay_y.addWidget(self.win_y_edit, 1)
        _lay_y.addWidget(self.win_y_sb)
        app_form.addRow('Posición Y de la interfaz (px):', _row_y)

        def _sync_x_from_edit():
            """Descripción: Realiza 'x from edit'.

Args:
    (sin parámetros)

Returns:
    None."""
            try:
                val = int(self.win_x_edit.text() or '0')
            except Exception as e:
                val = 0
            self.win_x_sb.blockSignals(True)
            self.win_x_sb.setValue(val)
            self.win_x_sb.blockSignals(False)

        def _sync_y_from_edit():
            """Descripción: Realiza 'y from edit'.

Args:
    (sin parámetros)

Returns:
    None."""
            try:
                val = int(self.win_y_edit.text() or '0')
            except Exception as e:
                val = 0
            self.win_y_sb.blockSignals(True)
            self.win_y_sb.setValue(val)
            self.win_y_sb.blockSignals(False)

        def _sync_x_from_sb(v):
            """Descripción: Realiza 'x from sb'.

Args:
    v: Valor genérico.

Returns:
    None."""
            self.win_x_edit.blockSignals(True)
            self.win_x_edit.setText(str(v))
            self.win_x_edit.blockSignals(False)

        def _sync_y_from_sb(v):
            """Descripción: Realiza 'y from sb'.

Args:
    v: Valor genérico.

Returns:
    None."""
            self.win_y_edit.blockSignals(True)
            self.win_y_edit.setText(str(v))
            self.win_y_edit.blockSignals(False)
        self.win_x_edit.textEdited.connect(lambda _=None: _sync_x_from_edit())
        self.win_y_edit.textEdited.connect(lambda _=None: _sync_y_from_edit())
        self.win_x_sb.valueChanged.connect(_sync_x_from_sb)
        self.win_y_sb.valueChanged.connect(_sync_y_from_sb)
        
    def choose_icon(self):
        """
        Abre un diálogo para seleccionar un icono de la aplicación.

        Este método permite al usuario elegir un archivo de imagen
        válido como icono (por ejemplo: .ico, .png, .jpg).
        La ruta seleccionada se guarda en el estado interno y se
        refleja inmediatamente en la interfaz.

        NOTE:
            El cambio de icono no se aplica completamente en caliente.
            Es necesario reiniciar la aplicación para que el nuevo icono
            se vea en todos los contextos (barra de tareas, ventana, etc.).
        """
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            'Seleccionar icono',
            '',
            'Iconos / Imágenes (*.ico *.png *.jpg *.jpeg *.bmp)'
        )

        # Si el usuario cancela el diálogo, no se realiza ninguna acción
        if not path:
            return

        # Guardar la ruta seleccionada como estado interno
        self._icon_path = path
        self.icon_edit.setText(path)

        # Informar al usuario de que el cambio requiere reinicio
        QtWidgets.QMessageBox.information(
            self,
            'Reinicio necesario',
            'El cambio del icono se aplicará completamente tras reiniciar la aplicación.'
        )

