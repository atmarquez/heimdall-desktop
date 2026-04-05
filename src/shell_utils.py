# Heimdall Desktop by Naidel
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

# -*- coding: utf-8 -*-

"""
shell_utils.py

Utilidades de bajo nivel para interactuar con el shell de Windows.

Este módulo encapsula:
- Resolución de accesos directos (.lnk) usando COM (IShellLinkW).
- Ejecución de archivos, carpetas y URLs vía ShellExecuteW.

⚠️ ADVERTENCIAS IMPORTANTES
- Este código es ESPECÍFICO DE WINDOWS.
- Utiliza interfaces COM mediante ctypes.
- Cambios incorrectos pueden provocar fallos difíciles de depurar.

Este módulo existe porque Python no ofrece una API estándar
para resolver completamente archivos .lnk.
"""

import os
import ctypes
from ctypes import wintypes


class GUID(ctypes.Structure):
    """
    Representación ctypes de un GUID de Windows (COM).

    Esta estructura es necesaria para interactuar con interfaces COM,
    que requieren GUIDs en formato binario específico.

    NOTE:
        Esta implementación sigue el layout exacto requerido por WinAPI.
        No modificar sin conocimiento profundo de COM.
    """

    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    def __init__(self, guid_str: str):
        """
        Construye un GUID COM a partir de un string estándar.

        Args:
            guid_str: GUID en formato texto (XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX).
        """
        super().__init__()
        import uuid

        u = uuid.UUID(guid_str)

        self.Data1 = u.time_low
        self.Data2 = u.time_mid
        self.Data3 = u.time_hi_version

        # Data4 debe componerse byte a byte siguiendo el estándar COM
        d4 = [u.clock_seq_hi_variant, u.clock_seq_low]
        d4.extend(u.node.to_bytes(6, "big"))

        self.Data4[:] = bytes(d4)


class IPersistFile(ctypes.Structure):
    """
    Interfaz COM IPersistFile.

    Permite cargar y guardar objetos COM en disco.
    En este módulo se utiliza únicamente para cargar archivos .lnk.
    """
    pass


class IShellLinkW(ctypes.Structure):
    """
    Interfaz COM IShellLinkW.

    Representa un acceso directo de Windows (.lnk) y permite
    consultar y modificar sus propiedades.
    """
    pass


# Alias de tipos WinAPI comunes
LPWSTR = wintypes.LPWSTR

try:
    HRESULT = ctypes.HRESULT
except AttributeError:
    # Compatibilidad con versiones antiguas de Python
    HRESULT = ctypes.c_long


class IPersistFileVtbl(ctypes.Structure):
    """
    Tabla virtual (VTable) de la interfaz COM IPersistFile.

    Solo se definen los métodos estrictamente necesarios.
    """
    _fields_ = [
        ("QueryInterface", ctypes.WINFUNCTYPE(
            HRESULT, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.c_void_p)),
        ("AddRef", ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)),
        ("Release", ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)),
        ("GetClassID", ctypes.c_void_p),
        ("IsDirty", ctypes.c_void_p),
        ("Load", ctypes.WINFUNCTYPE(
            HRESULT, ctypes.c_void_p, LPWSTR, wintypes.DWORD)),
        ("Save", ctypes.c_void_p),
        ("SaveCompleted", ctypes.c_void_p),
        ("GetCurFile", ctypes.c_void_p),
    ]


class IShellLinkWVtbl(ctypes.Structure):
    """
    Tabla virtual (VTable) de la interfaz COM IShellLinkW.

    Define los métodos seleccionados para recuperar:
    - destino
    - argumentos
    - directorio de trabajo
    - icono
    """
    _fields_ = [
        ("QueryInterface", ctypes.WINFUNCTYPE(
            HRESULT, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.c_void_p)),
        ("AddRef", ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)),
        ("Release", ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)),
        ("GetPath", ctypes.WINFUNCTYPE(
            HRESULT, ctypes.c_void_p, LPWSTR, ctypes.c_int,
            ctypes.c_void_p, wintypes.DWORD)),
        ("GetIDList", ctypes.c_void_p),
        ("SetIDList", ctypes.c_void_p),
        ("GetDescription", ctypes.c_void_p),
        ("SetDescription", ctypes.c_void_p),
        ("GetWorkingDirectory", ctypes.WINFUNCTYPE(
            HRESULT, ctypes.c_void_p, LPWSTR, ctypes.c_int)),
        ("SetWorkingDirectory", ctypes.c_void_p),
        ("GetArguments", ctypes.WINFUNCTYPE(
            HRESULT, ctypes.c_void_p, LPWSTR, ctypes.c_int)),
        ("SetArguments", ctypes.c_void_p),
        ("GetHotkey", ctypes.c_void_p),
        ("SetHotkey", ctypes.c_void_p),
        ("GetShowCmd", ctypes.c_void_p),
        ("SetShowCmd", ctypes.c_void_p),
        ("GetIconLocation", ctypes.WINFUNCTYPE(
            HRESULT, ctypes.c_void_p, LPWSTR, ctypes.c_int,
            ctypes.POINTER(ctypes.c_int))),
        ("SetIconLocation", ctypes.c_void_p),
        ("SetRelativePath", ctypes.c_void_p),
        ("Resolve", ctypes.c_void_p),
        ("SetPath", ctypes.c_void_p),
    ]


# Enlazar VTables con las estructuras COM
IPersistFile._fields_ = [("lpVtbl", ctypes.POINTER(IPersistFileVtbl))]
IShellLinkW._fields_ = [("lpVtbl", ctypes.POINTER(IShellLinkWVtbl))]


# ------------------------------------------------------------
# Inicialización de COM y GUIDs conocidos
# ------------------------------------------------------------

ole32 = ctypes.OleDLL("ole32")

CoInitialize = ole32.CoInitialize
CoInitialize.argtypes = [ctypes.c_void_p]
CoInitialize.restype = HRESULT

CoUninitialize = ole32.CoUninitialize

CoCreateInstance = ole32.CoCreateInstance
CoCreateInstance.argtypes = [
    ctypes.POINTER(GUID),
    ctypes.c_void_p,
    wintypes.DWORD,
    ctypes.POINTER(GUID),
    ctypes.c_void_p,
]
CoCreateInstance.restype = HRESULT


# GUIDs estándar de ShellLink
CLSID_ShellLink_GUID  = GUID("00021401-0000-0000-C000-000000000046")
IID_IShellLinkW_GUID  = GUID("000214F9-0000-0000-C000-000000000046")
IID_IPersistFile_GUID = GUID("0000010b-0000-0000-C000-000000000046")


# Constantes WinAPI
CLSCTX_INPROC_SERVER = 0x1
SLGP_UNCPRIORITY     = 0x2
STGM_READ            = 0x00000000


# ShellExecute
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

ShellExecuteW = shell32.ShellExecuteW
ShellExecuteW.argtypes = [
    wintypes.HWND, LPWSTR, LPWSTR, LPWSTR, LPWSTR, ctypes.c_int
]
ShellExecuteW.restype = wintypes.HINSTANCE

SW_SHOWNORMAL = 1


def resolve_lnk(path: str) -> dict | None:
    """
    Resuelve un archivo .lnk de Windows usando COM.

    Args:
        path: Ruta al archivo .lnk.

    Returns:
        Un diccionario con las claves:
        - target: ruta del destino
        - args: argumentos
        - workdir: directorio de trabajo
        - icon_path: ruta del icono
        - icon_index: índice del icono

        Devuelve None si el archivo no existe o no se puede resolver.

    WARNING:
        Esta función:
        - Inicializa COM manualmente.
        - Depende de APIs internas de Windows.
        - Está diseñada para fallar de forma silenciosa
          si algo no se puede resolver, para no romper la UI.
    """
    path = os.fspath(path)

    if not os.path.exists(path) or not path.lower().endswith(".lnk"):
        return None

    CoInitialize(None)

    try:
        psl = ctypes.c_void_p()

        hr = CoCreateInstance(
            ctypes.byref(CLSID_ShellLink_GUID),
            None,
            CLSCTX_INPROC_SERVER,
            ctypes.byref(IID_IShellLinkW_GUID),
            ctypes.byref(psl),
        )
        if hr != 0:
            return None

        psl = ctypes.cast(psl, ctypes.POINTER(IShellLinkW))

        ppf = ctypes.c_void_p()
        hr = psl.contents.lpVtbl.contents.QueryInterface(
            psl,
            ctypes.byref(IID_IPersistFile_GUID),
            ctypes.byref(ppf),
        )
        if hr != 0:
            return None

        ppf = ctypes.cast(ppf, ctypes.POINTER(IPersistFile))

        hr = ppf.contents.lpVtbl.contents.Load(ppf, path, STGM_READ)
        if hr != 0:
            return None

        MAX_PATH = 260

        buf_path = ctypes.create_unicode_buffer(MAX_PATH)
        buf_args = ctypes.create_unicode_buffer(MAX_PATH)
        buf_wdir = ctypes.create_unicode_buffer(MAX_PATH)
        buf_icon = ctypes.create_unicode_buffer(MAX_PATH)
        icon_index = ctypes.c_int(0)

        psl.contents.lpVtbl.contents.GetPath(
            psl, buf_path, MAX_PATH, None, SLGP_UNCPRIORITY)
        psl.contents.lpVtbl.contents.GetArguments(
            psl, buf_args, MAX_PATH)
        psl.contents.lpVtbl.contents.GetWorkingDirectory(
            psl, buf_wdir, MAX_PATH)
        psl.contents.lpVtbl.contents.GetIconLocation(
            psl, buf_icon, MAX_PATH, ctypes.byref(icon_index))

        return {
            "target": buf_path.value,
            "args": buf_args.value,
            "workdir": buf_wdir.value,
            "icon_path": buf_icon.value,
            "icon_index": int(icon_index.value),
        }

    finally:
        # COM debe cerrarse siempre
        try:
            CoUninitialize()
        except Exception:
            pass


def shell_execute(
    path: str,
    args: str | None = None,
    workdir: str | None = None,
    show_cmd: int = SW_SHOWNORMAL,
) -> int:
    """
    Ejecuta un archivo, acceso directo o URL usando ShellExecuteW.

    Args:
        path: Ruta del archivo o URL.
        args: Argumentos opcionales.
        workdir: Directorio de trabajo.
        show_cmd: Modo de visualización de la ventana (WinAPI).

    Returns:
        El handle devuelto por ShellExecuteW.

    Raises:
        OSError: Si ShellExecuteW indica error (códigos <= 32).
    """
    lpFile = os.fspath(path)
    lpParameters = args or None
    lpDirectory = workdir or None

    res = ShellExecuteW(
        None,
        None,
        lpFile,
        lpParameters,
        lpDirectory,
        show_cmd,
    )

    if isinstance(res, int) and res <= 32:
        raise OSError(f"ShellExecuteW falló con código {res}")

    return res