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
core.scripts

Ejecución de scripts y comandos externos (enfoque Windows‑first).

Este módulo centraliza toda la lógica necesaria para:
- Ejecutar scripts y ejecutables externos de forma robusta.
- Tratar correctamente argumentos en sistemas Windows.
- Soportar múltiples tipos de script (.bat, .cmd, .ps1, .py, .vbs, .exe, etc.).

IMPORTANTE:
- La prioridad es la fiabilidad antes que la verbosidad.
- Los errores NO deben romper la aplicación principal.
- Los mensajes de salida se limitan en tamaño deliberadamente.
"""

import shlex
import os
import subprocess
import sys
from pathlib import Path
from typing import Tuple

from logutils.setup import get_logger

LOGGER = get_logger()


def run_script(
    script_path: str,
    args: str = "",
    wait: bool = True,
    timeout_sec: int = 0,
    run_hidden: bool = True,
) -> Tuple[bool, str]:
    """
    Ejecuta un script o ejecutable externo con tratamiento correcto
    de argumentos en Windows.

    Soporta distintos tipos de archivo:
    - .vbs / .vb (wscript)
    - .bat / .cmd (cmd.exe)
    - .ps1 (PowerShell / pwsh)
    - .py  (Python)
    - .exe / .com y otros binarios

    Args:
        script_path: Ruta al script o ejecutable.
        args: Cadena de argumentos.
        wait: Si True, espera a que el proceso finalice.
        timeout_sec: Tiempo máximo de espera en segundos (0 = sin límite).
        run_hidden: Ejecutar sin mostrar ventana en Windows.

    Returns:
        Tupla (ok, mensaje):
        - ok: True si la ejecución fue correcta.
        - mensaje: salida estándar o mensaje de error (limitado en tamaño).

    WARNING:
        - Esta función está pensada para ser robusta, no estricta.
        - Fallos en scripts deben reflejarse en el resultado,
          pero NO causar excepciones no controladas.
    """

    script_path = (script_path or "").strip()
    if not script_path:
        # Ejecutar “nada” se considera éxito silencioso
        return True, ""

    sp = Path(script_path)
    if not sp.exists():
        return False, f"No existe: {sp}"

    # Normalizar argumentos según reglas Windows
    try:
        argv = clean_and_split_args_windows(args or "")
    except Exception:
        # Fallback defensivo extremadamente simple
        argv = [(args or "").replace(r'\"', '"')]

    ext = sp.suffix.lower()

    try:
        # ------------------------------------------------------------
        # Ejecución en Windows (caso principal)
        # ------------------------------------------------------------
        if os.name == "nt":
            CREATE_NO_WINDOW = 0x08000000
            creationflags = CREATE_NO_WINDOW if run_hidden else 0

            # Construcción del comando según extensión
            if ext in (".vbs", ".vb"):
                # Scripts VBScript: siempre mediante wscript
                wroot = os.environ.get("SystemRoot", r"C:\Windows")
                wscript = os.path.join(wroot, "System32", "wscript.exe")
                cmd = [wscript, os.fspath(sp), *argv]

            elif ext in (".bat", ".cmd"):
                # Scripts de consola clásicos
                cmd = [
                    os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe"),
                    "/C",
                    os.fspath(sp),
                    *argv,
                ]

            elif ext == ".ps1":
                # PowerShell (prioriza pwsh si existe)
                pwsh = r"C:\Program Files\PowerShell\7\pwsh.exe"
                if os.path.exists(pwsh):
                    cmd = [pwsh, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.fspath(sp), *argv]
                else:
                    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", os.fspath(sp), *argv]

            elif ext == ".py":
                # Scripts Python usando el intérprete actual
                python = sys.executable or "python.exe"
                cmd = [python, os.fspath(sp), *argv]

            else:
                # Ejecutables nativos (.exe, .com, etc.)
                cmd = [os.fspath(sp), *argv]

            LOGGER.info("Ejecutando: %s", cmd)

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creationflags,
            )

            if not wait:
                return True, ""

            try:
                rc = proc.wait(timeout=timeout_sec if timeout_sec > 0 else None)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, err = proc.communicate()
                msg = (err or out or b"").decode("utf-8", errors="ignore")
                return False, f"Timeout tras {timeout_sec}s. {msg[:2000]}"

            out, err = proc.communicate()
            msg = (err or out or b"").decode("utf-8", errors="ignore")
            return rc == 0, msg[:2000]

        # ------------------------------------------------------------
        # Otros sistemas (soporte mínimo)
        # ------------------------------------------------------------
        cmd = [os.fspath(sp), *argv]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        if not wait:
            return True, ""

        rc = proc.wait(timeout=timeout_sec if timeout_sec > 0 else None)
        out, err = proc.communicate()
        msg = (err or out or b"").decode("utf-8", errors="ignore")
        return rc == 0, msg[:2000]

    except Exception as e:
        # Fallback defensivo final
        return False, str(e)


# ---------------------------------------------------------------------------
# Helpers de argumentos (Windows)
# ---------------------------------------------------------------------------

def clean_and_split_args_windows(arg_str: str) -> list[str]:
    r"""
    Normaliza una cadena de argumentos pensada para Windows.

    Este método:
    - Desescapa comillas procedentes de JSON o entradas manuales.
    - Divide argumentos usando reglas de Windows (posix=False).
    - Elimina comillas exteriores de cada token.
    - Conserva backslashes de rutas Windows y UNC sin tocarlos.

    Args:
        arg_str: Cadena de argumentos original.

    Returns:
        Lista de argumentos normalizados como strings.

    IMPORTANT:
        El tratamiento de argumentos en Windows es NOTORIAMENTE complejo.
        Este método existe para minimizar errores comunes de quoting.
    """
    if not arg_str:
        return []

    s = str(arg_str)

    # 1) Desescapar comillas comunes (JSON / edición manual)
    s = s.replace('\"', '"').replace('\\"', '"')

    try:
        parts = shlex.split(s, posix=False)
    except Exception:
        # Fallback extremadamente tolerante
        parts = [s]

    # 2) Quitar solo comillas exteriores
    out: list[str] = []
    for p in parts:
        if len(p) >= 2 and (
            (p[0] == '"' and p[-1] == '"') or
            (p[0] == "'" and p[-1] == "'")
        ):
            p = p[1:-1]

        # Limpieza adicional residual
        p = p.replace('\"', '"').replace('\\"', '"')
        out.append(p)

    return out


def clean_and_split_args_windows_old(arg_str: str) -> list[str]:
    """
    Versión anterior del normalizador de argumentos para Windows.

    Se conserva por:
    - Compatibilidad.
    - Posibles comparativas o regresiones.

    NOTE:
        NO se utiliza actualmente por defecto.
        Puede eliminarse en el futuro si ya no es necesario.
    """
    if not arg_str:
        return []

    s = str(arg_str)
    s = s.replace('\"', '"').replace('\\"', '"')

    try:
        parts = shlex.split(s, posix=False)
    except Exception:
        parts = [s]

    out: list[str] = []
    for p in parts:
        if len(p) >= 2 and (
            (p[0] == '"' and p[-1] == '"') or
            (p[0] == "'" and p[-1] == "'")
        ):
            p = p[1:-1]

        p = p.replace('\"', '"').replace('\\"', '"')
        out.append(p)

    return out
