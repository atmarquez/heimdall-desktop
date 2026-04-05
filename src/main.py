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
main.py

Punto de entrada principal de Heimdall Desktop.

Responsabilidades de este fichero:
- Cargar la configuración inicial desde disco.
- Configurar el sistema de logging global de la aplicación.
- Inicializar la aplicación Qt (QApplication).
- Crear y mostrar la ventana principal (MainWindow).
- Lanzar el bucle de eventos de Qt.

IMPORTANTE:
- Este fichero NO contiene lógica de negocio.
- Este fichero NO contiene código de UI complejo.
- Toda la lógica funcional vive en módulos separados (ui/, core/, server/, etc.).

Este diseño es intencionado para mantener un arranque limpio y fácilmente mantenible.
"""

import sys
import logging

from PySide6.QtWidgets import QApplication

from config.service import load_config
from logutils.setup import (
    setup_logging_from_cfg,
    install_qmessagebox_logging,
    install_excepthook,
)
from logutils.memory import MemoryLogHandler

# Ventana principal de la aplicación.
# Toda la lógica de interfaz gráfica vive en esta clase.
from ui.main_window import MainWindow


def install_memory_logging() -> None:
    """
    Instala un handler de logging en memoria.

    Este handler permite:
    - Capturar logs recientes en memoria.
    - Mostrar el log desde la interfaz si es necesario.
    - Facilitar diagnóstico sin depender solo de ficheros físicos.

    Notes:
        - Este handler es opcional.
        - Su uso es seguro, pero establecer nivel DEBUG
          puede aumentar ligeramente el consumo de memoria.
    """
    root = logging.getLogger()

    handler = MemoryLogHandler()
    handler.setLevel(logging.DEBUG)

    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    )

    root.addHandler(handler)


# Metadato de licencia legible por herramientas y desarrolladores.
# Se define aquí (punto de entrada) para representar al programa completo.
__license__ = "GPL-3.0-or-later"


def main() -> None:
    """
    Función principal de arranque de la aplicación.

    Flujo de ejecución:
        1. Cargar configuración persistente desde disco.
        2. Configurar el sistema de logging (una sola vez).
        3. Inicializar QApplication (Qt).
        4. Crear la ventana principal (MainWindow).
        5. Aplicar comportamiento de inicio (mostrar/minimizar).
        6. Entrar en el bucle de eventos Qt.

    Important:
        - NO crear widgets antes de QApplication.
        - NO reconfigurar logging después de crear ventanas.
    """

    # -------------------------------------------------
    # 1. Cargar configuración
    # -------------------------------------------------
    # Se carga lo antes posible para que:
    # - logging lea niveles correctos
    # - temas y preferencias se apliquen desde inicio
    cfg = load_config()

    # -------------------------------------------------
    # 2. Configurar logging global
    # -------------------------------------------------
    # WARNING:
    # Esta función DEBE llamarse SOLO UNA VEZ.
    # Llamarla múltiples veces provocaría handlers duplicados.
    setup_logging_from_cfg(cfg)

    # Handler opcional para observabilidad en memoria.
    install_memory_logging()

    # Hook para mostrar errores no capturados con QMessageBox.
    install_qmessagebox_logging()

    # Hook global para excepciones no capturadas.
    install_excepthook()

    # -------------------------------------------------
    # 3. Inicializar Qt
    # -------------------------------------------------
    # QApplication debe crearse antes de cualquier widget.
    app = QApplication(sys.argv)

    # -------------------------------------------------
    # 4. Crear ventana principal
    # -------------------------------------------------
    window = MainWindow()

    # -------------------------------------------------
    # 5. Comportamiento inicial (mostrar / minimizar)
    # -------------------------------------------------
    # NOTE:
    # - La propia MainWindow guarda esta preferencia en self.cfg.
    # - Aquí solo decidimos si mostrarla inmediatamente.
    if not window.cfg.get('start_minimized', True):
        window.position_and_show()

    # -------------------------------------------------
    # 6. Bucle de eventos
    # -------------------------------------------------
    # Se bloquea aquí hasta que la aplicación finalice.
    sys.exit(app.exec())


# Convención estándar de Python:
# Permite ejecutar este fichero directamente sin importarlo como módulo.
if __name__ == "__main__":
    main()