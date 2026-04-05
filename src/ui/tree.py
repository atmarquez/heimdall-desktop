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
ui.tree

QTreeWidget especializado para Heimdall Desktop.

Este módulo implementa el árbol principal que muestra:
- Categorías (directorios).
- Accesos (archivos, accesos directos, etc.).

Funcionalidades principales:
- Soporte completo de arrastrar y soltar (drag & drop).
- Importación de archivos externos.
- Copia, movimiento y creación de accesos directos.
- Integración directa con la lógica de la ventana principal.

IMPORTANTE:
- Este widget forma parte de la UI.
- La lógica de negocio real se delega a otros módulos.
- El árbol actúa como intermediario entre UI y sistema de archivos.
"""

from pathlib import Path
import os
import shutil
from typing import Optional, List, Tuple

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QTreeWidgetItem

# Utilidades de dominio para generar rutas únicas
from core.shortcuts import unique_path, unique_dir

# Roles personalizados usados para almacenar metadatos en los items
from ui.roles import ROLE_PATH, ROLE_IS_DIR


class AppTree(QtWidgets.QTreeWidget):
    """
    Árbol principal de aplicaciones y categorías.

    Esta clase extiende QTreeWidget para:
    - Representar la estructura de carpetas y accesos.
    - Gestionar operaciones de drag & drop.
    - Coordinar acciones con la ventana principal.

    NOTE:
        - El árbol no toma decisiones de negocio.
        - Delegación consciente en `self.window`.
    """

    def __init__(self, window):
        """
        Inicializa el árbol de aplicaciones.

        Args:
            window: Referencia a la ventana principal (MainWindow).
                Se utiliza para delegar acciones como:
                - Importación.
                - Creación de accesos.
                - Recarga de categorías.
        """
        super().__init__(window)

        self.window = window

        # Configuración visual y de interacción
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)
        self.setDefaultDropAction(QtCore.Qt.MoveAction)

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _item_path_is_dir(
        self,
        it: QTreeWidgetItem,
    ) -> Tuple[Optional[Path], bool]:
        """
        Devuelve la ruta asociada a un item y si representa un directorio.

        Args:
            it: Item del árbol (QTreeWidgetItem).

        Returns:
            Tupla (ruta, es_directorio).
            - ruta: Path o None.
            - es_directorio: True si el item representa una carpeta.
        """
        p = it.data(0, ROLE_PATH)
        is_dir = bool(it.data(0, ROLE_IS_DIR))
        return (Path(str(p)) if p else None, is_dir)

    def _calc_target_dir(
        self,
        target_item: Optional[QTreeWidgetItem],
    ) -> Path:
        """
        Calcula el directorio destino para una operación de drop.

        Regla:
        - Si se suelta sobre categoría → esa carpeta.
        - Si se suelta sobre un archivo → carpeta contenedora.
        - Si no hay target → carpeta base.

        Args:
            target_item: Item bajo el cursor (o None).

        Returns:
            Directorio destino como Path.
        """
        base = self.window.base_dir()

        if target_item is None:
            return base

        p = target_item.data(0, ROLE_PATH)
        is_dir = bool(target_item.data(0, ROLE_IS_DIR))

        if p:
            p = Path(str(p))
            return p if is_dir else p.parent

        return base

    def _is_descendant(
        self,
        src_dir: Path,
        target_dir: Path,
    ) -> bool:
        """
        Comprueba si `target_dir` es descendiente de `src_dir`.

        Se usa para evitar:
        - Mover una carpeta dentro de sí misma.
        - Estructuras recursivas inválidas.

        Args:
            src_dir: Directorio origen.
            target_dir: Directorio destino.

        Returns:
            True si target_dir está dentro de src_dir.
        """
        try:
            src_dir = src_dir.resolve()
            target_dir = target_dir.resolve()
        except Exception:
            # Cualquier error → asumir que no es descendiente
            return False

        return str(target_dir).startswith(str(src_dir) + os.sep)

    # ------------------------------------------------------------------
    # Eventos de Drag & Drop
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        """
        Evento al entrar un objeto arrastrado en el árbol.

        Acepta:
        - URLs (arrastre desde Explorador).
        - Arrastres internos del propio árbol.
        """
        md = event.mimeData()

        if md and (md.hasUrls() or event.source() is self):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent):
        """
        Evento al mover un objeto arrastrado sobre el árbol.
        """
        md = event.mimeData()

        if md and (md.hasUrls() or event.source() is self):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent):
        """
        Evento principal de suelta (drop).

        Gestiona dos escenarios:
        1. Arrastre de archivos/carpetas externas.
        2. Arrastre interno de items del propio árbol.

        IMPORTANT:
            Este método es largo pero deliberadamente explícito,
            para mantener claridad y control de errores.
        """
        md = event.mimeData()
        pos = (
            event.position().toPoint()
            if hasattr(event, "position")
            else event.pos()
        )

        target_item = self.itemAt(pos)
        target_dir = self._calc_target_dir(target_item)

        # --------------------------------------------------
        # Caso 1: arrastre desde fuera de la aplicación
        # --------------------------------------------------
        if md and md.hasUrls() and (
            event.source() is None or event.source() is not self
        ):
            paths: List[Path] = []

            for url in md.urls():
                if url.isLocalFile():
                    p = Path(url.toLocalFile())
                    if p.exists():
                        paths.append(p)

            if not paths:
                event.ignore()
                return

            # Preguntar al usuario qué hacer con los archivos
            choice = self.window.ask_drop_import_choice(len(paths))
            if not choice:
                event.ignore()
                return

            completed: List[Path] = []
            self.setUpdatesEnabled(False)

            try:
                for p in paths:
                    try:
                        if choice == "copy":
                            # Copia directa
                            if p.is_dir():
                                dst = unique_dir(target_dir, p.name)
                                shutil.copytree(p, dst)
                                completed.append(dst)
                            else:
                                dst = unique_path(
                                    target_dir,
                                    p.stem,
                                    p.suffix,
                                )
                                target_dir.mkdir(
                                    parents=True,
                                    exist_ok=True,
                                )
                                shutil.copy2(p, dst)
                                completed.append(dst)
                        else:
                            # Creación de acceso directo
                            created = self.window.create_shortcut_to_target(
                                p,
                                target_dir,
                            )
                            if created:
                                completed.append(created)

                    except Exception as e:
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Error al importar",
                            f"No se pudo agregar:\n{p}\n→ {target_dir}\n\n{e}",
                        )

            finally:
                self.setUpdatesEnabled(True)

            if completed:
                last = completed[-1]

                def _refresh():
                    self.window.load_categories()
                    try:
                        self.window.select_item_by_path(last)
                    except Exception:
                        LOGGER.exception(
                            "[auto] Exception capturada en AppTree::dropEvent::_refresh"
                        )

                QtCore.QTimer.singleShot(0, _refresh)

            event.acceptProposedAction()
            return

        # --------------------------------------------------
        # Caso 2: arrastre interno del árbol
        # --------------------------------------------------
        items = self.selectedItems()
        if not items:
            event.ignore()
            return

        copy_mode = bool(
            event.keyboardModifiers() & QtCore.Qt.ControlModifier
        )

        completed: List[Path] = []
        self.setUpdatesEnabled(False)

        try:
            for it in items:
                p, is_dir = self._item_path_is_dir(it)
                if not p or not p.exists():
                    continue

                try:
                    if is_dir:
                        # Evitar mover carpeta dentro de sí misma
                        if (
                            self._is_descendant(p, target_dir)
                            or target_dir.resolve() == p.resolve()
                        ):
                            continue

                        dest_dir = unique_dir(target_dir, p.name)
                        if copy_mode:
                            shutil.copytree(p, dest_dir)
                        else:
                            shutil.move(
                                os.fspath(p),
                                os.fspath(dest_dir),
                            )
                        completed.append(dest_dir)

                    else:
                        dest = unique_path(
                            target_dir,
                            p.stem,
                            p.suffix,
                        )
                        target_dir.mkdir(
                            parents=True,
                            exist_ok=True,
                        )
                        if copy_mode:
                            shutil.copy2(p, dest)
                        else:
                            shutil.move(
                                os.fspath(p),
                                os.fspath(dest),
                            )
                        completed.append(dest)

                except Exception as e:
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Error al procesar",
                        f"No se pudo completar la operación:\n{p}\n→ {target_dir}\n\n{e}",
                    )

        finally:
            self.setUpdatesEnabled(True)

        if completed:
            last_path = completed[-1]

            def _after_drop_refresh():
                self.window.load_categories()
                try:
                    self.window.select_item_by_path(last_path)
                except Exception:
                    LOGGER.exception(
                        "[auto] Exception capturada en AppTree::dropEvent::_after_drop_refresh"
                    )

            QtCore.QTimer.singleShot(0, _after_drop_refresh)

        event.setDropAction(
            QtCore.Qt.CopyAction if copy_mode else QtCore.Qt.MoveAction
        )
        event.accept()
