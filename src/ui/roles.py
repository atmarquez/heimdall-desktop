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
Definición centralizada de roles Qt para widgets de la UI.

Este módulo define constantes de roles personalizados (`Qt.UserRole`)
utilizados para almacenar metadatos asociados a elementos de la interfaz,
principalmente en modelos y vistas (por ejemplo, QTreeWidget, QListView).

Su existencia evita:
- Valores mágicos dispersos por el código.
- Colisiones accidentales de roles.
- Errores al reinterpretar datos almacenados en ítems de la UI.

IMPORTANT:
    Estos roles forman parte del contrato implícito entre distintos
    widgets de la interfaz. Cambiarlos rompe compatibilidad interna.

NOTE:
    Todos los roles deben derivar de Qt.UserRole o superiores,
    nunca de roles predefinidos por Qt.
"""

from PySide6 import QtCore

# ------------------------------------------------------------------
# Roles personalizados compartidos entre widgets
# ------------------------------------------------------------------

#: Ruta asociada a un elemento (archivo o directorio).
#: Normalmente contiene un `str` o `pathlib.Path`.
ROLE_PATH = QtCore.Qt.UserRole

#: Indica si el elemento representa un directorio.
#: Normalmente contiene un `bool`.
ROLE_IS_DIR = QtCore.Qt.UserRole + 1
