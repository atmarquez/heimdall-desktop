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
ui.config.server (pestaña Log)

Pestaña de configuración relacionada con el sistema de logging
de la aplicación.

Este módulo implementa la clase `LogConfigTab`, que permite:
- Habilitar o deshabilitar el logging.
- Configurar la ruta del fichero de log.
- Visualizar eventos recientes almacenados en memoria.
- Limpiar el fichero de log manualmente.

IMPORTANT:
- Esta pestaña NO gestiona directamente la configuración global
  de logging (handlers, niveles, etc.).
- Únicamente actúa como interfaz de usuario sobre valores ya existentes.
- La persistencia final se realiza desde capas superiores
  (por ejemplo, el diálogo principal de Configuración).

NOTE:
- Aunque el comentario de cabecera mencione “server.py”, este módulo
  implementa la pestaña “Log”. El nombre se conserva por compatibilidad
  histórica y no debe alterarse.
"""

# ------------------------------------------------------------
# ui/config/server.py -> Clase LogConfigTab
# ------------------------------------------------------------
# Pestaña “Log” dentro de "Configuración"

from PySide6 import QtWidgets, QtCore, QtGui
from logutils.setup import get_logger
from logutils.memory import log_latest, log_count
from config.service import app_dir
from config.service import save_config

import os

LOGGER = get_logger()


class LogConfigTab(QtWidgets.QWidget):
    """
    Pestaña de configuración del sistema de logging.

    Proporciona:
    - Activación/desactivación del log.
    - Selección del fichero de log.
    - Visualización en tiempo real de eventos recientes.
    """

    def __init__(self, parent_tabs, cfg: dict):
        """
        Inicializa la pestaña de configuración de Log.

        Args:
            parent_tabs: Widget contenedor (habitualmente un QTabWidget).
            cfg: Diccionario de configuración actual.
        """
        super().__init__(parent_tabs)
        self.cfg = cfg

        self._build_ui()
        self._start_timer()

    def _build_ui(self):
        """
        Construye la interfaz gráfica de la pestaña Log.

        NOTE:
            Este método solo crea y configura widgets.
            No aplica ni persiste la configuración.
        """
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Activar/desactivar logging
        self.log_enabled_cb = QtWidgets.QCheckBox(
            'Habilitar registro (log)',
            self
        )
        self.log_enabled_cb.setChecked(
            bool(self.cfg.get('log_enabled', True))
        )
        layout.addWidget(self.log_enabled_cb)

        # Selección de fichero de log
        path_row = QtWidgets.QWidget(self)
        hp = QtWidgets.QHBoxLayout(path_row)
        hp.setContentsMargins(0, 0, 0, 0)

        self.log_path_edit = QtWidgets.QLineEdit(self)
        self.log_path_edit.setText(
            self.cfg.get('log_file_path', 'launcher.log')
        )

        btn_browse = QtWidgets.QPushButton('Examinar…', self)
        btn_browse.clicked.connect(self._browse_log_file)

        hp.addWidget(self.log_path_edit, 1)
        hp.addWidget(btn_browse)

        layout.addWidget(QtWidgets.QLabel('Fichero de log:', self))
        layout.addWidget(path_row)

        # Botones de acción sobre el log
        btns = QtWidgets.QWidget(self)
        hb = QtWidgets.QHBoxLayout(btns)
        hb.setContentsMargins(0, 0, 0, 0)

        btn_view = QtWidgets.QPushButton('Ver log', self)
        btn_clear = QtWidgets.QPushButton('Borrar log', self)

        btn_view.clicked.connect(self._view_log_file)
        btn_clear.clicked.connect(self._clear_log_file)

        hb.addWidget(btn_view)
        hb.addWidget(btn_clear)

        layout.addWidget(btns)

        # Separador visual
        sep = QtWidgets.QFrame(self)
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(sep)

        # Parte superior del visor en memoria
        top = QtWidgets.QWidget(self)
        ht = QtWidgets.QHBoxLayout(top)
        ht.setContentsMargins(0, 0, 0, 0)

        self.log_count_label = QtWidgets.QLabel('', self)
        ht.addWidget(self.log_count_label)
        ht.addStretch(1)

        ht.addWidget(QtWidgets.QLabel('Mostrar últimos N:', self))
        self.log_sb_n = QtWidgets.QSpinBox(self)
        self.log_sb_n.setRange(1, 1000)
        self.log_sb_n.setValue(
            int(self.cfg.get('log_latest_n', 200) or 200)
        )
        ht.addWidget(self.log_sb_n)

        layout.addWidget(top)

        # Lista de eventos de log (en memoria)
        self.log_list = QtWidgets.QListWidget(self)
        try:
            font = QtGui.QFont('Consolas')
            font.setStyleHint(QtGui.QFont.Monospace)
            self.log_list.setFont(font)
        except Exception:
            # Fallback silencioso si la fuente no está disponible
            pass

        self.log_list.setSelectionMode(
            QtWidgets.QAbstractItemView.NoSelection
        )
        self.log_list.setUniformItemSizes(True)
        layout.addWidget(self.log_list, 1)

    def _start_timer(self):
        """
        Inicia el temporizador que refresca la vista de logs.

        El refresco es periódico y poco costoso, ya que:
        - Solo se redibuja si hay cambios.
        """
        self._last_count = -1
        self._last_n = -1

        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(800)
        self.timer.timeout.connect(self._refresh)
        self.timer.start()

        self.log_sb_n.valueChanged.connect(
            lambda _: self._refresh(force=True)
        )
        self._refresh(force=True)

    def _refresh(self, force=False):
        """
        Actualiza la lista de eventos de log mostrados.

        Args:
            force: Si True, fuerza el refresco aunque no haya cambios detectados.
        """
        try:
            total = log_count()
        except Exception:
            total = 0

        n = int(self.log_sb_n.value())

        if not force and total == self._last_count and n == self._last_n:
            return

        try:
            entries = log_latest(n)
        except Exception:
            entries = []

        self.log_list.clear()

        for ev in entries:
            self.log_list.addItem(self._format_log_line(ev))

        self.log_count_label.setText(
            f'Eventos: {total} · Mostrando: {len(entries)}'
        )
        self._last_count = total
        self._last_n = n

    def _resolve_log_path(self) -> str:
        """
        Resuelve la ruta absoluta del fichero de log.

        Returns:
            Ruta absoluta al fichero de log.
        """
        p = self.log_path_edit.text().strip()
        if not p:
            return ''
        if not os.path.isabs(p):
            p = os.path.join(app_dir(), p)
        return p

    def _browse_log_file(self):
        """
        Abre un diálogo para seleccionar el fichero de log.
        """
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            'Seleccionar fichero de log',
            self._resolve_log_path() or app_dir(),
            'Log (*.log *.txt);;Todos (*.*)'
        )
        if path:
            self.log_path_edit.setText(path)

    def _view_log_file(self):
        """
        Abre el fichero de log con la aplicación por defecto del sistema.
        """
        path = self._resolve_log_path()
        if path and os.path.exists(path):
            os.startfile(path)

    def _clear_log_file(self):
        """
        Borra el contenido del fichero de log.

        WARNING:
            Esta operación es irreversible.
        """
        path = self._resolve_log_path()
        if path:
            try:
                open(path, 'w').close()
            except Exception:
                LOGGER.exception('Error borrando log')

    def _format_log_line(self, ev: dict) -> str:
        """
        Convierte un evento de log en una línea legible.

        Args:
            ev: Diccionario con los datos del evento de log.

        Returns:
            Cadena formateada para mostrar en la lista.
        """
        try:
            import datetime
            ts = float(ev.get("ts", 0) or 0)
            t = (
                datetime.datetime.fromtimestamp(ts).strftime("%H:%M:%S")
                if ts > 0 else "--:--:--"
            )
        except Exception:
            t = "--:--:--"

        level = str(ev.get("level", "")).upper()
        msg = str(ev.get("message", ""))

        return f"[{t}] {level} {msg}"

    def apply(self):
        """
        Guarda la configuración de logging en self.cfg.

        NOTE:
            - NO persiste en disco.
            - La escritura final se delega al diálogo de Configuración.
        """
        self.cfg['log_enabled'] = self.log_enabled_cb.isChecked()
        self.cfg['log_file_path'] = self.log_path_edit.text().strip()
        self.cfg['log_latest_n'] = int(self.log_sb_n.value())

        # Aquí se podría guardar en disco, pero se delega
        # al _on_apply_clicked del diálogo principal.

    def gather(self) -> dict:
        """
        Recoge la configuración del logging desde la UI.

        Returns:
            Diccionario parcial con opciones de logging.
        """
        cfg = {}

        if hasattr(self, 'log_enabled_cb'):
            cfg['log_enabled'] = bool(
                self.log_enabled_cb.isChecked()
            )

        if hasattr(self, 'log_path_edit'):
            path = self.log_path_edit.text().strip()
            cfg['log_file_path'] = path or 'launcher.log'

        if hasattr(self, 'log_level_combo'):
            levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
            idx = int(self.log_level_combo.currentIndex())
            if 0 <= idx < len(levels):
                cfg['log_level'] = levels[idx]

        if hasattr(self, 'log_maxsize_edit'):
            try:
                cfg['log_max_size_mb'] = int(
                    self.log_maxsize_edit.text()
                )
            except Exception:
                pass

        return cfg

    def apply_to_cfg(self, cfg: dict):
        """
        Aplica la configuración de logging al diccionario cfg.

        Args:
            cfg: Diccionario de configuración global.
        """
        cfg.update(self.gather())
        
    def populate_from_cfg(self):
        """
        Carga los valores desde la configuración actual (`cfg`)
        hacia el estado interno y la interfaz.
        """    
        self.log_enabled_cb.setChecked(
            bool(self.cfg.get('log_enabled', True))
        )
        
        self.log_path_edit.setText(
            self.cfg.get('log_file_path', 'launcher.log')
        )

        self.log_sb_n.setValue(
            int(self.cfg.get('log_latest_n', 200) or 200)
        )
        