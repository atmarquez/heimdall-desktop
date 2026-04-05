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
Editor de tareas programadas.

Este módulo define el diálogo `TaskEditorDialog`, utilizado para crear
y editar tareas programadas que serán gestionadas por el programador
de tareas interno de la aplicación.

Permite configurar:
- Script a ejecutar y argumentos.
- Opciones de ejecución (espera, timeout, modo oculto).
- Estado de la tarea (activa/inactiva).
- Política de ejecución de tareas vencidas.
- Límite de repeticiones.
- Distintos modos de planificación temporal.

IMPORTANT:
    Este diálogo NO ejecuta tareas ni las programa directamente.
    Se limita a recopilar una definición completa y validada de la tarea.
"""

from pathlib import Path
from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import (
    QDialog, QLineEdit, QPushButton, QFileDialog,
    QWidget, QHBoxLayout, QCheckBox, QSpinBox, QLabel
)

from ui.helpers import HelpableDialogMixin


class TaskEditorDialog(HelpableDialogMixin, QDialog):
    """
    Diálogo para crear o editar una tarea programada.

    Permite definir tanto la acción (script) como la planificación
    temporal con distintos modos soportados por el scheduler interno.

    NOTE:
        Integra ayuda contextual mediante `HelpableDialogMixin` (F1).
    """

    #: Tema de ayuda asociado a este diálogo.
    help_topic = 'task_editor'

    def __init__(self, parent=None, values=None):
        """
        Inicializa el editor de tareas.

        Args:
            parent (QWidget, optional):
                Widget padre.
            values (dict, optional):
                Diccionario con valores iniciales de la tarea.
        """
        super().__init__(parent)
        self.setWindowTitle('Editar tarea programada')

        # Copia defensiva de valores iniciales
        v = (values or {}).copy()

        form = QtWidgets.QFormLayout(self)

        # ---------------------------------------------------------
        # Nombre descriptivo
        # ---------------------------------------------------------
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText(
            'Nombre descriptivo (opcional)'
        )
        self.name_edit.setText(v.get('name', ''))
        form.addRow('Nombre:', self.name_edit)

        # ---------------------------------------------------------
        # Configuración del script
        # ---------------------------------------------------------
        self.path_edit = QLineEdit(self)
        self.path_edit.setText(v.get('script', ''))

        btn_browse = QPushButton('Examinar…', self)

        def _browse():
            """
            Abre un diálogo para seleccionar el script a ejecutar.

            NOTE:
                Se muestran extensiones habituales de scripts,
                aunque se permite cualquier archivo.
            """
            path, _ = QFileDialog.getOpenFileName(
                self,
                'Seleccionar script',
                str(Path.cwd()),
                'Scripts (*.bat *.cmd *.ps1 *.py *.vbs *.exe);;Todos (*.*)'
            )
            if path:
                self.path_edit.setText(path)

        btn_browse.clicked.connect(_browse)

        row = QWidget(self)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(self.path_edit, 1)
        h.addWidget(btn_browse)
        form.addRow('Ruta del script:', row)

        self.args_edit = QLineEdit(self)
        self.args_edit.setText(v.get('args', ''))
        form.addRow('Argumentos:', self.args_edit)

        self.wait_cb = QCheckBox('Esperar a que termine', self)
        self.wait_cb.setChecked(bool(v.get('wait', True)))
        form.addRow('', self.wait_cb)

        self.timeout_sb = QSpinBox(self)
        self.timeout_sb.setRange(0, 3600)
        self.timeout_sb.setValue(int(v.get('timeout', 20) or 0))
        form.addRow(
            'Timeout (s, 0 = sin límite):',
            self.timeout_sb
        )

        self.hidden_cb = QCheckBox(
            'Ejecutar oculto (Windows)',
            self
        )
        self.hidden_cb.setChecked(bool(v.get('hidden', True)))
        form.addRow('', self.hidden_cb)

        # ---------------------------------------------------------
        # Estado y control de ejecución
        # ---------------------------------------------------------
        self.active_cb = QCheckBox('Tarea activa', self)
        self.active_cb.setChecked(bool(v.get('active', True)))
        form.addRow('', self.active_cb)

        self.run_missed_cb = QCheckBox(
            'Ejecutar tareas vencidas al iniciar la app',
            self
        )
        self.run_missed_cb.setChecked(
            bool(v.get('run_missed_on_start', False))
        )
        form.addRow('', self.run_missed_cb)

        self.max_runs_sb = QSpinBox(self)
        self.max_runs_sb.setRange(0, 100000)
        self.max_runs_sb.setValue(
            int(v.get('max_runs', 0) or 0)
        )
        form.addRow(
            'Límite de repeticiones (0 = ilimitado):',
            self.max_runs_sb
        )

        # ---------------------------------------------------------
        # Modo de planificación
        # ---------------------------------------------------------
        self.mode_combo = QtWidgets.QComboBox(self)
        self.mode_combo.addItems([
            'Cada intervalo',
            'A una hora diaria',
            'Una sola vez (fecha y hora)',
            'Semanal por días'
        ])

        mode = v.get('mode', 'Cada intervalo')
        try:
            self.mode_combo.setCurrentIndex(
                [
                    'Cada intervalo',
                    'A una hora diaria',
                    'Una sola vez (fecha y hora)',
                    'Semanal por días'
                ].index(mode)
            )
        except ValueError:
            pass

        form.addRow('Modo:', self.mode_combo)

        # ---------------------------------------------------------
        # Stacked widget por modo
        # ---------------------------------------------------------
        self.stack = QtWidgets.QStackedWidget(self)

        # === Intervalo ===
        w_int = QWidget(self)
        h_int = QHBoxLayout(w_int)
        h_int.setContentsMargins(0, 0, 0, 0)

        self.int_value = QSpinBox(self)
        self.int_value.setRange(1, 1000000)

        self.int_unit = QtWidgets.QComboBox(self)
        self.int_unit.addItems(['segundos', 'minutos', 'horas'])

        interval_sec = int(
            v.get('interval_seconds', 600) or 600
        )
        if interval_sec % 3600 == 0:
            self.int_value.setValue(interval_sec // 3600)
            self.int_unit.setCurrentIndex(2)
        elif interval_sec % 60 == 0:
            self.int_value.setValue(interval_sec // 60)
            self.int_unit.setCurrentIndex(1)
        else:
            self.int_value.setValue(interval_sec)
            self.int_unit.setCurrentIndex(0)

        h_int.addWidget(self.int_value)
        h_int.addWidget(self.int_unit)
        self.stack.addWidget(w_int)

        # === Diario ===
        w_daily = QWidget(self)
        h_d = QHBoxLayout(w_daily)
        h_d.setContentsMargins(0, 0, 0, 0)

        self.time_daily = QtWidgets.QTimeEdit(self)
        self.time_daily.setDisplayFormat('HH:mm')
        try:
            hh, mm = map(
                int,
                (v.get('daily_time', '08:00') or '08:00').split(':')[:2]
            )
            self.time_daily.setTime(
                QtCore.QTime(hh, mm)
            )
        except Exception:
            self.time_daily.setTime(QtCore.QTime(8, 0))

        h_d.addWidget(QLabel('Hora:'))
        h_d.addWidget(self.time_daily)
        self.stack.addWidget(w_daily)

        # === Una sola vez ===
        w_once = QWidget(self)
        h_o = QHBoxLayout(w_once)
        h_o.setContentsMargins(0, 0, 0, 0)

        self.dt_once = QtWidgets.QDateTimeEdit(self)
        self.dt_once.setCalendarPopup(True)
        try:
            ts = v.get('once_iso', '')
            if ts:
                self.dt_once.setDateTime(
                    QtCore.QDateTime.fromString(
                        ts, QtCore.Qt.ISODate
                    )
                )
            else:
                self.dt_once.setDateTime(
                    QtCore.QDateTime.currentDateTime()
                )
        except Exception:
            self.dt_once.setDateTime(
                QtCore.QDateTime.currentDateTime()
            )

        h_o.addWidget(self.dt_once)
        self.stack.addWidget(w_once)

        # === Semanal ===
        w_week = QWidget(self)
        lay_w = QtWidgets.QVBoxLayout(w_week)
        lay_w.setContentsMargins(0, 0, 0, 0)

        row_w = QWidget(self)
        hw = QHBoxLayout(row_w)
        hw.setContentsMargins(0, 0, 0, 0)

        hw.addWidget(QLabel('Hora:'))
        self.time_week = QtWidgets.QTimeEdit(self)
        self.time_week.setDisplayFormat('HH:mm')
        try:
            hh, mm = map(
                int,
                (v.get('weekly_time', '08:00') or '08:00').split(':')[:2]
            )
            self.time_week.setTime(
                QtCore.QTime(hh, mm)
            )
        except Exception:
            self.time_week.setTime(QtCore.QTime(8, 0))

        hw.addWidget(self.time_week)
        lay_w.addWidget(row_w)

        self.week_cbs = []
        names = ['L', 'M', 'X', 'J', 'V', 'S', 'D']
        row_days = QWidget(self)
        hd = QHBoxLayout(row_days)
        hd.setContentsMargins(0, 0, 0, 0)

        sel_days = v.get('weekdays', [])
        for i, n in enumerate(names):
            cb = QCheckBox(n, self)
            cb.setChecked(i in sel_days)
            self.week_cbs.append(cb)
            hd.addWidget(cb)

        lay_w.addWidget(row_days)
        self.stack.addWidget(w_week)

        form.addRow('Detalles:', self.stack)

        self.mode_combo.currentIndexChanged.connect(
            self.stack.setCurrentIndex
        )
        self.stack.setCurrentIndex(
            self.mode_combo.currentIndex()
        )

        # ---------------------------------------------------------
        # Botonera estándar + ayuda
        # ---------------------------------------------------------
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok |
            QtWidgets.QDialogButtonBox.Cancel,
            self
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        self._install_help_button(btns)
        form.addRow(btns)

    def result_task(self):
        """
        Devuelve el diccionario completo de la tarea configurada.

        Returns:
            dict: Definición completa de la tarea.
        """
        mode = self.mode_combo.currentText()

        d = {
            'name': self.name_edit.text().strip(),
            'script': self.path_edit.text().strip(),
            'args': self.args_edit.text().strip(),
            'wait': bool(self.wait_cb.isChecked()),
            'timeout': int(self.timeout_sb.value()),
            'hidden': bool(self.hidden_cb.isChecked()),
            'active': bool(self.active_cb.isChecked()),
            'run_missed_on_start': bool(
                self.run_missed_cb.isChecked()
            ),
            'max_runs': int(self.max_runs_sb.value()),
            'mode': mode,
            'runs_done': int(0),
            'last_run_ts': float(0),
        }

        if mode == 'Cada intervalo':
            mult = [1, 60, 3600][
                self.int_unit.currentIndex()
            ]
            d['interval_seconds'] = (
                int(self.int_value.value()) * mult
            )
        elif mode == 'A una hora diaria':
            t = self.time_daily.time()
            d['daily_time'] = (
                f"{t.hour():02d}:{t.minute():02d}"
            )
        elif mode == 'Una sola vez (fecha y hora)':
            d['once_iso'] = (
                self.dt_once.dateTime()
                .toString(QtCore.Qt.ISODate)
            )
        else:
            t = self.time_week.time()
            d['weekly_time'] = (
                f"{t.hour():02d}:{t.minute():02d}"
            )
            days = [
                i for i, cb in enumerate(self.week_cbs)
                if cb.isChecked()
            ]
            d['weekdays'] = days

        return d

