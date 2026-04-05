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
core.scheduler

Programador de tareas para Heimdall Desktop.

Este módulo implementa un sistema de planificación de tareas que:
- Es completamente independiente de la interfaz gráfica.
- No depende directamente de Qt ni de temporizadores concretos.
- Se integra mediante callbacks proporcionados por la UI o el controlador.

Soporta distintos modos de ejecución:
- Cada intervalo.
- A una hora diaria.
- Ejecución única (fecha y hora).
- Ejecución semanal por días.

IMPORTANTE:
- Este módulo está diseñado para ser tolereante a errores:
  los fallos NO deben romper la aplicación.
- El almacenamiento del estado depende del diccionario de configuración.
"""

import time
import datetime
from typing import Callable, List, Dict, Any


class TaskScheduler:
    """
    Programador de tareas independiente de la UI.

    Características clave:
    - No depende de Qt directamente.
    - Funciona mediante callbacks inyectados.
    - Persiste su estado dentro de la configuración de la aplicación.

    El scheduler NO ejecuta comandos directamente:
    delega esa responsabilidad al callback `run_script_cb`.
    """

    def __init__(
        self,
        cfg: dict,
        run_script_cb: Callable[..., tuple],
        save_cfg_cb: Callable[[dict], None],
        timer_factory: Callable[[Callable[[], None]], Any],
    ):
        """
        Inicializa el programador de tareas.

        Args:
            cfg: Diccionario de configuración compartido de la aplicación.
            run_script_cb: Callback para ejecutar scripts
                (por ejemplo, MainWindow._run_script).
            save_cfg_cb: Callback para guardar la configuración persistente.
            timer_factory: Función que recibe un callback y devuelve un temporizador
                configurado y ya iniciado.
        """
        self.cfg = cfg
        self._run_script = run_script_cb
        self._save_cfg = save_cfg_cb

        # Timer periódico: revisa tareas vencidas (por defecto cada ~30s,
        # dependiendo de la implementación del timer_factory).
        self._timer = timer_factory(self._check_and_run_due_tasks)

        # Timer de arranque: gestiona tareas vencidas al iniciar la app.
        # Se ejecuta una sola vez con ligero retardo para no bloquear el inicio.
        self._startup_timer = timer_factory(
            self._handle_overdue_on_start,
            single_shot=True,
            delay_ms=1000,
        )

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _now(self) -> datetime.datetime:
        """
        Devuelve la fecha y hora actuales.

        Se encapsula para facilitar pruebas o cambios futuros.
        """
        return datetime.datetime.now()

    def _task_list(self) -> List[Dict]:
        """
        Obtiene la lista de tareas programadas desde la configuración.

        Returns:
            Lista de diccionarios de tareas.
        """
        return list(self.cfg.get("scheduled_tasks") or [])

    def _save_task_list(self, tasks: List[Dict]) -> None:
        """
        Guarda la lista de tareas en la configuración persistente.

        Args:
            tasks: Lista de tareas actualizada.
        """
        self.cfg["scheduled_tasks"] = tasks
        self._save_cfg(self.cfg)

    # ------------------------------------------------------------------
    # Cálculo de próxima ejecución
    # ------------------------------------------------------------------

    def _compute_next_run(self, t: Dict) -> float:
        """
        Calcula la siguiente fecha de ejecución de una tarea.

        Args:
            t: Diccionario que describe la tarea.

        Returns:
            Timestamp UNIX de la próxima ejecución,
            o 0.0 si no se puede calcular.
        """
        now = self._now()
        mode = t.get("mode", "")

        if mode == "Cada intervalo":
            sec = int(t.get("interval_seconds", 600) or 600)
            last = float(t.get("last_run_ts", 0) or 0)

            if last <= 0:
                return (now + datetime.timedelta(seconds=sec)).timestamp()

            nr = datetime.datetime.fromtimestamp(last) + datetime.timedelta(seconds=sec)
            while nr < now:
                nr += datetime.timedelta(seconds=sec)

            return nr.timestamp()

        if mode == "A una hora diaria":
            try:
                hh, mm = map(
                    int,
                    (t.get("daily_time", "08:00") or "08:00").split(":")[:2],
                )
            except Exception:
                # Valor por defecto defensivo
                hh, mm = (8, 0)

            cand = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if cand <= now:
                cand += datetime.timedelta(days=1)

            return cand.timestamp()

        if mode == "Una sola vez (fecha y hora)":
            try:
                iso = (t.get("once_iso") or "").replace("Z", "")
                dt = datetime.datetime.fromisoformat(iso)
                return dt.timestamp()
            except Exception:
                return 0.0

        if mode == "Semanal por días":
            try:
                hh, mm = map(
                    int,
                    (t.get("weekly_time", "08:00") or "08:00").split(":")[:2],
                )
            except Exception:
                hh, mm = (8, 0)

            days = t.get("weekdays", []) or []
            if not days:
                return 0.0

            for add in range(0, 8):
                cand = now + datetime.timedelta(days=add)
                if cand.weekday() in days:
                    c = cand.replace(hour=hh, minute=mm, second=0, microsecond=0)
                    if c > now:
                        return c.timestamp()

            return 0.0

        return 0.0

    def _is_due(self, t: Dict, when_ts: float) -> bool:
        """
        Determina si una tarea está vencida y debe ejecutarse.

        Args:
            t: Diccionario de la tarea.
            when_ts: Timestamp de referencia (normalmente ahora).

        Returns:
            True si la tarea debe ejecutarse, False en caso contrario.
        """
        if not t.get("active", True):
            return False

        max_runs = int(t.get("max_runs", 0) or 0)
        runs_done = int(t.get("runs_done", 0) or 0)

        if max_runs > 0 and runs_done >= max_runs:
            return False

        nr = float(t.get("next_run_ts", 0) or 0)
        if nr <= 0:
            nr = self._compute_next_run(t)
            t["next_run_ts"] = nr

        return nr > 0 and nr <= when_ts

    # ------------------------------------------------------------------
    # Ejecución de tareas
    # ------------------------------------------------------------------

    def _run_task_now(self, t: Dict) -> bool:
        """
        Ejecuta inmediatamente una tarea y actualiza su estado.

        Args:
            t: Diccionario de la tarea.

        Returns:
            True si la ejecución fue correcta, False en caso contrario.
        """
        ok, _ = self._run_script(
            script_path=t.get("script", ""),
            args=t.get("args", ""),
            wait=bool(t.get("wait", True)),
            timeout_sec=int(t.get("timeout", 0) or 0),
            run_hidden=bool(t.get("hidden", True)),
        )

        t["last_run_ts"] = time.time()
        t["runs_done"] = int(t.get("runs_done", 0) or 0) + 1
        t["next_run_ts"] = self._compute_next_run(t)

        return ok

    def _check_and_run_due_tasks(self) -> None:
        """
        Comprueba periódicamente si hay tareas vencidas y las ejecuta.

        Este método está diseñado para:
        - Fallar silenciosamente.
        - No romper el temporizador si ocurre un error.
        """
        try:
            now_ts = time.time()
            tasks = self._task_list()
            changed = False

            for t in tasks:
                if self._is_due(t, now_ts):
                    self._run_task_now(t)
                    changed = True

            if changed:
                self._save_task_list(tasks)

        except Exception:
            # WARNING: Nunca propagar excepciones desde el scheduler
            pass

    def _check_and_run_due_tasks_print(self) -> None:
        """
        Variante de depuración del scheduler.

        Muestra por consola el estado de las tareas y las ejecuciones.
        NO usar en producción salvo diagnóstico puntual.
        """
        try:
            now_ts = time.time()
            tasks = self._task_list()

            print("SCHEDULER tick:", time.strftime("%H:%M:%S"))
            print("Tasks:", len(tasks))

            for t in tasks:
                print(
                    "TASK",
                    t.get("name"),
                    "mode=", t.get("mode"),
                    "next=", t.get("next_run_ts"),
                    "interval=", t.get("interval_seconds"),
                    "active=", t.get("active"),
                )

            changed = False
            for t in tasks:
                if self._is_due(t, now_ts):
                    print("RUNNING:", t.get("name"))
                    self._run_task_now(t)
                    changed = True

            if changed:
                self._save_task_list(tasks)

        except Exception as e:
            print("SCHEDULER ERROR:", e)

    def _handle_overdue_on_start(self) -> None:
        """
        Gestiona tareas vencidas en el momento de arranque de la aplicación.

        Si una tarea está marcada para ejecutar al iniciar
        (`run_missed_on_start`), se evalúa y ejecuta si corresponde.
        """
        try:
            now_ts = time.time()
            tasks = self._task_list()
            changed = False

            for t in tasks:
                if not t.get("run_missed_on_start", False):
                    if not t.get("next_run_ts"):
                        t["next_run_ts"] = self._compute_next_run(t)
                    continue

                nr = float(t.get("next_run_ts", 0) or 0)
                if nr <= 0:
                    nr = self._compute_next_run(t)
                    t["next_run_ts"] = nr

                if nr > 0 and nr <= now_ts:
                    self._run_task_now(t)
                    changed = True

            if changed:
                self._save_task_list(tasks)

        except Exception:
            # Fallo silencioso intencionado
            pass