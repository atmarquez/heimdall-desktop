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
Utilidades de seguridad para Heimdall Desktop.

Este módulo agrupa funciones relacionadas con:
- Protección y descifrado de secretos mediante DPAPI (en Windows).
- Generación y validación de tokens HMAC.
- Comparación segura de valores sensibles.
- Manipulación de URLs y parámetros de autenticación.

IMPORTANT:
    Este módulo es crítico para la seguridad del servidor HTTP.
    Cualquier modificación debe revisarse cuidadosamente.

NOTE:
    El módulo incluye fallbacks explícitos para entornos no Windows,
    intencionados principalmente para pruebas o ejecución limitada.
"""

import sys
import base64
import hmac
import secrets
from hashlib import sha256
from typing import Tuple

# ------------------------------------------------------------------
# Logging opcional
# ------------------------------------------------------------------
# NOTE:
#   El logging no es obligatorio para el funcionamiento del módulo.
#   Si no está disponible, las funciones siguen siendo funcionales.
try:
    import logging
    LOGGER = logging.getLogger(__name__)
except Exception:
    LOGGER = None

# ==========================================================
# DPAPI (Windows)
# ==========================================================

# Detección explícita de plataforma Windows
_IS_WIN = sys.platform.startswith("win")

if _IS_WIN:
    import ctypes
    import ctypes.wintypes as wt

    class _DATA_BLOB(ctypes.Structure):
        """
        Estructura DATA_BLOB utilizada por la API de Windows (DPAPI).

        Representa un bloque de memoria binaria administrado por el sistema.
        """
        _fields_ = [
            ("cbData", wt.DWORD),
            ("pbData", wt.LPBYTE),
        ]

    # Carga de librerías del sistema
    _crypt32 = ctypes.WinDLL("Crypt32.dll")
    _kernel32 = ctypes.WinDLL("Kernel32.dll")


def _to_blob(data: bytes):
    """
    Convierte bytes Python a una estructura DATA_BLOB.

    Args:
        data (bytes): Datos binarios a proteger/descifrar.

    Returns:
        _DATA_BLOB: Estructura compatible con DPAPI.
    """
    blob = _DATA_BLOB()
    blob.cbData = len(data)
    blob.pbData = ctypes.cast(ctypes.create_string_buffer(data), wt.LPBYTE)
    return blob


def _from_blob(blob) -> bytes:
    """
    Extrae bytes de una estructura DATA_BLOB y libera la memoria asociada.

    Args:
        blob (_DATA_BLOB): Estructura retornada por DPAPI.

    Returns:
        bytes: Datos originales.
    """
    buf = ctypes.create_string_buffer(blob.cbData)
    ctypes.memmove(buf, blob.pbData, blob.cbData)
    try:
        _kernel32.LocalFree(blob.pbData)
    except Exception:
        # Código defensivo: fallo al liberar memoria no debe romper flujo
        pass
    return buf.raw


def dpapi_protect_user(data: bytes) -> str:
    """
    Protege datos utilizando DPAPI con el contexto del usuario actual.

    En Windows:
        - Se utiliza CryptProtectData.
        - El resultado se devuelve codificado en Base64.

    Fuera de Windows:
        - Se utiliza un fallback explícito SIN cifrado real.

    WARNING:
        El fallback "plain:" NO proporciona seguridad criptográfica.

    Args:
        data (bytes): Datos a proteger.

    Returns:
        str: Datos protegidos en formato Base64 (o plain:* en fallback).
    """
    if not _IS_WIN:
        # Fallback explícito (NO cifrado)
        raw = base64.urlsafe_b64encode(data).decode().rstrip("=")
        return "plain:" + raw

    in_blob = _to_blob(data)
    out_blob = _DATA_BLOB()

    if not _crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        1,
        ctypes.byref(out_blob),
    ):
        raise ctypes.WinError()

    protected = _from_blob(out_blob)
    return base64.b64encode(protected).decode()


def dpapi_unprotect_user(protected_b64: str) -> bytes:
    """
    Descifra datos previamente protegidos con DPAPI.

    Soporta:
    - Formato real DPAPI en Windows.
    - Fallback plain:* en cualquier sistema.

    Args:
        protected_b64 (str): Datos protegidos en Base64 o prefijo "plain:".

    Returns:
        bytes: Datos originales.

    Raises:
        RuntimeError: Si DPAPI no está disponible o falla el descifrado.
    """
    if protected_b64.startswith("plain:"):
        raw = protected_b64[len("plain:"):]
        pad = "=" * (-len(raw) % 4)
        return base64.urlsafe_b64decode(raw + pad)

    if not _IS_WIN:
        raise RuntimeError("DPAPI no disponible fuera de Windows")

    blob = base64.b64decode(protected_b64)
    in_blob = _to_blob(blob)
    out_blob = _DATA_BLOB()

    if not _crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        1,
        ctypes.byref(out_blob),
    ):
        raise RuntimeError("DPAPI: no se pudo descifrar el secreto")

    return _from_blob(out_blob)

# ==========================================================
# Tokens / HMAC
# ==========================================================

def generate_secret_b64url(nbytes: int = 32) -> str:
    """
    Genera un secreto aleatorio en formato Base64 URL-safe.

    Args:
        nbytes (int): Número de bytes aleatorios.

    Returns:
        str: Secreto codificado sin padding.
    """
    raw = secrets.token_bytes(nbytes)
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def secret_to_bytes(secret: str) -> bytes:
    """
    Convierte un secreto Base64 URL-safe a bytes.

    Fallback:
        Si la decodificación falla, se interpreta como UTF-8.

    Args:
        secret (str): Secreto codificado.

    Returns:
        bytes: Secreto en formato binario.
    """
    try:
        pad = "=" * (-len(secret) % 4)
        return base64.urlsafe_b64decode(secret + pad)
    except Exception:
        return secret.encode("utf-8")


def compute_hmac_hex(raw_url_without_token: str, secret: str) -> str:
    """
    Calcula un HMAC SHA-256 en formato hexadecimal.

    Args:
        raw_url_without_token (str):
            URL completa sin el parámetro token.
        secret (str):
            Secreto compartido.

    Returns:
        str: HMAC expresado en hexadecimal.
    """
    key = secret_to_bytes(secret)
    msg = raw_url_without_token.encode("utf-8")
    return hmac.new(key, msg, sha256).hexdigest()


def consteq(a: str, b: str) -> bool:
    """
    Compara dos cadenas de forma segura contra ataques de temporización.

    Args:
        a (str): Primer valor.
        b (str): Segundo valor.

    Returns:
        bool: True si son iguales, False en caso contrario.
    """
    return hmac.compare_digest(a, b)

# ==========================================================
# Helpers URL / token
# ==========================================================

def split_path_query(raw_target: str) -> Tuple[str, str]:
    """
    Separa una URL en ruta y query string.

    Args:
        raw_target (str): URL completa.

    Returns:
        Tuple[str, str]: (ruta, query)
    """
    if "?" in raw_target:
        return raw_target.split("?", 1)
    return raw_target, ""


def strip_token_param(query: str):
    """
    Elimina el parámetro token de una query string.

    Args:
        query (str): Query string original.

    Returns:
        tuple:
            (query_sin_token, token_extraído, número_de_tokens)
    """
    if not query:
        return "", "", 0

    parts = query.split("&")
    out = []
    token_value = ""
    count = 0

    for part in parts:
        k, sep, v = part.partition("=")
        if k == "token":
            token_value = v
            count += 1
        else:
            out.append(part)

    return "&".join(out), token_value, count