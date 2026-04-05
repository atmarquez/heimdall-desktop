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
Pestaña de configuración del Servidor HTTP.

Este módulo define la clase `ServerConfigTab`, responsable de construir y
controlar la pestaña “Servidor” dentro del diálogo de Configuración.

Responsabilidades:
- Mostrar y editar la configuración del servidor HTTP integrado.
- Configurar opciones generales del servidor (puerto, interfaz, token).
- Configurar TLS (certificados, versiones mínimas).
- Configurar mecanismos de auditoría y throttling.
- Proporcionar acceso a diálogos avanzados (auditoría, tokens, etc.).

IMPORTANT:
    Esta clase NO arranca ni detiene el servidor directamente.
    Su responsabilidad es exclusivamente la gestión de la configuración.
"""

# ------------------------------------------------------------
# Resúmenes visuales (texto compacto de configuración)
# ------------------------------------------------------------

from ui.server.summaries import (
    server_opts_summary,
    tls_opts_summary,
    throttle_summary,
)

# ------------------------------------------------------------
# Diálogos de configuración avanzada
# ------------------------------------------------------------

from ui.server.dialogs import (
    TlsOptionsDialog,
    ServerOptionsDialog,
    ThrottleConfigDialog,
    AuditViewerDialog,
    TokenDialog,
)

# ------------------------------------------------------------
# Imports estándar y Qt
# ------------------------------------------------------------

from pathlib import Path
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QFileDialog

# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------

from logutils.setup import get_logger
LOGGER = get_logger()


class ServerConfigTab:
    """
    Controlador de la pestaña “Servidor” del diálogo de Configuración.

    Esta clase actúa como intermediario entre:
    - El diálogo principal de configuración.
    - Los widgets Qt que componen la pestaña del servidor.
    - Los diálogos secundarios de opciones avanzadas.

    Diseño:
    - No hereda directamente de QWidget.
    - Posee un widget raíz (`self.widget`) que se inserta en el tab.
    - Centraliza toda la lógica de UI relacionada con el servidor.

    NOTE:
        El estado se sincroniza siempre contra el diccionario `cfg`
        proporcionado por el diálogo principal.
    """

    def __init__(self, parent_dialog, cfg, server_opts_summary_fn, tls_opts_summary_fn):
        """
        Inicializa la pestaña de configuración del servidor.

        Args:
            parent_dialog (QDialog):
                Diálogo padre de configuración.
            cfg (dict):
                Diccionario de configuración actual de la aplicación.
            server_opts_summary_fn (callable):
                Función que genera el resumen textual de opciones del servidor.
            tls_opts_summary_fn (callable):
                Función que genera el resumen textual de opciones TLS.
        """
        self.parent = parent_dialog
        self.cfg = cfg

        # Funciones generadoras de resúmenes (inyectadas)
        self.server_opts_summary_fn = server_opts_summary_fn
        self.tls_opts_summary_fn = tls_opts_summary_fn

        # Widget raíz de la pestaña
        self.widget = QtWidgets.QWidget(parent_dialog)
        self.form = QtWidgets.QFormLayout(self.widget)

        # Construcción de la interfaz
        self._build_ui()

    def _build_ui(self):
        """
        Construye todos los widgets de la pestaña de configuración del servidor.

        Este método se encarga de:
        - Crear los controles de activación del servidor HTTP/HTTPS.
        - Configurar parámetros de red, seguridad (TLS), whitelist y extensiones.
        - Inicializar valores a partir del diccionario de configuración (`self.cfg`).
        - Construir secciones avanzadas (auditoría, token, backoff).
        - Ocultar o mostrar campos según el contexto y opciones disponibles.

        IMPORTANT:
            - Este método SOLO construye la interfaz gráfica.
            - NO guarda configuración en disco.
            - NO inicia ni detiene el servidor.
            - La aplicación de cambios se delega a otros métodos.
        """
        self.server_enabled_cb = QtWidgets.QCheckBox('Habilitar servidor', self.widget)
        self.server_enabled_cb.setObjectName('server_enabled_cb')
        self.server_enabled_cb.setChecked(bool(self.cfg.get('server_enabled', False)))
        self.form.addRow('', self.server_enabled_cb)

        # --------------------------------------------------
        # Puerto del servidor
        # --------------------------------------------------
        self.server_port_edit = QtWidgets.QLineEdit(self.widget)
        self.server_port_edit.setObjectName('server_port_edit')
        self.server_port_edit.setValidator(QtGui.QIntValidator(1, 65535, self.server_port_edit))
        try:
            _port = int(self.cfg.get('server_port', 8080) or 8080)
        except Exception as e:
            _port = 8080
        self.server_port_edit.setText(str(_port))
        self.form.addRow('Puerto de escucha:', self.server_port_edit)
        
        # --------------------------------------------------
        # Restricciones de acceso
        # --------------------------------------------------
        self.server_local_cb = QtWidgets.QCheckBox('Atender solo peticiones locales', self.widget)
        self.server_local_cb.setObjectName('server_local_cb')
        self.server_local_cb.setChecked(bool(self.cfg.get('server_local_only', True)))
        if hasattr(self, 'server_whitelist_cb'):
            self.server_whitelist_cb.setChecked(bool(self.cfg.get('server_whitelist_base', False)))

        # --------------------------------------------------
        # Inicialización defensiva de opciones TLS
        # --------------------------------------------------
        try:
            if hasattr(self, 'server_tls_enabled_cb'):
                self.server_tls_enabled_cb.setChecked(bool(self.cfg.get('server_tls_enabled', False)))
            if hasattr(self, 'server_tls_cert_edit'):
                self.server_tls_cert_edit.setText(self.cfg.get('server_tls_certfile', '') or '')
            if hasattr(self, 'server_tls_key_edit'):
                self.server_tls_key_edit.setText(self.cfg.get('server_tls_keyfile', '') or '')
            if hasattr(self, 'server_tls_minver_combo'):
                keys = getattr(self, '_server_tls_minver_keys', ['TLS1.2', 'TLS1.3'])
                mv = str(self.cfg.get('server_tls_min_version', 'TLS1.2') or 'TLS1.2').upper()
                try:
                    idx = keys.index(mv)
                except Exception as e:
                    idx = 0
                self.server_tls_minver_combo.setCurrentIndex(idx)
        except Exception as e:
            # Nunca romper la UI por errores defensivos
            LOGGER.exception('[auto] Exception capturada en ConfigDialog::__init__')

        # --------------------------------------------------
        # Extensiones permitidas
        # --------------------------------------------------
        try:
            if hasattr(self, 'server_exts_edit'):
                _exts = self.cfg.get('server_allowed_exts', None)
                if not _exts:
                    _exts = list(SERVER_ALLOWED_EXTS)
                if isinstance(_exts, str):
                    _exts = [e.strip() for e in _exts.split(',') if e.strip()]
                _exts_norm = sorted({(e if e.startswith('.') else '.' + e).lower() for e in _exts})
                self.server_exts_edit.setText(','.join(_exts_norm))
        except Exception as e:
            LOGGER.exception('[auto] Exception capturada en ConfigDialog::__init__')

        # --------------------------------------------------
        # Modo de notificaciones del servidor
        # --------------------------------------------------
        if hasattr(self, 'server_notify_combo'):
            keys = getattr(self, '_server_notify_keys', ['all', 'none', 'only_ok', 'only_errors'])
            _val = str(self.cfg.get('server_notify_mode', 'all'))
            try:
                _i = keys.index(_val)
            except Exception as e:
                _i = 0
            self.server_notify_combo.setCurrentIndex(_i)
        self.form.addRow('', self.server_local_cb)
        
        # --------------------------------------------------
        # Whitelist de carpeta base
        # --------------------------------------------------
        self.server_whitelist_cb = QtWidgets.QCheckBox('Whitelist carpeta base', self.widget)
        self.server_whitelist_cb.setObjectName('server_whitelist_cb')
        self.server_whitelist_cb.setChecked(bool(self.cfg.get('server_whitelist_base', False)))
        self.form.addRow('', self.server_whitelist_cb)
        
        # --------------------------------------------------
        # TLS / HTTPS
        # --------------------------------------------------
        self.server_tls_enabled_cb = QtWidgets.QCheckBox('Habilitar TLS (HTTPS)', self.widget)
        self.server_tls_enabled_cb.setChecked(bool(self.cfg.get('server_tls_enabled', False)))
        self.form.addRow('', self.server_tls_enabled_cb)
        self.server_tls_cert_edit = QtWidgets.QLineEdit(self.widget)
        self.server_tls_cert_edit.setText(self.cfg.get('server_tls_certfile', '') or '')
        btn_tls_cert = QtWidgets.QPushButton('Examinar…', self.widget)

        def _browse_cert():
            path, _ = QFileDialog.getOpenFileName(self, 'Seleccionar certificado (PEM/CRT)', str(Path.cwd()), 'Certificados (*.pem *.crt *.cer);;Todos (*.*)')
            if path:
                self.server_tls_cert_edit.setText(path)
        btn_tls_cert.clicked.connect(_browse_cert)
        row_cert = QtWidgets.QWidget(self.widget)
        _lc = QtWidgets.QHBoxLayout(row_cert)
        _lc.setContentsMargins(0, 0, 0, 0)
        _lc.addWidget(self.server_tls_cert_edit, 1)
        _lc.addWidget(btn_tls_cert)
        self.form.addRow('Certificado (PEM):', row_cert)
        self.server_tls_key_edit = QtWidgets.QLineEdit(self.widget)
        self.server_tls_key_edit.setText(self.cfg.get('server_tls_keyfile', '') or '')
        btn_tls_key = QtWidgets.QPushButton('Examinar…', self.widget)

        def _browse_key():
            path, _ = QFileDialog.getOpenFileName(self, 'Seleccionar clave privada (KEY/PEM)', str(Path.cwd()), 'Claves privadas (*.key *.pem);;Todos (*.*)')
            if path:
                self.server_tls_key_edit.setText(path)
        btn_tls_key.clicked.connect(_browse_key)
        row_key = QtWidgets.QWidget(self.widget)
        _lk = QtWidgets.QHBoxLayout(row_key)
        _lk.setContentsMargins(0, 0, 0, 0)
        _lk.addWidget(self.server_tls_key_edit, 1)
        _lk.addWidget(btn_tls_key)
        self.form.addRow('Clave privada:', row_key)
        self.server_tls_minver_combo = QtWidgets.QComboBox(self.widget)
        self._server_tls_minver_keys = ['TLS1.2', 'TLS1.3']
        self.server_tls_minver_combo.addItems(['TLS 1.2', 'TLS 1.3'])
        _curr_minv = str(self.cfg.get('server_tls_min_version', 'TLS1.2') or 'TLS1.2').upper()
        try:
            _idx = self._server_tls_minver_keys.index(_curr_minv)
        except Exception as e:
            _idx = 0
        self.server_tls_minver_combo.setCurrentIndex(_idx)
        self.form.addRow('Versión mínima TLS:', self.server_tls_minver_combo)
        self.server_exts_edit = QtWidgets.QLineEdit(self.widget)
        self.server_exts_edit.setObjectName('server_exts_edit')
        try:
            _exts = self.cfg.get('server_allowed_exts', None)
            if not _exts:
                _exts = list(SERVER_ALLOWED_EXTS)
            if isinstance(_exts, str):
                _exts = [e.strip() for e in _exts.split(',') if e.strip()]
            _exts_norm = sorted({(e if e.startswith('.') else '.' + e).lower() for e in _exts})
        except Exception as e:
            _exts_norm = sorted({e for e in SERVER_ALLOWED_EXTS})
        self.server_exts_edit.setText(','.join(_exts_norm))
        self.server_exts_edit.setPlaceholderText('.exe,.com,.bat,.cmd,.vbs,.ps1,.py')
        self.form.addRow('Extensiones permitidas:', self.server_exts_edit)
        note = QtWidgets.QLabel('Servidor HTTP/HTTPS. Soporta parámetros close=1 y silent=1.', self.widget)
        note.setWordWrap(True)
        self.form.addRow(note)

        def _hide_row_widget(_field_widget, _container_widget=None):
            try:
                _w = _container_widget if _container_widget is not None else _field_widget
                _lab = self.form.labelForField(_w)
                if _lab is not None:
                    _lab.setVisible(False)
                if _w is not None:
                    _w.setVisible(False)
            except Exception as e:
                LOGGER.exception('[auto] Exception capturada en ConfigDialog::__init__::_hide_row_widget')
        try:
            if hasattr(self, 'server_port_edit'):
                _hide_row_widget(self.server_port_edit)
            if hasattr(self, 'server_local_cb'):
                _hide_row_widget(self.server_local_cb)
            if hasattr(self, 'server_whitelist_cb'):
                _hide_row_widget(self.server_whitelist_cb)
            if hasattr(self, 'server_exts_edit'):
                _hide_row_widget(self.server_exts_edit)
            if hasattr(self, 'server_notify_combo'):
                _hide_row_widget(self.server_notify_combo)
        except Exception as e:
            LOGGER.exception('[auto] Exception capturada en ConfigDialog::__init__')
        try:
            if hasattr(self, 'server_tls_cert_edit'):
                _hide_row_widget(self.server_tls_cert_edit, self.server_tls_cert_edit.parent())
            if hasattr(self, 'server_tls_key_edit'):
                _hide_row_widget(self.server_tls_key_edit, self.server_tls_key_edit.parent())
            if hasattr(self, 'server_tls_minver_combo'):
                _hide_row_widget(self.server_tls_minver_combo)
        except Exception as e:
            LOGGER.exception('[auto] Exception capturada en ConfigDialog::__init__')
        self.server_opts_summary = QtWidgets.QLabel(self.server_opts_summary_fn(self.cfg), self.widget)
        btn_srv_opts = QtWidgets.QPushButton('Opciones del servidor…', self.widget)
        btn_srv_opts.clicked.connect(self._open_server_opts_dialog)
        _row_srv = QtWidgets.QWidget(self.widget)
        _ls = QtWidgets.QHBoxLayout(_row_srv)
        _ls.setContentsMargins(0, 0, 0, 0)
        _ls.addWidget(self.server_opts_summary, 1)
        _ls.addWidget(btn_srv_opts)
        self.form.addRow('Configuración de servidor:', _row_srv)
        self.tls_opts_summary = QtWidgets.QLabel(self.tls_opts_summary_fn(self.cfg), self.widget)
        btn_tls_opts = QtWidgets.QPushButton('Opciones TLS…', self.widget)
        btn_tls_opts.clicked.connect(self._open_tls_options_dialog)
        _row_tls = QtWidgets.QWidget(self.widget)
        _lt = QtWidgets.QHBoxLayout(_row_tls)
        _lt.setContentsMargins(0, 0, 0, 0)
        _lt.addWidget(self.tls_opts_summary, 1)
        _lt.addWidget(btn_tls_opts)
        self.form.addRow('TLS:', _row_tls)
        self.btn_server_audit = QtWidgets.QPushButton('Auditoría…', self.widget)
        self.btn_server_audit.clicked.connect(self._open_audit_viewer)
        self.form.addRow('Auditoría:', self.btn_server_audit)
        btn_token = QtWidgets.QPushButton('Calcular Token', self.widget)
        btn_token.clicked.connect(self._open_token_dialog)
        self.form.addRow('Token HMAC:', btn_token)
        try:
            self._th_params = {'window_sec': int(self.cfg.get('server_throttle_window_sec', 30) or 30), 'base_ms': int(self.cfg.get('server_throttle_base_ms', 100) or 100), 'max_ms': int(self.cfg.get('server_throttle_max_ms', 1000) or 1000), 'threshold': int(self.cfg.get('server_throttle_threshold', 3) or 3)}
            self.th_summary = QtWidgets.QLabel(throttle_summary(self._th_params), self.widget)
            btn_throttle = QtWidgets.QPushButton('Configurar backoff…', self.widget)
            btn_throttle.clicked.connect(self._open_throttle_dialog)
            row = QtWidgets.QWidget(self.widget)
            h = QtWidgets.QHBoxLayout(row)
            h.setContentsMargins(0, 0, 0, 0)
            h.addWidget(self.th_summary, 1)
            h.addWidget(btn_throttle)
            self.form.addRow('Backoff (errores):', row)
            example = QtWidgets.QLabel(self.widget)
            example.setTextFormat(QtCore.Qt.RichText)
            example.setWordWrap(True)
            example.setText('Ejemplo de llamada:<br><code>http(s)://127.0.0.1:8080/?path=C:\\Apps\\MiExe.exe&amp;close=1&amp;silent=0&amp;token=...</code><br><br><b>Parámetros:</b><br><code>close=1</code> → intenta cerrar la pestaña devolviendo una página con <code>window.close()</code> (el navegador puede bloquearlo).<br><code>silent=1</code> → devuelve <code>HTTP 204 No Content</code> y <code>Connection: close</code> (no muestra contenido).<br>Si ambos se especifican, <code>silent</code> tiene prioridad.')
            self.form.addRow(example)
            note2 = QtWidgets.QLabel(self.widget)
            note2.setText('Si activas "Whitelist carpeta base", la URL debe usar una ruta <b>relativa</b> respecto a la carpeta base configurada.')
            note2.setWordWrap(True)
            self.form.addRow(note2)
        except Exception as e:
            LOGGER.exception('[auto] Exception capturada en ConfigDialog::__init__')
            
    def _open_tls_options_dialog(self):
        """
        Abre el diálogo de configuración de opciones TLS.

        Permite configurar:
        - Certificado TLS.
        - Clave privada.
        - Versión mínima de TLS.

        Los valores se reflejan tanto en los widgets visibles
        como en el diccionario de configuración (`self.cfg`).

        NOTE:
            Este método es defensivo: todos los accesos a widgets
            y escritura de configuración están protegidos.

        Returns:
            None
        """
        try:
            widgets = {
                'cert': getattr(self, 'server_tls_cert_edit', None),
                'key': getattr(self, 'server_tls_key_edit', None),
                'minver': getattr(self, 'server_tls_minver_combo', None),
            }

            dlg = TlsOptionsDialog(
                self.parent,
                cfg=self.cfg,
                widgets=widgets
            )

            if dlg.exec() == QtWidgets.QDialog.Accepted:
                vals = dlg.values()

                # Actualizar widgets visibles
                try:
                    if widgets['cert'] is not None:
                        widgets['cert'].setText(
                            vals['server_tls_certfile']
                        )
                    if widgets['key'] is not None:
                        widgets['key'].setText(
                            vals['server_tls_keyfile']
                        )
                    if widgets['minver'] is not None:
                        keys = ['TLS1.2', 'TLS1.3']
                        try:
                            idx = keys.index(
                                vals['server_tls_min_version']
                            )
                        except Exception:
                            idx = 0
                        widgets['minver'].setCurrentIndex(idx)
                except Exception:
                    LOGGER.exception(
                        '[auto] Exception capturada en ConfigDialog::_open_tls_options_dialog'
                    )

                # Persistir valores en cfg
                try:
                    self.cfg['server_tls_certfile'] = vals['server_tls_certfile']
                    self.cfg['server_tls_keyfile'] = vals['server_tls_keyfile']
                    self.cfg['server_tls_min_version'] = vals['server_tls_min_version']
                except Exception:
                    LOGGER.exception(
                        '[auto] Exception capturada en ConfigDialog::_open_tls_options_dialog'
                    )

                # Actualizar resumen TLS
                try:
                    if hasattr(self, 'tls_opts_summary'):
                        self.tls_opts_summary.setText(
                            tls_opts_summary(self.cfg)
                        )
                except Exception:
                    LOGGER.exception(
                        '[auto] Exception capturada en ConfigDialog::_open_tls_options_dialog'
                    )
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en ConfigDialog::_open_tls_options_dialog'
            )

    def _open_audit_viewer(self):
        """
        Abre el visor de auditoría del servidor.

        Muestra los eventos registrados por el servidor HTTP
        (accesos, errores, ejecuciones, etc.).

        Returns:
            None
        """
        try:
            dlg = AuditViewerDialog(self.parent)
            dlg.exec()
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en ConfigDialog::_open_audit_viewer'
            )

    def _open_token_dialog(self):
        """
        Abre el diálogo de gestión del token de autenticación.

        Permite:
        - Activar o desactivar autenticación por token.
        - Generar o modificar la clave protegida.

        Returns:
            None
        """
        try:
            dlg = TokenDialog(self.parent, cfg=self.cfg)
            if dlg.exec() == QtWidgets.QDialog.Accepted:
                vals = dlg.persisted_values()
                self.cfg['server_token_enabled'] = bool(
                    vals.get('server_token_enabled', False)
                )
                self.cfg['server_token_key_protected'] = (
                    vals.get('server_token_key_protected', '')
                )
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en ConfigDialog::_open_token_dialog'
            )

    def _open_throttle_dialog(self):
        """
        Abre el diálogo de configuración de throttling / backoff.

        Permite definir:
        - Ventana temporal.
        - Retardo base.
        - Retardo máximo.
        - Umbral de penalización.

        Returns:
            None
        """
        try:
            dlg = ThrottleConfigDialog(
                self.parent,
                values=self._th_params
            )
            if dlg.exec() == QtWidgets.QDialog.Accepted:
                self._th_params = dlg.result_values()
                self.th_summary.setText(
                    throttle_summary(self._th_params)
                )

                # Persistir en cfg
                self.cfg['server_throttle_window_sec'] = int(
                    self._th_params['window_sec']
                )
                self.cfg['server_throttle_base_ms'] = int(
                    self._th_params['base_ms']
                )
                self.cfg['server_throttle_max_ms'] = int(
                    self._th_params['max_ms']
                )
                self.cfg['server_throttle_threshold'] = int(
                    self._th_params['threshold']
                )
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en ConfigDialog::_open_throttle_dialog'
            )

    def _open_server_opts_dialog(self):
        """
        Abre el diálogo de opciones generales del servidor HTTP.

        Incluye:
        - Puerto.
        - Modo solo local.
        - Whitelist de carpeta base.
        - Extensiones permitidas.
        - Modo de notificaciones.

        Returns:
            None
        """
        try:
            widgets = {
                'port': getattr(self, 'server_port_edit', None),
                'local': getattr(self, 'server_local_cb', None),
                'wl': getattr(self, 'server_whitelist_cb', None),
                'exts': getattr(self, 'server_exts_edit', None),
                'notify': getattr(self, 'server_notify_combo', None),
            }

            dlg = ServerOptionsDialog(
                self.parent,
                cfg=self.cfg,
                widgets=widgets
            )

            if dlg.exec() == QtWidgets.QDialog.Accepted:
                vals = dlg.values()

                # Actualizar widgets
                try:
                    if widgets['port'] is not None:
                        widgets['port'].setText(
                            str(vals['server_port'])
                        )
                    if widgets['local'] is not None:
                        widgets['local'].setChecked(
                            bool(vals['server_local_only'])
                        )
                    if widgets['wl'] is not None:
                        widgets['wl'].setChecked(
                            bool(vals['server_whitelist_base'])
                        )
                    if widgets['exts'] is not None:
                        widgets['exts'].setText(
                            ','.join(vals['server_allowed_exts'])
                        )
                    if widgets['notify'] is not None:
                        keys = ['all', 'none', 'only_ok', 'only_errors']
                        try:
                            idx = keys.index(
                                vals['server_notify_mode']
                            )
                        except Exception:
                            idx = 0
                        widgets['notify'].setCurrentIndex(idx)
                except Exception:
                    LOGGER.exception(
                        '[auto] Exception capturada en ConfigDialog::_open_server_opts_dialog'
                    )

                # Persistir valores en cfg
                try:
                    self.cfg['server_port'] = int(vals['server_port'])
                    self.cfg['server_local_only'] = bool(
                        vals['server_local_only']
                    )
                    self.cfg['server_whitelist_base'] = bool(
                        vals['server_whitelist_base']
                    )
                    self.cfg['server_allowed_exts'] = list(
                        vals['server_allowed_exts']
                    )
                    self.cfg['server_notify_mode'] = str(
                        vals['server_notify_mode']
                    )
                except Exception:
                    LOGGER.exception(
                        '[auto] Exception capturada en ConfigDialog::_open_server_opts_dialog'
                    )

                # Actualizar resumen visual
                try:
                    if hasattr(self, 'server_opts_summary'):
                        self.server_opts_summary.setText(
                            server_opts_summary(self.cfg)
                        )
                except Exception:
                    LOGGER.exception(
                        '[auto] Exception capturada en ConfigDialog::_open_server_opts_dialog'
                    )
        except Exception:
            LOGGER.exception(
                '[auto] Exception capturada en ConfigDialog::_open_server_opts_dialog'
            )

    def apply(self):
        """
        Aplica los valores actuales de los widgets del servidor a `self.cfg`.

        IMPORTANT:
            Este método NO guarda en disco.
            Solo sincroniza el estado del diálogo con el diccionario cfg.

        Returns:
            None
        """
        # Habilitado
        if hasattr(self, 'server_enabled_cb'):
            self.cfg['server_enabled'] = (
                self.server_enabled_cb.isChecked()
            )

        # Puerto
        if hasattr(self, 'server_port_edit'):
            try:
                self.cfg['server_port'] = int(
                    self.server_port_edit.text()
                )
            except Exception:
                pass

        # Solo local
        if hasattr(self, 'server_local_cb'):
            self.cfg['server_local_only'] = (
                self.server_local_cb.isChecked()
            )

        # Whitelist de carpeta base
        if hasattr(self, 'server_whitelist_cb'):
            self.cfg['server_whitelist_base'] = (
                self.server_whitelist_cb.isChecked()
            )

        # Extensiones permitidas (CRÍTICO)
        if hasattr(self, 'server_exts_edit'):
            raw = self.server_exts_edit.text().strip()
            if raw:
                parts = [
                    p.strip().lower()
                    for p in raw.replace(';', ',').split(',')
                    if p.strip()
                ]
                exts = sorted(
                    {(p if p.startswith('.') else '.' + p) for p in parts}
                )
            else:
                exts = []

            self.cfg['server_allowed_exts'] = list(exts)

        # Modo de notificaciones
        if hasattr(self, 'server_notify_combo'):
            keys = ['all', 'none', 'only_ok', 'only_errors']
            idx = int(self.server_notify_combo.currentIndex())
            if 0 <= idx < len(keys):
                self.cfg['server_notify_mode'] = keys[idx]

    def collect_config(self) -> dict:
        """
        Devuelve un diccionario con la configuración del servidor
        recogida desde los widgets.

        Returns:
            dict
        """
        try:
            notify_idx = int(
                self.server_notify_combo.currentIndex()
            )
        except Exception:
            notify_idx = 0

        notify_keys = ['all', 'none', 'only_ok', 'only_errors']
        notify_mode = (
            notify_keys[notify_idx]
            if notify_idx < len(notify_keys)
            else 'all'
        )

        return {
            'server_enabled': bool(self.server_enabled_cb.isChecked()),
            'server_port': int(self.server_port_edit.text() or 8080),
            'server_local_only': bool(self.server_local_cb.isChecked()),
            'server_whitelist_base': bool(self.server_whitelist_cb.isChecked()),
            'server_notify_mode': notify_mode,
            'server_allowed_exts': [
                s.strip().lower()
                for s in (self.server_exts_edit.text() or '').split(',')
                if s.strip()
            ],
        }

    def gather(self) -> dict:
        """
        Recoge TODA la configuración del servidor desde la interfaz.

        Incluye:
        - Opciones generales.
        - TLS.
        - Throttling.

        IMPORTANT:
            NO guarda en disco.

        Returns:
            dict
        """
        notify_keys = ['all', 'none', 'only_ok', 'only_errors']

        try:
            notify_idx = int(
                self.server_notify_combo.currentIndex()
            )
        except Exception:
            notify_idx = 0

        notify_mode = (
            notify_keys[notify_idx]
            if 0 <= notify_idx < len(notify_keys)
            else 'all'
        )

        # Extensiones
        raw_exts = (self.server_exts_edit.text() or '').strip()
        if raw_exts:
            exts = sorted(
                {
                    (e if e.startswith('.') else '.' + e)
                    for e in (
                        p.strip().lower()
                        for p in raw_exts.replace(';', ',').split(',')
                    )
                    if e
                }
            )
        else:
            exts = []

        return {
            'server_enabled': bool(self.server_enabled_cb.isChecked()),
            'server_port': int(self.server_port_edit.text() or 8080),
            'server_local_only': bool(self.server_local_cb.isChecked()),
            'server_whitelist_base': bool(self.server_whitelist_cb.isChecked()),
            'server_notify_mode': notify_mode,
            'server_allowed_exts': list(exts),
            'server_tls_enabled': bool(
                self.server_tls_enabled_cb.isChecked()
            ),
            'server_tls_certfile': self.server_tls_cert_edit.text().strip(),
            'server_tls_keyfile': self.server_tls_key_edit.text().strip(),
            'server_tls_min_version': (
                self._server_tls_minver_keys[
                    self.server_tls_minver_combo.currentIndex()
                ]
            ),
            'server_throttle_window_sec': int(
                self._th_params['window_sec']
            ),
            'server_throttle_base_ms': int(
                self._th_params['base_ms']
            ),
            'server_throttle_max_ms': int(
                self._th_params['max_ms']
            ),
            'server_throttle_threshold': int(
                self._th_params['threshold']
            ),
        }

    def apply_to_cfg(self, cfg: dict):
        """
        Aplica la configuración del logging al diccionario de configuración global.

        Este método actualiza el diccionario `cfg` con los valores recogidos
        desde la interfaz gráfica mediante el método `gather()`.

        Args:
            cfg: Diccionario de configuración global de la aplicación
                 que será actualizado con las opciones de logging.

        IMPORTANT:
            - Este método NO guarda la configuración en disco.
            - La persistencia debe realizarse desde una capa superior
              (por ejemplo, el diálogo principal de Configuración).
        """
        cfg.update(self.gather())
