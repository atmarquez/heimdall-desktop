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
core.autostart

Gestión del auto-inicio de Heimdall Desktop en Windows.

Este módulo permite:
- Activar o desactivar el auto-inicio de la aplicación con Windows.
- Soportar dos mecanismos:
  - Registro (HKCU\\Run)
  - Carpeta Inicio (Startup)
- Detectar el estado actual del auto-inicio para diagnóstico.

IMPORTANTE:
- Este módulo es **ESPECÍFICO DE WINDOWS**.
- No debe usarse ni importarse en otros sistemas.
- Todo el código está diseñado para fallar de forma segura y controlada.
"""

from __future__ import annotations

import os
import sys
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Tuple

from config.service import get_cfg_service, app_dir


# ---------------------------------------------------------------------------
# Helpers generales
# ---------------------------------------------------------------------------

def _is_windows() -> bool:
    """
    Indica si el sistema operativo actual es Windows.

    Returns:
        True si se ejecuta en Windows, False en caso contrario.
    """
    return os.name == "nt"


# Nombre cacheado del valor de Registro / acceso directo
_def_autostart_value_name: Optional[str] = None


def _autostart_value_name() -> str:
    """
    Devuelve un nombre estable y seguro para identificar el auto-inicio.

    Este valor se usa como:
    - Nombre del valor en HKCU\\Run
    - Nombre base del acceso directo en la carpeta Inicio

    Se deriva del título de la aplicación y se sanea para cumplir
    las restricciones de Windows.

    Returns:
        Nombre seguro para usar en Registro y accesos directos.
    """
    global _def_autostart_value_name

    if _def_autostart_value_name:
        return _def_autostart_value_name

    try:
        title = (get_cfg_service().data.get("app_title") or "").strip()
    except Exception:
        # Fallback defensivo
        title = "Heimdall Desktop"

    # Caracteres inválidos para nombres de archivo/registro
    invalid = '<>:"/\\|?*' + "".join(chr(i) for i in range(32))
    safe = "".join(c for c in title if c not in invalid).strip()

    _def_autostart_value_name = safe or "HeimdallDesktop"
    return _def_autostart_value_name


def _exe_and_args_for_autostart(minimized: bool) -> Tuple[str, str, str, str]:
    """
    Determina ejecutable, argumentos y contexto para el auto-inicio.

    Tiene en cuenta:
    - Ejecución normal desde código fuente.
    - Ejecución empaquetada (PyInstaller).
    - Inicio minimizado si procede.

    Args:
        minimized: Si True, añade el argumento --minimized.

    Returns:
        Tupla con:
        (ejecutable, argumentos, directorio de trabajo, icono)
    """
    try:
        if getattr(sys, "frozen", False):
            # Ejecución como binario
            target = sys.executable
            args = "--minimized" if minimized else ""
            workdir = os.fspath(app_dir())
        else:
            # Ejecución desde código fuente
            target = sys.executable
            script = os.fspath(Path(__file__).resolve().parents[1] / "main.py")
            args = f'"{script}"' + (" --minimized" if minimized else "")
            workdir = os.fspath(Path(script).parent)

        icon = os.fspath(get_cfg_service().app_icon_path())
        return target, args, workdir, icon

    except Exception:
        # Fallback extremadamente defensivo
        return sys.executable, "", os.getcwd(), ""


def _startup_dir() -> Path:
    """
    Devuelve la ruta a la carpeta Inicio del usuario actual.

    Returns:
        Ruta a la carpeta Startup como Path.
    """
    appdata = os.environ.get("APPDATA")
    if not appdata:
        return Path.home()

    return (
        Path(appdata)
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )


# ---------------------------------------------------------------------------
# Creación de accesos directos (.lnk) vía VBS
# ---------------------------------------------------------------------------

def _create_lnk_via_vbs(
    lnk_path: str,
    target: str,
    args: str = "",
    workdir: str = "",
    icon: str = "",
) -> Tuple[bool, str]:
    """
    Crea un acceso directo (.lnk) usando cscript y VBScript.

    Se utiliza este método para:
    - Evitar dependencia de pywin32.
    - Funcionamiento estable en sistemas sin componentes COM expuestos a Python.

    Args:
        lnk_path: Ruta donde crear el .lnk.
        target: Ejecutable objetivo.
        args: Argumentos.
        workdir: Directorio de trabajo.
        icon: Ruta del icono.

    Returns:
        Tupla (ok, error).
    """

    def esc(s: str) -> str:
        # Escape básico para strings VBS
        return (s or "").replace('"', '""')

    vbs = (
        'Set WshShell = WScript.CreateObject("WScript.Shell")\n'
        f'Set lnk = WshShell.CreateShortcut("{esc(lnk_path)}")\n'
        f'lnk.TargetPath = "{esc(target)}"\n'
        f'lnk.Arguments = "{esc(args)}"\n'
        f'lnk.WorkingDirectory = "{esc(workdir)}"\n'
        f'lnk.IconLocation = "{esc(icon)}"\n'
        "lnk.Save\n"
    )

    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix=".vbs", text=True)
        os.close(fd)
        Path(tmp).write_text(vbs, encoding="utf-8")

        res = subprocess.run(
            ["cscript", "//nologo", tmp],
            capture_output=True,
            text=True,
        )

        if res.returncode != 0:
            return False, res.stderr or res.stdout

        return True, ""

    except Exception as e:
        return False, str(e)

    finally:
        # Limpieza obligatoria del archivo temporal
        try:
            if tmp and Path(tmp).exists():
                Path(tmp).unlink()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Detección del estado actual de auto-inicio
# ---------------------------------------------------------------------------

def _detect_registry_autostart_for_current_exe() -> bool:
    """
    Detecta si el ejecutable actual está registrado en HKCU\\Run.

    Returns:
        True si existe entrada de auto-inicio vía Registro.
    """
    if not _is_windows():
        return False

    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        exe = os.fspath(Path(sys.executable).resolve()).lower()

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            i = 0
            while True:
                try:
                    _, val, _ = winreg.EnumValue(key, i)
                    i += 1
                    if isinstance(val, str) and exe in val.lower():
                        return True
                except OSError:
                    break

    except Exception:
        pass

    return False


def _detect_startup_shortcut_for_current_exe() -> bool:
    """
    Detecta si existe un acceso directo de auto-inicio en la carpeta Startup.

    Returns:
        True si existe acceso directo válido.
    """
    if not _is_windows():
        return False

    try:
        from shell_utils import resolve_lnk

        exe = Path(sys.executable).resolve()
        sd = _startup_dir()

        if not sd.exists():
            return False

        for lnk in sd.glob("*.lnk"):
            try:
                info = resolve_lnk(os.fspath(lnk))
                tgt = (info or {}).get("target", "")
                if tgt and Path(tgt).resolve() == exe:
                    return True
            except Exception:
                continue

    except Exception:
        pass

    return False


def current_autostart_diagnostic() -> str:
    """
    Devuelve un diagnóstico legible del estado actual de auto-inicio.

    Returns:
        Texto descriptivo del estado de auto-inicio.
    """
    if not _is_windows():
        return "No disponible"

    reg = _detect_registry_autostart_for_current_exe()
    st = _detect_startup_shortcut_for_current_exe()

    if reg and st:
        return "Activado (Registro + Inicio)"
    if reg:
        return "Activado (Registro)"
    if st:
        return "Activado (Inicio)"
    return "Desactivado"


# ---------------------------------------------------------------------------
# Aplicación del auto-inicio
# ---------------------------------------------------------------------------

def set_windows_autostart(
    *,
    enabled: bool,
    method: str = "registry",
    minimized: bool = True,
) -> Tuple[bool, str]:
    """
    Activa o desactiva el auto-inicio de la aplicación con Windows.

    Args:
        enabled: True para activar, False para desactivar.
        method: 'registry' o 'startup'.
        minimized: Iniciar minimizado.

    Returns:
        Tupla (ok, mensaje_error).
    """
    if not _is_windows():
        return False, "Solo disponible en Windows"

    try:
        target, args, workdir, icon = _exe_and_args_for_autostart(minimized)

        # IMPORTANTE:
        # Siempre limpiamos ambas vías primero para evitar estados inconsistentes.
        _apply_registry_autostart(value_name=_autostart_value_name(), command=None)
        _remove_startup_shortcuts(_startup_dir())

        if not enabled:
            return True, ""

        if method == "startup":
            return _apply_startup_shortcut(
                file_name=_autostart_value_name() + ".lnk",
                target=target,
                args=args,
                workdir=workdir,
                icon=icon,
            )

        cmd = f'"{target}" {args}'.strip()
        return _apply_registry_autostart(
            value_name=_autostart_value_name(),
            command=cmd,
        )

    except Exception as e:
        return False, str(e)


def _apply_registry_autostart(
    *,
    value_name: str,
    command: Optional[str],
) -> Tuple[bool, str]:
    """
    Aplica o elimina el auto-inicio vía Registro de Windows.

    Args:
        value_name: Nombre del valor del Registro.
        command: Comando a ejecutar o None para borrar.

    Returns:
        Tupla (ok, error).
    """
    if not _is_windows():
        return False, "N/A"

    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            if command is None:
                try:
                    winreg.DeleteValue(key, value_name)
                except FileNotFoundError:
                    pass
            else:
                winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, command)

        return True, ""

    except Exception as e:
        return False, str(e)


def _apply_startup_shortcut(
    *,
    file_name: str | None = None,
    target: str | None = None,
    args: str | None = None,
    workdir: str | None = None,
    icon: str | None = None,
) -> Tuple[bool, str]:
    """
    Aplica o elimina el auto-inicio usando la carpeta Startup.

    Args:
        file_name: Nombre del archivo .lnk o None para solo limpiar.
        target: Ejecutable objetivo.
        args: Argumentos.
        workdir: Directorio de trabajo.
        icon: Icono.

    Returns:
        Tupla (ok, error).
    """
    if not _is_windows():
        return False, "N/A"

    try:
        sd = _startup_dir()
        sd.mkdir(parents=True, exist_ok=True)

        # Eliminación robusta previa
        _remove_startup_shortcuts(sd)

        if file_name is None:
            return True, ""

        ok, err = _create_lnk_via_vbs(
            lnk_path=str(sd / file_name),
            target=target or "",
            args=args or "",
            workdir=workdir or "",
            icon=icon or "",
        )
        return ok, err

    except Exception as e:
        return False, str(e)


def _remove_startup_shortcuts(startup_dir: Path) -> None:
    """
    Elimina todos los accesos de auto-inicio relacionados con la aplicación.

    Se basa en el nombre base, no en el target,
    para evitar problemas de normalización de rutas.

    Args:
        startup_dir: Directorio Startup.
    """
    name_base = _autostart_value_name().lower()

    for lnk in startup_dir.glob("*.lnk"):
        try:
            if name_base in lnk.stem.lower():
                lnk.unlink(missing_ok=True)
        except Exception:
            # Nunca romper el flujo por un .lnk problemático
            pass