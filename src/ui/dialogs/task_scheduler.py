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
ui.dialogs.task_scheduler

Diálogo de gestión de tareas programadas.

Este módulo implementa el diálogo gráfico que permite:
- Listar tareas programadas.
- Añadir, editar y eliminar tareas.
- Ejecutar una tarea manualmente (modo “play”).
- Visualizar programación, próximo lanzamiento y estado.

IMPORTANT:
- Este diálogo NO guarda configuración en disco.
- Devuelve la lista de tareas al cerrarse.
- La ejecución real se delega dinámicamente a MainWindow.
"""

# ------------------------------------------------------------
# ui/dialogs/task_scheduler.py -> Clase TaskSchedulerDialog
# ------------------------------------------------------------

from PySide6 import QtCore, QtGui, QtWidgets

from PySide6.QtWidgets import (
    QLineEdit, QCheckBox, QLabel, QPushButton,
    QComboBox, QSpinBox, QDialog, QWidget,
    QDialogButtonBox, QMessageBox
)

from ui.helpers import HelpableDialogMixin
from core.scheduler import TaskScheduler
from ui.roles import ROLE_PATH
from ui.dialogs.task_editor import TaskEditorDialog


class TaskSchedulerDialog(HelpableDialogMixin, QDialog):
    """
    Gestor de tareas programadas.

    Permite al usuario:
    - Gestionar (crear, editar, eliminar) tareas programadas.
    - Ver de forma resumida su planificación y próximo disparo.
    - Ejecutar manualmente una tarea puntual.
    """

    #: Tópico de ayuda contextual
    help_topic = 'task_scheduler'

    def __init__(self, cfg, parent=None):
        """
        Inicializa el diálogo del programador de tareas.

        Args:
            cfg: Diccionario de configuración de la aplicación.
            parent: Widget padre (normalmente MainWindow).
        """
        super().__init__(parent)
        self.setWindowTitle('Programador de tareas')

        # --- Tamaño inicial del diálogo ---
        self.adjustSize()
        w = self.width()
        h = self.height()
        # Escalado intencional para permitir vista cómoda del listado
        self.resize(w * 8, h * 10)

        self.cfg = cfg
        self.tasks = list(cfg.get('scheduled_tasks') or [])

        lay = QtWidgets.QVBoxLayout(self)

        # --------------------------------------------------
        # Barra superior de acciones
        # --------------------------------------------------
        top = QWidget(self)
        hb = QtWidgets.QHBoxLayout(top)
        hb.setContentsMargins(0, 0, 0, 0)

        self.btn_add = QPushButton('Añadir', top)
        self.btn_edit = QPushButton('Editar…', top)
        self.btn_del = QPushButton('Eliminar', top)
        self.btn_play = QPushButton('▶ Ejecutar ahora', top)

        hb.addWidget(self.btn_add)
        hb.addWidget(self.btn_edit)
        hb.addWidget(self.btn_del)
        hb.addStretch(1)
        hb.addWidget(self.btn_play)

        lay.addWidget(top)

        # --------------------------------------------------
        # Lista de tareas programadas
        # --------------------------------------------------
        self.list = QtWidgets.QTreeWidget(self)
        self.list.setHeaderLabels([
            'Nombre',
            'Tipo',
            'Programación',
            'Próxima',
            'Activo',
            'Vencida al iniciar'
        ])
        self.list.setColumnWidth(0, 200)
        self.list.setSelectionMode(
            QtWidgets.QAbstractItemView.SingleSelection
        )
        lay.addWidget(self.list, 1)

        # --------------------------------------------------
        # Botonera inferior
        # --------------------------------------------------
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok
            | QtWidgets.QDialogButtonBox.Cancel,
            self
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        self._install_help_button(btns)
        lay.addWidget(btns)

        # --------------------------------------------------
        # Señales
        # --------------------------------------------------
        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_del.clicked.connect(self._on_del)
        self.btn_play.clicked.connect(self._on_play)

        self._rebuild()

    def _format_sched(self, t: dict):
        """
        Devuelve una descripción legible de la programación de una tarea.

        Args:
            t: Diccionario de definición de la tarea.

        Returns:
            Cadena descriptiva de la planificación.
        """
        m = t.get('mode', '')

        if m == 'Cada intervalo':
            s = int(t.get('interval_seconds', 0) or 0)
            if s % 3600 == 0:
                return f"Cada {s // 3600} h"
            if s % 60 == 0:
                return f"Cada {s // 60} min"
            return f"Cada {s} s"

        if m == 'A una hora diaria':
            return f"Diaria a las {t.get('daily_time', '--:--')}"

        if m == 'Una sola vez (fecha y hora)':
            return f"Una vez: {t.get('once_iso', '')}"

        if m == 'Semanal por días':
            days = t.get('weekdays', [])
            names = ['L', 'M', 'X', 'J', 'V', 'S', 'D']
            sel = ''.join(names[i] for i in days) or '(sin días)'
            return f"Semanal {sel} a {t.get('weekly_time', '--:--')}"

        return ''

    def _compute_next(self, t: dict):
        """
        Calcula la próxima ejecución prevista de una tarea.

        Args:
            t: Diccionario de definición de la tarea.

        Returns:
            Objeto datetime con la próxima ejecución o None.
        """
        from datetime import datetime, timedelta

        now = datetime.now()
        m = t.get('mode', '')

        if m == 'Cada intervalo':
            sec = int(t.get('interval_seconds', 600) or 600)
            last = t.get('last_run_ts', 0) or 0

            if last <= 0:
                return now + timedelta(seconds=sec)

            nr = datetime.fromtimestamp(last) + timedelta(seconds=sec)
            while nr < now:
                nr += timedelta(seconds=sec)
            return nr

        if m == 'A una hora diaria':
            hh, mm = map(
                int,
                (t.get('daily_time', '08:00') or '08:00').split(':')[:2]
            )
            cand = now.replace(
                hour=hh, minute=mm, second=0, microsecond=0
            )
            if cand <= now:
                cand = cand + timedelta(days=1)
            return cand

        if m == 'Una sola vez (fecha y hora)':
            try:
                dt = datetime.fromisoformat(
                    (t.get('once_iso') or '').replace('Z', '')
                )
                return dt
            except Exception:
                return None

        if m == 'Semanal por días':
            hh, mm = map(
                int,
                (t.get('weekly_time', '08:00') or '08:00').split(':')[:2]
            )
            days = t.get('weekdays', []) or []
            if not days:
                return None

            for add in range(0, 8):
                cand = now + timedelta(days=add)
                dow = cand.weekday()  # 0=Lunes..6=Domingo
                if dow in days:
                    c = cand.replace(
                        hour=hh, minute=mm, second=0, microsecond=0
                    )
                    if c > now:
                        return c
            return None

        return None

    def _rebuild(self):
        """
        Reconstruye completamente la lista de tareas en la UI.
        """
        self.list.clear()

        for t in self.tasks:
            name = (
                t.get('name')
                or Path(t.get('script', '')).name
                or '(sin nombre)'
            )
            tipo = t.get('mode', '')
            prog = self._format_sched(t)
            nxt = self._compute_next(t)
            nxt_s = nxt.strftime('%Y-%m-%d %H:%M') if nxt else '-'

            it = QtWidgets.QTreeWidgetItem([
                name,
                tipo,
                prog,
                nxt_s,
                'Sí' if t.get('active', True) else 'No',
                'Sí' if t.get('run_missed_on_start', False) else 'No'
            ])
            it.setData(0, ROLE_PATH, t)

            self.list.addTopLevelItem(it)

        if self.list.topLevelItemCount() > 0:
            self.list.setCurrentItem(self.list.topLevelItem(0))

    def _selected_index(self):
        """
        Devuelve el índice de la tarea seleccionada.

        Returns:
            Índice entero o -1 si no hay selección.
        """
        it = self.list.currentItem()
        if not it:
            return -1
        return self.list.indexOfTopLevelItem(it)

    def _on_add(self):
        """
        Acción: añadir una nueva tarea.
        """
        dlg = TaskEditorDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.tasks.append(dlg.result_task())
            self._rebuild()

    def _on_edit(self):
        """
        Acción: editar la tarea seleccionada.
        """
        i = self._selected_index()
        if i < 0:
            return
        dlg = TaskEditorDialog(self, values=self.tasks[i])
        if dlg.exec() == QDialog.Accepted:
            self.tasks[i] = dlg.result_task()
            self._rebuild()

    def _on_del(self):
        """
        Acción: eliminar la tarea seleccionada.
        """
        i = self._selected_index()
        if i < 0:
            return
        del self.tasks[i]
        self._rebuild()

    def _on_play(self):
        """
        Ejecuta inmediatamente la tarea seleccionada.

        NOTE:
            La ejecución se realiza delegando en MainWindow._run_script,
            buscándolo dinámicamente en la jerarquía de padres.
        """
        i = self._selected_index()
        if i < 0:
            return

        t = self.tasks[i]

        # Localizar MainWindow con capacidad de ejecución
        mw = self.parent() or self.parentWidget()
        while mw is not None and not hasattr(mw, '_run_script'):
            mw = mw.parent()

        if mw is not None:
            ok, out = mw._run_script(
                t.get('script', ''),
                t.get('args', ''),
                bool(t.get('wait', True)),
                int(t.get('timeout', 0) or 0),
                bool(t.get('hidden', True))
            )
            try:
                LOGGER.info(
                    "[task] '%s' -> ok=%s msg=%s",
                    t.get('name') or t.get('script'),
                    ok,
                    (out or '')[:2000]
                )
            except Exception:
                pass

            QtWidgets.QMessageBox.information(
                self,
                'Tarea',
                'Ejecutada' if ok else f'Error: {out}'
            )
        else:
            QtWidgets.QMessageBox.information(
                self,
                'Tarea',
                'No se pudo localizar el contexto para ejecutar el script'
            )

    def result_tasks(self):
        """
        Devuelve la lista final de tareas programadas.

        Returns:
            Lista de diccionarios de tareas.
        """
        return self.tasks