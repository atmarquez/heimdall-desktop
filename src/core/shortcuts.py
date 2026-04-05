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
core.shortcuts

Creación y gestión de accesos directos (.lnk, .url) y utilidades asociadas.

Este módulo encapsula la lógica de dominio relacionada con:
- Creación de accesos directos de Windows (.lnk) mediante VBS.
- Creación de accesos web (.url).
- Generación de nombres de archivo seguros.
- Evitar colisiones de nombres en el sistema de archivos.

IMPORTANTE:
- Este módulo está orientado a Windows.
- No depende de la interfaz gráfica.
- Se usa desde distintos puntos del proyecto (UI, comandos especiales, etc.).
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Tuple


def sanitize_filename(name: str) -> str:
    """
    Devuelve un nombre de archivo o carpeta válido para sistemas Windows.

    Sustituye caracteres no permitidos por guiones bajos y elimina
    terminaciones problemáticas.

    Args:
        name: Nombre original proporcionado por el usuario.

    Returns:
        Nombre saneado y seguro para su uso en el sistema de archivos.

    NOTE:
        - Windows prohíbe ciertos caracteres como < > : " / \\ | ? *.
        - También se eliminan saltos de línea y puntos finales.
    """
    invalid = '<>:"/\\\n?*'
    sanitized = ''.join('_' if c in invalid else c for c in name)
    sanitized = sanitized.strip().rstrip('. ')

    # Garantizar siempre un nombre no vacío
    return sanitized or 'Acceso'


def unique_path(dir_path: Path, stem: str, ext: str) -> Path:
    """
    Genera una ruta única para un archivo, evitando sobrescrituras.

    Si el nombre ya existe, añade un sufijo incremental:
    - nombre.ext
    - nombre (2).ext
    - nombre (3).ext
    ...

    Args:
        dir_path: Directorio destino.
        stem: Nombre base del archivo (sin extensión).
        ext: Extensión del archivo (incluyendo el punto).

    Returns:
        Ruta única donde puede crearse el archivo con seguridad.
    """
    dir_path.mkdir(parents=True, exist_ok=True)

    base = dir_path / f'{stem}{ext}'
    if not base.exists():
        return base

    n = 2
    while True:
        candidate = dir_path / f'{stem} ({n}){ext}'
        if not candidate.exists():
            return candidate
        n += 1


def unique_dir(parent: Path, name: str) -> Path:
    """
    Genera una ruta única para un directorio, evitando colisiones de nombre.

    Usa el mismo esquema incremental que los archivos:
    - carpeta
    - carpeta (2)
    - carpeta (3)
    ...

    Args:
        parent: Directorio padre donde se creará la carpeta.
        name: Nombre base del directorio.

    Returns:
        Ruta única para la nueva carpeta.
    """
    parent.mkdir(parents=True, exist_ok=True)

    dst = parent / name
    if not dst.exists():
        return dst

    n = 2
    while True:
        cand = parent / f'{name} ({n})'
        if not cand.exists():
            return cand
        n += 1


def create_lnk_via_vbs(
    lnk_path: str,
    target: str,
    args: str = '',
    workdir: str = '',
    icon: str = '',
) -> Tuple[bool, str]:
    """
    Crea un acceso directo de Windows (.lnk) utilizando un script VBS.

    Este método evita:
    - Dependencias externas como pywin32.
    - Uso directo de COM desde Python.

    En su lugar, delega la creación del acceso a `cscript.exe`
    mediante un pequeño script VBScript temporal.

    Args:
        lnk_path: Ruta completa donde se creará el acceso directo.
        target: Ejecutable o recurso de destino.
        args: Argumentos a pasar al ejecutable.
        workdir: Directorio de trabajo del acceso.
        icon: Ruta del icono a usar.

    Returns:
        Tupla (ok, mensaje_error):
        - ok: True si se creó correctamente.
        - mensaje_error: Texto de error si falló.

    WARNING:
        Este método es específico de Windows.
        Fallos aquí no deben propagarse sin control.
    """

    def esc(s: str) -> str:
        # Escape básico de comillas para VBScript
        return s.replace('"', '""')

    vbs = (
        'Set WshShell = WScript.CreateObject("WScript.Shell")\n'
        f'Set lnk = WshShell.CreateShortcut("{esc(lnk_path)}")\n'
        f'lnk.TargetPath = "{esc(target)}"\n'
        f'lnk.Arguments = "{esc(args)}"\n'
        f'lnk.WorkingDirectory = "{esc(workdir)}"\n'
        f'lnk.IconLocation = "{esc(icon)}"\n'
        'lnk.Save\n'
    )

    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(suffix='.vbs', text=True)
        os.close(fd)

        Path(tmp).write_text(vbs, encoding='utf-8')

        res = subprocess.run(
            ['cscript', '//nologo', tmp],
            capture_output=True,
            text=True,
        )

        if res.returncode != 0:
            return False, res.stderr or res.stdout

        return True, ''

    except Exception as e:
        # Fallback defensivo: devolvemos el error sin lanzar excepción
        return False, str(e)

    finally:
        # Limpieza obligatoria del fichero temporal
        if tmp and Path(tmp).exists():
            try:
                Path(tmp).unlink()
            except Exception:
                pass


def create_url_shortcut(
    dest_dir: Path,
    name: str,
    url: str,
) -> Path:
    """
    Crea un acceso web de Windows (.url).

    Este tipo de acceso es interpretado directamente por el Explorador
    y se utiliza para:
    - URLs HTTP/HTTPS
    - FTP
    - file://
    - Otros protocolos soportados por Windows

    Args:
        dest_dir: Directorio destino.
        name: Nombre base del acceso.
        url: URL de destino.

    Returns:
        Ruta al archivo .url creado.

    NOTE:
        El formato .url es un fichero INI sencillo
        reconocido nativamente por Windows.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    path = unique_path(dest_dir, name, '.url')
    content = f'[InternetShortcut]\r\nURL={url}\r\n'

    path.write_text(content, encoding='utf-8', errors='ignore')
    return path
