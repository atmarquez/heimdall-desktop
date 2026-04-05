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
Pestaña de configuración de Scripts y tareas programadas.

Este módulo define la clase `ScriptConfigTab`, correspondiente a la
pestaña “Scripts” del diálogo de Configuración.

Responsabilidades:
- Configuración del script de inicio de la aplicación.
- Configuración del script de salida de la aplicación.
- Acceso al programador de tareas integrado.

IMPORTANT:
    Esta pestaña no ejecuta scripts ni tareas directamente.
    Solo gestiona su configuración, que es utilizada por otros
    componentes de la aplicación (AppController, TaskScheduler).
"""

from PySide6 import QtWidgets, QtCore
from PySide6.QtWidgets import (
    QWidget, QLabel, QPushButton,
    QCheckBox, QFormLayout, QHBoxLayout
)

from ui.dialogs.script_config import ScriptConfigDialog
from ui.dialogs.task_scheduler import TaskSchedulerDialog


class ScriptConfigTab(QtWidgets.QWidget):
    """
    Pestaña “Scripts” dentro del diálogo de Configuración.

    Permite al usuario:
    - Definir un script de inicio.
    - Definir un script de salida.
    - Habilitar o deshabilitar dichos scripts.
    - Acceder al programador de tareas.

    NOTE:
        Esta clase trabaja exclusivamente con configuración.
        La ejecución real se delega a otros módulos.
    """

    def __init__(self, cfg: dict, parent=None):
        """
        Inicializa la pestaña de Scripts.

        Args:
            cfg (dict):
                Diccionario de configuración actual.
            parent (QWidget, optional):
                Widget padre.
        """
        super().__init__(parent)
        self.cfg = cfg

        # ---------------------------------------------------------
        # Configuración interna (no escrita directamente en cfg)
        # ---------------------------------------------------------
        self._pre_cfg = {}
        self._post_cfg = {}

        self._build_ui()
        self.populate_from_cfg()

    def _build_ui(self):
        """
        Construye los elementos visuales de la pestaña.
        """
        layout = QFormLayout(self)

        # ---------------------------------------------------------
        # Scripts de inicio
        # ---------------------------------------------------------
        self.pre_summary = QLabel('', self)

        btn_cfg_pre = QPushButton(
            'Configurar script de inicio…',
            self
        )
        btn_cfg_pre.clicked.connect(
            self._open_pre_script_dialog
        )

        wpre = QWidget(self)
        lpre = QHBoxLayout(wpre)
        lpre.setContentsMargins(0, 0, 0, 0)
        lpre.addWidget(self.pre_summary, 1)
        lpre.addWidget(btn_cfg_pre)

        layout.addRow('Script al iniciar:', wpre)

        self.pre_enabled_cb = QCheckBox(
            'Habilitar script de inicio',
            self
        )
        layout.addRow('', self.pre_enabled_cb)

        # ---------------------------------------------------------
        # Scripts de salida
        # ---------------------------------------------------------
        self.post_summary = QLabel('', self)

        btn_cfg_post = QPushButton(
            'Configurar script de salida…',
            self
        )
        btn_cfg_post.clicked.connect(
            self._open_post_script_dialog
        )

        wpost = QWidget(self)
        lpost = QHBoxLayout(wpost)
        lpost.setContentsMargins(0, 0, 0, 0)
        lpost.addWidget(self.post_summary, 1)
        lpost.addWidget(btn_cfg_post)

        layout.addRow('Script al salir:', wpost)

        self.post_enabled_cb = QCheckBox(
            'Habilitar script de salida',
            self
        )
        layout.addRow('', self.post_enabled_cb)

        # ---------------------------------------------------------
        # Programador de tareas
        # ---------------------------------------------------------
        self.tasks_summary = QLabel('', self)

        btn_sched = QPushButton(
            'Programador de tareas…',
            self
        )
        btn_sched.clicked.connect(
            self._open_task_scheduler_dialog
        )

        wts = QWidget(self)
        lts = QHBoxLayout(wts)
        lts.setContentsMargins(0, 0, 0, 0)
        lts.addWidget(self.tasks_summary, 1)
        lts.addWidget(btn_sched)

        layout.addRow('Tareas programadas:', wts)

    def _script_summary_text(self, d: dict) -> str:
        """
        Genera un texto resumen legible de la configuración de un script.

        Args:
            d (dict):
                Diccionario con la configuración del script.

        Returns:
            str: Resumen descriptivo.
        """
        script = d.get('script') or '(ninguno)'
        args = d.get('args') or ''
        wait = 'sí' if d.get('wait', True) else 'no'
        timeout = int(d.get('timeout', 0) or 0)
        hidden = 'sí' if d.get('hidden', True) else 'no'

        base = f'{script} {args}'.strip()
        extra = (
            f' | esperar: {wait}; '
            f'timeout: {timeout}s; '
            f'oculto: {hidden}'
        )
        return base + extra

    def populate_from_cfg(self):
        """
        Carga los valores desde la configuración actual (`cfg`)
        hacia el estado interno y la interfaz.
        """
        self._pre_cfg = {
            'script': self.cfg.get('pre_start_script', ''),
            'args': self.cfg.get('pre_start_args', ''),
            'wait': bool(self.cfg.get('pre_start_wait', True)),
            'timeout': int(
                self.cfg.get('pre_start_timeout_sec', 20) or 0
            ),
            'hidden': bool(
                self.cfg.get('pre_start_run_hidden', True)
            ),
        }

        self._post_cfg = {
            'script': self.cfg.get('post_exit_script', ''),
            'args': self.cfg.get('post_exit_args', ''),
            'wait': bool(self.cfg.get('post_exit_wait', True)),
            'timeout': int(
                self.cfg.get('post_exit_timeout_sec', 20) or 0
            ),
            'hidden': bool(
                self.cfg.get('post_exit_run_hidden', True)
            ),
        }

        self.pre_enabled_cb.setChecked(
            bool(self.cfg.get('pre_start_script_enabled', False))
        )
        self.post_enabled_cb.setChecked(
            bool(self.cfg.get('post_exit_script_enabled', False))
        )

        self.pre_summary.setText(
            self._script_summary_text(self._pre_cfg)
        )
        self.post_summary.setText(
            self._script_summary_text(self._post_cfg)
        )

        self._update_tasks_summary()

    def apply_to_cfg(self, cfg: dict):
        """
        Aplica los valores actuales de la pestaña al diccionario de configuración.

        Args:
            cfg (dict):
                Diccionario de configuración a actualizar.

        Returns:
            dict: Configuración resultante.
        """
        cfg['pre_start_script_enabled'] = bool(
            self.pre_enabled_cb.isChecked()
        )
        cfg['post_exit_script_enabled'] = bool(
            self.post_enabled_cb.isChecked()
        )

        cfg['pre_start_script'] = self._pre_cfg.get('script', '')
        cfg['pre_start_args'] = self._pre_cfg.get('args', '')
        cfg['pre_start_wait'] = bool(self._pre_cfg.get('wait', True))
        cfg['pre_start_timeout_sec'] = int(
            self._pre_cfg.get('timeout', 0) or 0
        )
        cfg['pre_start_run_hidden'] = bool(
            self._pre_cfg.get('hidden', True)
        )

        cfg['post_exit_script'] = self._post_cfg.get('script', '')
        cfg['post_exit_args'] = self._post_cfg.get('args', '')
        cfg['post_exit_wait'] = bool(
            self._post_cfg.get('wait', True)
        )
        cfg['post_exit_timeout_sec'] = int(
            self._post_cfg.get('timeout', 0) or 0
        )
        cfg['post_exit_run_hidden'] = bool(
            self._post_cfg.get('hidden', True)
        )

        return cfg

    def _open_pre_script_dialog(self):
        """
        Abre el diálogo de configuración del script de inicio.
        """
        dlg = ScriptConfigDialog(
            self,
            'Script al iniciar',
            values=self._pre_cfg
        )
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self._pre_cfg = dlg.result_values()
            self.pre_summary.setText(
                self._script_summary_text(self._pre_cfg)
            )

    def _open_post_script_dialog(self):
        """
        Abre el diálogo de configuración del script de salida.
        """
        dlg = ScriptConfigDialog(
            self,
            'Script al salir',
            values=self._post_cfg
        )
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self._post_cfg = dlg.result_values()
            self.post_summary.setText(
                self._script_summary_text(self._post_cfg)
            )

    def _open_task_scheduler_dialog(self):
        """
        Abre el diálogo del programador de tareas.
        """
        dlg = TaskSchedulerDialog(self.cfg, self)
        if dlg.exec() == QtWidgets.QDialog.Accepted:
            self.cfg['scheduled_tasks'] = dlg.result_tasks()
            self._update_tasks_summary()

    def _update_tasks_summary(self):
        """
        Actualiza el resumen visual del número de tareas programadas.
        """
        try:
            tasks = self.cfg.get('scheduled_tasks') or []
            n = len(tasks)
            self.tasks_summary.setText(
                f"{n} tarea(s) definida(s)"
            )
        except Exception:
            # Código defensivo: no romper UI por errores de cfg
            self.tasks_summary.setText('')