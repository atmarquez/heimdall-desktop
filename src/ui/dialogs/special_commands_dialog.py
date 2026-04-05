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
ui.dialogs.special_commands_dialog

Diálogo para explorar y utilizar comandos especiales de Windows
a partir de un catálogo definido en formato JSON.

Este diálogo permite:
- Explorar comandos del tipo shell:, ms-settings:, .msc, CLSID, etc.
- Filtrar por texto y categoría.
- Ejecutar comandos directamente desde la aplicación.
- Copiar comandos al portapapeles.
- Crear accesos en el lanzador principal.
- Descargar y fusionar automáticamente catálogos públicos.

IMPORTANT:
- Este diálogo NO define lógica de ejecución real de comandos.
- Se apoya en MainWindow para ejecutar o crear accesos.
- Está diseñado para ser tolerante a errores y fuentes externas.
"""

# ------------------------------------------------------------
# ui/dialogs/special_commands_dialog.py -> Clase SpecialCommandsDialog
# ------------------------------------------------------------

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTreeWidget, QPlainTextEdit, QMenu
)

from pathlib import Path
import os
import json

from ui.helpers import HelpableDialogMixin
from ui.help import open_help_page

from ui.tree import ROLE_PATH, ROLE_IS_DIR
from shell_utils import resolve_lnk
from config.service import app_dir


class SpecialCommandsDialog(HelpableDialogMixin, QDialog):
    """
    Diálogo para explorar y usar comandos especiales de Windows.

    Este diálogo proporciona una interfaz de catálogo avanzada
    que permite gestionar comandos “no convencionales” de Windows,
    como URIs internas, CLSID, consolas MMC y comandos del Shell.
    """

    #: Tema de ayuda contextual
    help_topic = 'special_commands'

    def __init__(self, parent=None, json_path: str = ''):
        """
        Inicializa el diálogo de comandos especiales.

        Args:
            parent: Widget padre (normalmente MainWindow).
            json_path: Ruta opcional a un catálogo JSON personalizado.
        """
        super().__init__(parent)
        self.setWindowTitle('Comandos especiales')
        self.resize(820, 520)

        self.json_path = json_path
        self.items = []

        main = QVBoxLayout(self)

        # --------------------------------------------------
        # Barra superior de filtros
        # --------------------------------------------------
        top = QWidget(self)
        h = QtWidgets.QHBoxLayout(top)
        h.setContentsMargins(0, 0, 0, 0)

        self.filter_edit = QLineEdit(top)
        self.filter_edit.setPlaceholderText('Filtrar por comando o descripción…')

        self.category_combo = QtWidgets.QComboBox(top)
        self.category_combo.addItem(
            'Todas las categorías',
            userData='__ALL__'
        )

        btn_reload = QPushButton('Refrescar', top)

        h.addWidget(self.filter_edit, 1)
        h.addWidget(self.category_combo)
        h.addWidget(btn_reload)

        self.btn_fetch = QPushButton('Descargar catálogo', top)
        h.addWidget(self.btn_fetch)

        main.addWidget(top)

        # --------------------------------------------------
        # Lista de comandos
        # --------------------------------------------------
        self.list = QtWidgets.QTreeWidget(self)
        self.list.setHeaderLabels(['Comando', 'Categoría'])
        self.list.setColumnWidth(0, 460)
        self.list.setSelectionMode(
            QtWidgets.QAbstractItemView.ExtendedSelection
        )
        main.addWidget(self.list, 1)

        # --------------------------------------------------
        # Área de descripción
        # --------------------------------------------------
        self.desc = QtWidgets.QPlainTextEdit(self)
        self.desc.setReadOnly(True)
        self.desc.setFixedHeight(110)
        main.addWidget(self.desc)

        # --------------------------------------------------
        # Botonera inferior de acciones
        # --------------------------------------------------
        btns_row = QWidget(self)
        hb = QtWidgets.QHBoxLayout(btns_row)
        hb.setContentsMargins(0, 0, 0, 0)

        self.btn_open = QPushButton('Abrir', btns_row)
        self.btn_copy = QPushButton('Copiar comando', btns_row)
        self.btn_shortcut = QPushButton(
            'Crear acceso en el lanzador',
            btns_row
        )

        hb.addWidget(self.btn_open)
        hb.addWidget(self.btn_copy)
        hb.addWidget(self.btn_shortcut)
        hb.addStretch(1)

        main.addWidget(btns_row)

        # --------------------------------------------------
        # Botón cerrar + ayuda
        # --------------------------------------------------
        close_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Close,
            self
        )
        close_box.rejected.connect(self.reject)
        self._install_help_button(close_box)
        main.addWidget(close_box)

        # --------------------------------------------------
        # Conexión de señales
        # --------------------------------------------------
        self.filter_edit.textChanged.connect(
            lambda _: self._apply_filter()
        )
        self.category_combo.currentIndexChanged.connect(
            lambda _: self._apply_filter()
        )
        self.list.itemSelectionChanged.connect(
            self._on_selection_changed
        )
        self.btn_open.clicked.connect(self._on_open_clicked)
        self.btn_copy.clicked.connect(self._on_copy_clicked)
        self.btn_shortcut.clicked.connect(self._on_create_shortcut)
        btn_reload.clicked.connect(self._reload)

        try:
            self.btn_fetch.clicked.connect(
                self._fetch_and_update_catalog
            )
        except Exception:
            # Descarga opcional: no debe romper la UI
            pass

        self._reload()

    def _reload(self):
        """
        Carga o recarga el catálogo JSON y reconstruye la interfaz.
        """
        self.items = []
        self.list.clear()

        self.category_combo.blockSignals(True)
        self.category_combo.clear()
        self.category_combo.addItem(
            'Todas las categorías',
            userData='__ALL__'
        )
        self.category_combo.blockSignals(False)

        path = (
            Path(self.json_path)
            if self.json_path
            else Path(app_dir()) / 'windows_special_commands.json'
        )

        try:
            data = json.loads(
                Path(path).read_text(encoding='utf-8')
            )
            raw = data.get('items', []) if isinstance(data, dict) else []
            cats = []

            for it in raw:
                cat = str(it.get('Categoría', '') or '')
                cmd = str(it.get('Comando', '') or '')
                desc = str(it.get('Descripción', '') or '')

                if not cmd:
                    continue

                self.items.append({
                    'cat': cat,
                    'cmd': cmd,
                    'desc': desc
                })

                if cat and cat not in cats:
                    cats.append(cat)

            for c in sorted(cats, key=str.lower):
                self.category_combo.addItem(c, userData=c)

        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                'Catálogo',
                f'No se pudo cargar el catálogo JSON:\n'
                f'{path}\n\n{e}'
            )

        self._apply_filter()

    def _fetch_and_update_catalog(self):
        """
        Descarga y actualiza el catálogo de comandos especiales de Windows.

        Este método:
        - Descarga información desde varias fuentes públicas (HTTP).
        - Extrae comandos especiales (ms-settings, shell:, .msc y CLSID).
        - Fusiona los resultados con el catálogo existente si lo hay.
        - Actualiza el archivo `windows_special_commands.json`.
        - Recarga el contenido en la interfaz.

        IMPORTANT:
            Este método realiza accesos de red y escritura en disco.
            Está protegido mediante múltiples bloques try/except para
            evitar bloquear la interfaz ante fallos externos.

        WARNING:
            Las fuentes externas pueden cambiar o desaparecer.
            El catálogo nunca se sobrescribe sin intentar preservar
            entradas existentes.

        Returns:
            None
        """        
        import urllib.request, urllib.error, io, csv
        import re as _re, time
        base_dir = app_dir()
        out_path = base_dir / 'windows_special_commands.json'
        def _http_get(url, timeout=20):
            """
            Realiza una petición HTTP GET simple con User-Agent estándar.

            NOTE:
                Se usa un User-Agent genérico para evitar bloqueos básicos.

            Args:
                url (str): URL a descargar.
                timeout (int): Timeout en segundos.

            Returns:
                bytes: Contenido descargado.
            """
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        # Cargar catálogo existente si existe
        try:
            existing = json.loads(out_path.read_text(encoding='utf-8')) if out_path.exists() else {"metadata": {}, "items": []}
        except Exception:
            # Código defensivo: catálogo corrupto o ilegible
            existing = {"metadata": {}, "items": []}
        items, sources = [], []
        
        # ---------------------------------------------------------
        # ms-settings: (CSV público)
        # ---------------------------------------------------------
        try:
            ms_url = 'https://gist.github.com/apersonintech/8d255c61adc292d90373ee0dc017f3f3/raw'
            raw = _http_get(ms_url)
            reader = csv.reader(io.StringIO(raw.decode('utf-8', errors='ignore')))
            for row in reader:
                for cell in row:
                    c = (cell or '').strip()
                    if c.startswith('ms-settings:'):
                        items.append({"Categoría": 'ms-settings:', "Comando": c, "Descripción": 'URI de Configuración (Windows). Fuente: Gist CSV.'})
                        break
            sources.append(ms_url)
        except Exception:
            # Fallo tolerable: fuente externa no disponible
            pass

        # ---------------------------------------------------------
        # shell: (HTML)
        # ---------------------------------------------------------
        try:
            sh_url = 'https://windowsloop.com/windows-shell-commands/'
            html = _http_get(sh_url).decode('utf-8', errors='ignore')
            for m in _re.finditer(r'\bshell:([A-Za-z0-9 .-]+)\b', html, _re.IGNORECASE):
                cmd = f"shell:{m.group(1).strip()}"
                if any(x.get('Comando','').lower() == cmd.lower() for x in items):
                    continue
                items.append({"Categoría": 'shell:', "Comando": cmd, "Descripción": 'Carpeta especial del Explorador. Fuente: WindowsLoop.'})
            sources.append(sh_url)
        except Exception:
            pass
        
        # ---------------------------------------------------------
        # .msc (MMC)
        # ---------------------------------------------------------
        try:
            msc_url = 'https://www.itechtics.com/msc-files/'
            html = _http_get(msc_url).decode('utf-8', errors='ignore')
            for m in _re.finditer(r'\b([a-z0-9_.-]+\.msc)\b', html, _re.IGNORECASE):
                cmd = m.group(1)
                if len(cmd) >= 6 and not any(x.get('Comando','').lower() == cmd.lower() for x in items):
                    items.append({"Categoría": '.msc (MMC)', "Comando": cmd, "Descripción": 'Consola de administración MMC. Fuente: ITechtics.'})
            sources.append(msc_url)
        except Exception:
            pass

        # ---------------------------------------------------------
        # CLSID / GUID (Shell)
        # ---------------------------------------------------------
        try:
            clsid_url = 'https://www.elevenforum.com/t/list-of-windows-11-clsid-key-guid-shortcuts.1075/'
            html = _http_get(clsid_url).decode('utf-8', errors='ignore')
            for m in _re.finditer(r'shell:::\\{[0-9A-Fa-f-]{36}\\}(?:\\\\[A-Za-z0-9_]+)?', html):
                cmd = m.group(0)
                if not any(x.get('Comando','').lower() == cmd.lower() for x in items):
                    items.append({"Categoría": 'CLSID / GUID (Shell)', "Comando": cmd, "Descripción": 'Ubicación virtual del Shell (GUID). Fuente: Windows 11 Forum.'})
            sources.append(clsid_url)
        except Exception:
            pass

        # ---------------------------------------------------------
        # Fusión con catálogo existente
        # ----------------------------------------------------
        try:
            existing_items = existing.get('items', []) if isinstance(existing, dict) else []
        except Exception:
            existing_items = []
        merged = { (i.get('Comando') or '').lower(): i for i in existing_items if isinstance(i, dict) }
        for it in items:
            key = (it.get('Comando') or '').lower()
            if key and key not in merged:
                merged[key] = it
        merged_list = list(merged.values())
        new_meta = {
            "nombre": existing.get('metadata', {}).get('nombre') or 'Windows Special Commands Catalog',
            "version": existing.get('metadata', {}).get('version') or '1.0.0',
            "generado_en": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            "comentario": "Catálogo consolidado automáticamente desde fuentes públicas.",
            "fuentes_generales": [
                {"titulo": "Windows Shell Commands (shell:)", "url": "https://windowsloop.com/windows-shell-commands/"},
                {"titulo": "MS-Settings URI list (CSV)", "url": "https://gist.github.com/apersonintech/8d255c61adc292d90373ee0dc017f3f3"},
                {"titulo": "List Of .MSC Consoles", "url": "https://www.itechtics.com/msc-files/"},
                {"titulo": "Windows 11 CLSID list", "url": "https://www.elevenforum.com/t/list-of-windows-11-clsid-key-guid-shortcuts.1075/"}
            ],
            "_ultima_descarga": {"fuentes_usadas": sources, "total_fusionado": len(merged_list)}
        }
        try:
            out_path.write_text(json.dumps({"metadata": new_meta, "items": merged_list}, ensure_ascii=False, indent=2), encoding='utf-8')
            QtWidgets.QMessageBox.information(self, 'Catálogo actualizado', f'Se han fusionado {len(merged_list)} entradas.\n\nArchivo:\n{out_path}')
            self._reload()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Error', f'No se pudo escribir el catálogo:\n{e}')

    def _apply_filter(self):
        """
        Aplica el filtro de texto y categoría al listado de comandos.

        Filtra por:
        - Categoría seleccionada.
        - Texto contenido en comando o descripción.

        Returns:
            None
        """
        txt = (self.filter_edit.text() or '').strip().lower()
        want_cat = self.category_combo.currentData()

        self.list.clear()

        for it in self.items:
            if want_cat and want_cat != '__ALL__' and it['cat'] != want_cat:
                continue
            if txt and (
                txt not in it['cmd'].lower() and
                txt not in it['desc'].lower()
            ):
                continue

            item = QtWidgets.QTreeWidgetItem([it['cmd'], it['cat']])
            item.setData(0, ROLE_PATH, it['cmd'])
            item.setData(0, ROLE_IS_DIR, False)
            item.setToolTip(0, it['desc'])
            self.list.addTopLevelItem(item)

        if self.list.topLevelItemCount() > 0:
            self.list.setCurrentItem(self.list.topLevelItem(0))

    def _on_selection_changed(self):
        """
        Actualiza el panel de descripción según el elemento seleccionado.
        """
        it = self.list.currentItem()
        if not it:
            self.desc.setPlainText('')
            return
        self.desc.setPlainText(it.toolTip(0) or '')

    def _selected_commands(self):
        """
        Devuelve la lista de comandos seleccionados.

        Returns:
            list[dict]: Lista de comandos con claves cmd, cat y desc.
        """
        items = self.list.selectedItems() or []
        if not items and self.list.topLevelItemCount() > 0:
            items = [self.list.topLevelItem(0)]

        cmds = []
        for it in items:
            cmds.append({
                'cmd': it.text(0),
                'cat': it.text(1),
                'desc': it.toolTip(0) or '',
            })
        return cmds

    def _on_open_clicked(self):
        """
        Ejecuta los comandos seleccionados utilizando MainWindow.
        """
        mw = self.parent() if isinstance(self.parent(), MainWindow) else None
        if not mw:
            return

        for entry in self._selected_commands():
            mw.execute_special_command(entry['cmd'], entry['cat'])

    def _on_copy_clicked(self):
        """
        Copia los comandos seleccionados al portapapeles.
        """
        cb = QtGui.QGuiApplication.clipboard()
        cmds = [e['cmd'] for e in self._selected_commands()]
        cb.setText('\n'.join(cmds))

    def _on_create_shortcut(self):
        """
        Crea accesos en la carpeta base para los comandos seleccionados.
        """
        mw = self.parent()
        if not mw or not hasattr(
            mw,
            "create_shortcut_for_special_command"
        ):
            return

        last = None
        for entry in self._selected_commands():
            created = mw.create_shortcut_for_special_command(
                entry['cmd'],
                entry['cat']
            )
            if created:
                last = created

        if last:
            try:
                mw.load_categories()
                mw.select_item_by_path(last)
            except Exception:
                pass