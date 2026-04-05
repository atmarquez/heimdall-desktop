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
Diálogos de configuración del servidor HTTP.

Este módulo agrupa todos los diálogos relacionados con la configuración
avanzada del servidor integrado en la aplicación.

Clases incluidas:
- ThrottleConfigDialog: Configuración del sistema de throttling/backoff.
- ServerOptionsDialog: Opciones generales del servidor (puerto, red, filtros).
- TlsOptionsDialog: Configuración de TLS (certificados y versión mínima).
- AuditViewerDialog: Visualizador de registros de auditoría del servidor.
- TokenDialog: Gestión de autenticación mediante token compartido.

IMPORTANT:
    Ninguno de estos diálogos arranca, detiene o reinicia el servidor.
    Su función es exclusivamente editar y mostrar opciones, dejando la
    aplicación efectiva a otros componentes.

NOTE:
    Todos los diálogos están diseñados para ser tolerantes a errores
    (código defensivo) y minimizar el impacto de configuraciones incorrectas.
"""

# ------------------------------------------------------------
# Imports Qt / UI
# ------------------------------------------------------------

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QLabel, QPushButton,
    QDialogButtonBox, QCheckBox, QSpinBox,
    QListWidget, QFileDialog
)

# ------------------------------------------------------------
# Utilidades estándar
# ------------------------------------------------------------

from pathlib import Path
import os
import json
import tempfile
import subprocess
import shutil

# ------------------------------------------------------------
# Helpers de UI
# ------------------------------------------------------------

from ui.helpers import HelpableDialogMixin
from ui.help import open_help_page
from ui.roles import ROLE_PATH, ROLE_IS_DIR

# ------------------------------------------------------------
# Configuración y logging
# ------------------------------------------------------------

from config.service import app_dir, save_config
from logutils.memory import log_latest, log_count

# ------------------------------------------------------------
# Auditoría del servidor
# ------------------------------------------------------------

from server.audit import audit_latest, audit_count

# ------------------------------------------------------------
# Seguridad y criptografía (tokens / DPAPI)
# ------------------------------------------------------------

from server.security import (
    dpapi_protect_user,
    dpapi_unprotect_user,
    generate_secret_b64url,
    compute_hmac_hex,
)


class ThrottleConfigDialog(HelpableDialogMixin, QtWidgets.QDialog):
    """
    Diálogo de configuración del backoff (throttle) del servidor.

    Permite ajustar cómo el servidor retrasa respuestas tras múltiples
    errores provenientes del mismo origen (IP / agente).

    Parámetros configurables:
    - Ventana de conteo de errores (en segundos).
    - Retardo base aplicado al superar el umbral.
    - Retardo máximo permitido.
    - Umbral de errores a partir del cual se penaliza.

    NOTE:
        Este diálogo solo recopila y valida valores numéricos.
        La aplicación real de estos parámetros se realiza en el servidor.
    """

    #: Tema de ayuda contextual asociado a este diálogo
    help_topic = 'server_throttle'

    def __init__(self, parent=None, values=None):
        """
        Inicializa el diálogo de configuración del backoff del servidor.

        Args:
            parent: Widget padre (normalmente MainWindow o un diálogo de configuración).
            values: Diccionario opcional con valores iniciales/preconfigurados
                    para los controles del formulario.
        """
        super().__init__(parent)
        self.setWindowTitle('Configurar backoff del servidor')

        # Copia defensiva de los valores iniciales
        vals = (values or {}).copy()

        lay = QtWidgets.QVBoxLayout(self)

        # --------------------------------------------------
        # Texto informativo
        # --------------------------------------------------
        info = QtWidgets.QLabel(
            'Estas opciones controlan cómo se retrasa la respuesta tras varios '
            'errores de un mismo origen (IP/Agente):\n'
            '• Ventana de conteo de errores (s): intervalo de tiempo en el que se '
            'acumulan errores por IP/UA.\n'
            '• Retardo base (ms): retraso inicial aplicado al alcanzar el umbral.\n'
            '• Retardo máximo (ms): límite superior del retraso aplicado.\n'
            '• Umbral de errores: número de errores en ventana a partir del cual '
            'empieza a aplicarse el retraso.'
        )
        info.setWordWrap(True)
        lay.addWidget(info)

        # --------------------------------------------------
        # Formulario de parámetros
        # --------------------------------------------------
        form = QtWidgets.QFormLayout()

        self.win_sb = QtWidgets.QSpinBox(self)
        self.win_sb.setRange(1, 3600)
        self.win_sb.setValue(int(vals.get('window_sec', 30) or 30))

        self.base_sb = QtWidgets.QSpinBox(self)
        self.base_sb.setRange(0, 10000)
        self.base_sb.setValue(int(vals.get('base_ms', 100) or 100))

        self.max_sb = QtWidgets.QSpinBox(self)
        self.max_sb.setRange(0, 60000)
        self.max_sb.setValue(int(vals.get('max_ms', 1000) or 1000))

        self.thr_sb = QtWidgets.QSpinBox(self)
        self.thr_sb.setRange(0, 100)
        self.thr_sb.setValue(int(vals.get('threshold', 3) or 3))

        form.addRow('Ventana de conteo de errores (s):', self.win_sb)
        form.addRow('Retardo base (ms):', self.base_sb)
        form.addRow('Retardo máximo (ms):', self.max_sb)
        form.addRow('Umbral de errores antes de penalizar:', self.thr_sb)

        lay.addLayout(form)

        # --------------------------------------------------
        # Botonera inferior
        # --------------------------------------------------
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            self
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        # Botón de ayuda contextual
        self._install_help_button(btns)

        lay.addWidget(btns)

    def result_values(self):
        """
        Devuelve los valores configurados en el formulario.

        Returns:
            Diccionario con la configuración de backoff:
            - window_sec
            - base_ms
            - max_ms
            - threshold
        """
        return {
            'window_sec': int(self.win_sb.value()),
            'base_ms': int(self.base_sb.value()),
            'max_ms': int(self.max_sb.value()),
            'threshold': int(self.thr_sb.value()),
        }


class ServerOptionsDialog(HelpableDialogMixin, QtWidgets.QDialog):
    """
    Diálogo de opciones del servidor HTTP/HTTPS.

    Permite configurar los parámetros generales del servidor:
    - Puerto de escucha.
    - Alcance (solo local o accesible desde red).
    - Uso de whitelist de carpeta base.
    - Extensiones de archivos permitidas.
    - Política de notificaciones del servidor.

    NOTE:
        Este diálogo no aplica los cambios directamente.
        Simplemente devuelve los valores seleccionados para que
        sean procesados y persistidos por capas superiores.
    """

    #: Tema de ayuda contextual asociado a este diálogo
    help_topic = 'server_options'

    def __init__(self, parent=None, cfg=None, widgets=None):
        """
        Inicializa el diálogo de opciones del servidor.

        Args:
            parent: Widget padre (normalmente MainWindow o un diálogo de configuración).
            cfg: Diccionario de configuración actual del servidor.
            widgets: Diccionario opcional con referencias a widgets existentes
                     (usado para sincronizar valores ya mostrados en otras vistas).

        IMPORTANT:
            - Se priorizan los valores de `widgets` si están disponibles.
            - `cfg` actúa como respaldo si no hay widgets asociados.
            - Siempre se trabaja con copias defensivas.
        """
        QtWidgets.QDialog.__init__(self, parent)
        self.setWindowTitle('Opciones del servidor')

        # Copia defensiva de la configuración
        self.cfg = (cfg or {}).copy()

        # Widgets externos (si existen) para sincronización
        self.widgets = widgets or {}

        lay = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        # --------------------------------------------------
        # Puerto de escucha
        # --------------------------------------------------
        self.port_edit = QtWidgets.QLineEdit(self)
        self.port_edit.setValidator(
            QtGui.QIntValidator(1, 65535, self.port_edit)
        )

        _port = 8080
        try:
            if self.widgets.get('port') is not None:
                _port = int(self.widgets['port'].text() or '8080')
            else:
                _port = int(self.cfg.get('server_port', 8080) or 8080)
        except Exception:
            # Fallback seguro ante errores de conversión
            _port = 8080

        self.port_edit.setText(str(_port))
        form.addRow('Puerto de escucha:', self.port_edit)

        # --------------------------------------------------
        # Alcance del servidor
        # --------------------------------------------------
        self.local_cb = QtWidgets.QCheckBox(
            'Atender solo peticiones locales',
            self
        )
        try:
            _local = (
                bool(self.widgets.get('local').isChecked())
                if self.widgets.get('local') is not None
                else bool(self.cfg.get('server_local_only', True))
            )
        except Exception:
            _local = bool(self.cfg.get('server_local_only', True))

        self.local_cb.setChecked(_local)
        form.addRow('', self.local_cb)

        # --------------------------------------------------
        # Whitelist de carpeta base
        # --------------------------------------------------
        self.wl_cb = QtWidgets.QCheckBox(
            'Whitelist carpeta base',
            self
        )
        try:
            _wl = (
                bool(self.widgets.get('wl').isChecked())
                if self.widgets.get('wl') is not None
                else bool(self.cfg.get('server_whitelist_base', False))
            )
        except Exception:
            _wl = bool(self.cfg.get('server_whitelist_base', False))

        self.wl_cb.setChecked(_wl)
        form.addRow('', self.wl_cb)

        # --------------------------------------------------
        # Extensiones permitidas
        # --------------------------------------------------
        self.exts_edit = QtWidgets.QLineEdit(self)
        exts_placeholder = '.exe,.com,.bat,.cmd,.vbs,.ps1,.py'
        self.exts_edit.setPlaceholderText(exts_placeholder)

        try:
            raw_exts = ''
            w_ext = self.widgets.get('exts')

            if w_ext is not None:
                raw_exts = w_ext.text().strip()
            else:
                _exts = self.cfg.get('server_allowed_exts', None)
                if not _exts:
                    _exts = list(SERVER_ALLOWED_EXTS)
                if isinstance(_exts, str):
                    _exts = [e.strip() for e in _exts.split(',') if e.strip()]
                _exts_norm = sorted({
                    (e if e.startswith('.') else '.' + e).lower()
                    for e in _exts
                })
                raw_exts = ','.join(_exts_norm)
        except Exception:
            # Fallback defensivo: usar placeholder por defecto
            raw_exts = exts_placeholder

        self.exts_edit.setText(raw_exts)
        form.addRow('Extensiones permitidas:', self.exts_edit)

        # --------------------------------------------------
        # Política de notificaciones
        # --------------------------------------------------
        self.notify_combo = QtWidgets.QComboBox(self)
        self._notify_keys = ['all', 'none', 'only_ok', 'only_errors']
        self.notify_combo.addItems([
            'Todas las notificaciones',
            'Ninguna notificación',
            'Solo peticiones correctas',
            'Solo peticiones con error'
        ])

        try:
            current = None
            w_nc = self.widgets.get('notify')

            if w_nc is not None:
                idx = int(w_nc.currentIndex())
                current = (
                    self._notify_keys[idx]
                    if 0 <= idx < len(self._notify_keys)
                    else 'all'
                )
            else:
                current = str(
                    self.cfg.get('server_notify_mode', 'all')
                    or 'all'
                )

            idx = (
                self._notify_keys.index(current)
                if current in self._notify_keys
                else 0
            )
        except Exception:
            idx = 0

        self.notify_combo.setCurrentIndex(idx)
        form.addRow('Notificaciones del servidor:', self.notify_combo)

        lay.addLayout(form)

        # --------------------------------------------------
        # Botonera inferior
        # --------------------------------------------------
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok
            | QtWidgets.QDialogButtonBox.Cancel,
            self
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        # Botón de ayuda contextual
        self._install_help_button(btns)

        lay.addWidget(btns)

    def values(self):
        """
        Devuelve los valores configurados en el diálogo.

        Returns:
            Diccionario con las opciones del servidor:
            - server_port
            - server_local_only
            - server_whitelist_base
            - server_allowed_exts
            - server_notify_mode

        NOTE:
            Este método normaliza extensiones y es tolerante
            a errores de entrada del usuario.
        """
        try:
            import re as _re
            raw = self.exts_edit.text().strip()

            if raw:
                parts = [
                    s for s in _re.split('[;,\\s]+', raw)
                    if s
                ]
                norm_exts = sorted({
                    (p if p.startswith('.') else '.' + p).lower()
                    for p in parts
                })
            else:
                norm_exts = list(SERVER_ALLOWED_EXTS)

        except Exception:
            # Fallback defensivo ante fallos de normalización
            norm_exts = list(SERVER_ALLOWED_EXTS)

        return {
            'server_port': int(self.port_edit.text() or '8080'),
            'server_local_only': bool(self.local_cb.isChecked()),
            'server_whitelist_base': bool(self.wl_cb.isChecked()),
            'server_allowed_exts': norm_exts,
            'server_notify_mode': (
                self._notify_keys[self.notify_combo.currentIndex()]
                if 0 <= self.notify_combo.currentIndex() < len(self._notify_keys)
                else 'all'
            ),
        }


class TlsOptionsDialog(HelpableDialogMixin, QtWidgets.QDialog):
    """
    Diálogo de configuración de opciones TLS del servidor.

    Permite configurar:
    - Certificado TLS (PEM/CRT).
    - Clave privada asociada.
    - Versión mínima de TLS permitida.
    - Generación automática de certificado local autofirmado.

    NOTE:
        Este diálogo recopila y valida rutas/configuración TLS,
        pero la activación real del TLS ocurre en el servidor.
    """

    #: Tema de ayuda contextual asociado a este diálogo
    help_topic = 'tls_options'

    def __init__(self, parent=None, cfg=None, widgets=None):
        """
        Inicializa el diálogo de opciones TLS.

        Args:
            parent: Widget padre (normalmente MainWindow o diálogo de configuración).
            cfg: Diccionario de configuración actual del servidor.
            widgets: Diccionario opcional con referencias a widgets externos
                     para sincronizar valores ya mostrados en otras vistas.

        IMPORTANT:
            - Se priorizan valores existentes en `widgets` si están disponibles.
            - `cfg` actúa como respaldo.
            - Siempre se trabaja con copias defensivas.
        """
        super().__init__(parent)
        self.setWindowTitle('Opciones TLS')

        # Copia defensiva de la configuración
        self.cfg = (cfg or {}).copy()

        # Widgets externos opcionales para sincronización
        self.widgets = widgets or {}

        lay = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()

        # --------------------------------------------------
        # Certificado TLS
        # --------------------------------------------------
        self.cert_edit = QtWidgets.QLineEdit(self)
        _cert = ''
        try:
            w_ce = self.widgets.get('cert')
            if w_ce is not None:
                _cert = w_ce.text().strip()
            else:
                _cert = self.cfg.get('server_tls_certfile', '') or ''
        except Exception:
            _cert = ''

        self.cert_edit.setText(_cert)

        btn_cert = QtWidgets.QPushButton('Examinar…', self)

        def _b_cert():
            """
            Abre un diálogo para seleccionar el certificado TLS.
            """
            path, _ = QFileDialog.getOpenFileName(
                self,
                'Seleccionar certificado (PEM/CRT)',
                str(Path.cwd()),
                'Certificados (*.pem *.crt *.cer);;Todos (*.*)'
            )
            if path:
                self.cert_edit.setText(path)

        btn_cert.clicked.connect(_b_cert)

        row_cert = QtWidgets.QWidget(self)
        lc = QtWidgets.QHBoxLayout(row_cert)
        lc.setContentsMargins(0, 0, 0, 0)
        lc.addWidget(self.cert_edit, 1)
        lc.addWidget(btn_cert)
        form.addRow('Certificado (PEM):', row_cert)

        # --------------------------------------------------
        # Clave privada TLS
        # --------------------------------------------------
        self.key_edit = QtWidgets.QLineEdit(self)
        _key = ''
        try:
            w_ke = self.widgets.get('key')
            if w_ke is not None:
                _key = w_ke.text().strip()
            else:
                _key = self.cfg.get('server_tls_keyfile', '') or ''
        except Exception:
            _key = ''

        self.key_edit.setText(_key)

        btn_key = QtWidgets.QPushButton('Examinar…', self)

        def _b_key():
            """
            Abre un diálogo para seleccionar la clave privada TLS.
            """
            path, _ = QFileDialog.getOpenFileName(
                self,
                'Seleccionar clave privada (KEY/PEM)',
                str(Path.cwd()),
                'Claves privadas (*.key *.pem);;Todos (*.*)'
            )
            if path:
                self.key_edit.setText(path)

        btn_key.clicked.connect(_b_key)

        row_key = QtWidgets.QWidget(self)
        lk = QtWidgets.QHBoxLayout(row_key)
        lk.setContentsMargins(0, 0, 0, 0)
        lk.addWidget(self.key_edit, 1)
        lk.addWidget(btn_key)
        form.addRow('Clave privada:', row_key)

        # --------------------------------------------------
        # Versión mínima TLS
        # --------------------------------------------------
        self.minver_combo = QtWidgets.QComboBox(self)
        self._minver_keys = ['TLS1.2', 'TLS1.3']
        self.minver_combo.addItems(['TLS 1.2', 'TLS 1.3'])

        try:
            current = None
            w_mv = self.widgets.get('minver')

            if w_mv is not None:
                idx = int(w_mv.currentIndex())
                current = (
                    self._minver_keys[idx]
                    if 0 <= idx < len(self._minver_keys)
                    else 'TLS1.2'
                )
            else:
                current = str(
                    self.cfg.get('server_tls_min_version', 'TLS1.2')
                    or 'TLS1.2'
                ).upper()

            idx = (
                self._minver_keys.index(current)
                if current in self._minver_keys
                else 0
            )
        except Exception:
            idx = 0

        self.minver_combo.setCurrentIndex(idx)
        form.addRow('Versión mínima TLS:', self.minver_combo)

        # --------------------------------------------------
        # Generación de certificado local autofirmado
        # --------------------------------------------------
        self.btn_generate_cert = QtWidgets.QPushButton(
            'Generar certificado local',
            self
        )
        self.btn_generate_cert.setToolTip(
            'Genera un certificado autofirmado (localhost) y su '
            'clave privada en formato PEM dentro de resources/ssl/.'
        )
        self.btn_generate_cert.clicked.connect(
            self._on_generate_local_cert
        )
        form.addRow('Certificado local:', self.btn_generate_cert)

        lay.addLayout(form)

        # --------------------------------------------------
        # Botonera inferior
        # --------------------------------------------------
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok
            | QtWidgets.QDialogButtonBox.Cancel,
            self
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        # Botón de ayuda contextual
        self._install_help_button(btns)

        lay.addWidget(btns)

    def values(self):
        """
        Devuelve los valores configurados en el diálogo.

        Returns:
            Diccionario con opciones TLS:
            - server_tls_certfile
            - server_tls_keyfile
            - server_tls_min_version
        """
        return {
            'server_tls_certfile': self.cert_edit.text().strip(),
            'server_tls_keyfile': self.key_edit.text().strip(),
            'server_tls_min_version': (
                self._minver_keys[self.minver_combo.currentIndex()]
                if 0 <= self.minver_combo.currentIndex() < len(self._minver_keys)
                else 'TLS1.2'
            ),
        }



    def _on_generate_local_cert(self):
        """
        Genera un certificado TLS autofirmado para localhost
        y actualiza automáticamente los campos del formulario.

        Estrategia:
        - Intenta usar PowerShell 7 (pwsh) si está disponible.
        - Si no, usa Windows PowerShell 5.1 con construcción ASN.1 pura.
        - Genera cert.pem y key.pem en resources/ssl/.
        - Actualiza la configuración y la UI.

        WARNING:
            - Esta acción elimina previamente el certificado y clave actuales.
            - Requiere PowerShell y permisos adecuados en el sistema.
        """
        ...
        """Genera un certificado autofirmado (localhost) y actualiza los campos.
        Auto-detección: usa PowerShell 7 (pwsh) si está disponible; si no, Windows PowerShell 5.1 con construcción ASN.1 en PowerShell puro (sin C#).
        Pregunta confirmación y elimina el certificado/clave actuales antes de regenerar.
        """
        try:
            
            # --------------------------------------------------
            # Confirmación explícita del usuario
            # --------------------------------------------------
            reply = QtWidgets.QMessageBox.question(
                self,
                'Generar certificado',
                'Esto eliminará el certificado actual y creará uno nuevo para "localhost".\n\n¿Quieres continuar?',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return

            # --------------------------------------------------
            # Resolver rutas absolutas de certificados existentes
            # --------------------------------------------------
            def _resolve(p):
                """
                Resuelve una ruta a Path absoluto.

                - Permite rutas relativas (se resuelven desde app_dir).
                - Devuelve None si no hay valor.
                """
                from pathlib import Path as _P
                if not p:
                    return None
                pp = _P(p)
                if not pp.is_absolute():
                    try:
                        pp = (app_dir() / pp).resolve()
                    except Exception:
                        pp = pp.resolve()
                return pp

            # --------------------------------------------------
            # Eliminar certificado/clave previos si existen
            # (operación defensiva, errores ignorados)
            # --------------------------------------------------
            for current in (self.cert_edit.text().strip(), self.key_edit.text().strip()):
                try:
                    rp = _resolve(current)
                    if rp and rp.exists():
                        rp.unlink(missing_ok=True)
                except Exception:
                    pass

            import shutil, subprocess, tempfile, os
            from pathlib import Path as _P

            _appdir = app_dir()
            
            # Directorio de salida fijo: resources/ssl
            out_dir = _appdir / 'resources' / 'ssl'
            out_dir.mkdir(parents=True, exist_ok=True)
            cert_path = out_dir / 'cert.pem'
            key_path = out_dir / 'key.pem'

            # --------------------------------------------------
            # Detección automática de motores PowerShell
            # ------------------------------------------------
            pwsh = shutil.which('pwsh') or shutil.which('pwsh.exe')
            winps = shutil.which('powershell') or shutil.which('powershell.exe')

            # --------------------------------------------------
            # PowerShell 7+ (Core): ExportPkcs8PrivateKey disponible
            # -------------------------------------------------
            if pwsh:
                psexe = pwsh
                # Script para PowerShell 7+ (Core): usa ExportPkcs8PrivateKey directamente
                ps_script = r"""
param([string]$OutDir)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }
$certPath = Join-Path $OutDir 'cert.pem'
$keyPath = Join-Path $OutDir 'key.pem'
$dns = 'localhost'
$cert = New-SelfSignedCertificate -DnsName $dns -CertStoreLocation 'Cert:\CurrentUser\My' -KeyExportPolicy Exportable -KeyAlgorithm RSA -KeyLength 2048 -NotAfter (Get-Date).AddYears(3) -FriendlyName "LocalDev-$dns"
function Write-Pem([byte[]]$der, [string]$header, [string]$footer, [string]$path) {
  $b64 = [Convert]::ToBase64String($der)
  $sb = [System.Text.StringBuilder]::new()
  [void]$sb.AppendLine($header)
  for ($i=0; $i -lt $b64.Length; $i+=64) {
    $len = [Math]::Min(64, $b64.Length - $i)
    [void]$sb.AppendLine($b64.Substring($i, $len))
  }
  [void]$sb.AppendLine($footer)
  [System.IO.File]::WriteAllText($path, $sb.ToString(), [System.Text.Encoding]::ASCII)
}
$derCert = $cert.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert)
Write-Pem -der $derCert -header '-----BEGIN CERTIFICATE-----' -footer '-----END CERTIFICATE-----' -path $certPath
$rsa = $null
try { $rsa = $cert.GetRSAPrivateKey() } catch {}
if ($null -eq $rsa) { try { $rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($cert) } catch {} }
if ($null -eq $rsa) { throw 'No se pudo obtener la clave privada RSA del certificado.' }
$derKey = $rsa.ExportPkcs8PrivateKey()
Write-Pem -der $derKey -header '-----BEGIN PRIVATE KEY-----' -footer '-----END PRIVATE KEY-----' -path $keyPath
Write-Output 'OK'
"""
            else:
                
                # --------------------------------------------------
                # Windows PowerShell 5.1 (sin pwsh)
                # Construcción manual de PKCS#8 en PowerShell puro
                # ------------------------------------------
                if not winps:
                    QtWidgets.QMessageBox.warning(self, 'PowerShell no encontrado', 'No se encontró ninguna instalación de PowerShell.\n\nInstala PowerShell 7 (recomendado) o asegúrate de que Windows PowerShell 5.1 está disponible.')
                    return
                psexe = winps
                # Script para Windows PowerShell 5.1 (PowerShell puro, sin C#) que construye PKCS#8
                ps_script = r"""
param([string]$OutDir)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }
$certPath = Join-Path $OutDir 'cert.pem'
$keyPath = Join-Path $OutDir 'key.pem'
$dns = 'localhost'
$cert = New-SelfSignedCertificate -DnsName $dns -CertStoreLocation 'Cert:\CurrentUser\My' -KeyExportPolicy Exportable -KeyAlgorithm RSA -KeyLength 2048 -NotAfter (Get-Date).AddYears(3) -FriendlyName "LocalDev-$dns"

function Write-Pem([byte[]]$der, [string]$header, [string]$footer, [string]$path) {
  $b64 = [Convert]::ToBase64String($der)
  $sb = [System.Text.StringBuilder]::new()
  [void]$sb.AppendLine($header)
  for ($i=0; $i -lt $b64.Length; $i+=64) {
    $len = [Math]::Min(64, $b64.Length - $i)
    [void]$sb.AppendLine($b64.Substring($i, $len))
  }
  [void]$sb.AppendLine($footer)
  [System.IO.File]::WriteAllText($path, $sb.ToString(), [System.Text.Encoding]::ASCII)
}

function EncLen([int]$len) { if ($len -lt 0x80) { return ,([byte]$len) } $bytes=@(); $v=$len; while($v -gt 0){ $bytes = ,([byte]($v -band 0xFF)) + $bytes; $v = $v -shr 8 } $count=[byte]$bytes.Length; return ,([byte](0x80 -bor $count)) + $bytes }
function TrimZero([byte[]]$v) { if (-not $v -or $v.Length -eq 0) { return ,0x00 } $i=0; while($i -lt ($v.Length-1) -and $v[$i] -eq 0x00){$i++} $o=$v[$i..($v.Length-1)]; if ($o[0] -band 0x80){ return ,0x00 + $o } else { return $o } }
function EncInt([byte[]]$v) { $val = TrimZero $v; $l = EncLen $val.Length; return ,0x02 + $l + $val }
function Octet([byte[]]$v) { $l = EncLen $v.Length; return ,0x04 + $l + $v }
function Seq([byte[]]$parts) { $l = EncLen $parts.Length; return ,0x30 + $l + $parts }
function Concat([byte[][]]$arr) { $out = New-Object System.Collections.Generic.List[byte]; foreach($a in $arr){[void]$out.AddRange($a)} return $out.ToArray() }
function OID([int[]]$arcs){ $first = 40*$arcs[0] + $arcs[1]; $rest=@($first); for($i=2;$i -lt $arcs.Length;$i++){ $n=[uint64]$arcs[$i]; $stack=@(); do { $stack = ,([byte]($n -band 0x7F)) + $stack; $n = $n -shr 7 } while($n -gt 0); for($j=0;$j -lt $stack.Length-1;$j++){ $stack[$j] = $stack[$j] -bor 0x80 } $rest += $stack } $bytes=[byte[]]$rest; $l=EncLen $bytes.Length; return ,0x06 + $l + $bytes }
function Null(){ return ,0x05 + ,0x00 }

$derCert = $cert.Export([System.Security.Cryptography.X509Certificates.X509ContentType]::Cert)
Write-Pem -der $derCert -header '-----BEGIN CERTIFICATE-----' -footer '-----END CERTIFICATE-----' -path $certPath

$rsa = $null
try { $rsa = $cert.GetRSAPrivateKey() } catch {}
if ($null -eq $rsa) { try { $rsa = [System.Security.Cryptography.X509Certificates.RSACertificateExtensions]::GetRSAPrivateKey($cert) } catch {} }
if ($null -eq $rsa) { $rsa = [System.Security.Cryptography.RSA]$cert.PrivateKey }
if ($null -eq $rsa) { throw 'No se pudo obtener la clave privada RSA del certificado.' }

$params = $rsa.ExportParameters($true)
$seqParts = Concat @((EncInt @(0x00)), (EncInt $params.Modulus), (EncInt $params.Exponent), (EncInt $params.D), (EncInt $params.P), (EncInt $params.Q), (EncInt $params.DP), (EncInt $params.DQ), (EncInt $params.InverseQ))
$rsaDer = Seq $seqParts
$algId = Seq (Concat @((OID @(1,2,840,113549,1,1,1)), (Null)))
$pkcs8 = Seq (Concat @((EncInt @(0x00)), $algId, (Octet $rsaDer)))

Write-Pem -der $pkcs8 -header '-----BEGIN PRIVATE KEY-----' -footer '-----END PRIVATE KEY-----' -path $keyPath
Write-Output 'OK'
"""
           
            # --------------------------------------------------
            # Escritura del script a fichero temporal y ejecución
            # --------------------------------------------------
            fd, tmp_ps1 = tempfile.mkstemp(suffix='.ps1', text=True)
            os.close(fd)
            _P(tmp_ps1).write_text(ps_script, encoding='utf-8')
            try:
                cmd = [psexe, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', tmp_ps1, '-OutDir', str(out_dir)]
                res = subprocess.run(cmd, capture_output=True, text=True, shell=False)
                if res.returncode != 0:
                    QtWidgets.QMessageBox.warning(self, 'Error generando certificado', (res.stderr or res.stdout or 'Fallo desconocido'))
                    return
            finally:
                # Limpieza del script temporal (defensiva)
                try:
                    _P(tmp_ps1).unlink(missing_ok=True)
                except Exception:
                    pass

            # --------------------------------------------------
            # Verificación de archivos generados
            # -----------------------------------------------
            if (not cert_path.exists()) or (not key_path.exists()):
                QtWidgets.QMessageBox.warning(self, 'Archivos no encontrados', f'No se generaron cert.pem/key.pem en: {out_dir}')
                return

            # --------------------------------------------------
            # Guardar rutas
            # --------------------------------------------------
            try:
                self.cfg['server_tls_certfile'] = str(cert_path)
                self.cfg['server_tls_keyfile'] = str(key_path)
                self.cert_edit.setText(str(cert_path))
                self.key_edit.setText(str(key_path))
                
                # Persistir en disco
                save_config(self.cfg)
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, 'Error', f'No se pudo actualizar la configuración: {e}')
                return

            # --------------------------------------------------
            # Refrescar UI del padre si existe
            # --------------------------------------------------
            try:
                parent = self.parent()
                if parent is not None:
                    if hasattr(parent, 'tls_opts_summary') and hasattr(parent, '_tls_opts_summary_text'):
                        parent.tls_opts_summary.setText(parent._tls_opts_summary_text())
                    if bool(self.cfg.get('server_enabled', False)) and hasattr(parent, '_apply_config_live'):
                        parent._apply_config_live(self.cfg)
            except Exception:
                pass

            QtWidgets.QMessageBox.information(self, 'Certificado generado', f'Se han creado:\n{cert_path}\n{key_path}')
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, 'Error', f'Excepción generando certificado: {e}')





class AuditViewerDialog(HelpableDialogMixin, QtWidgets.QDialog):
    # Abre resources/help/es/config_auditoria.html
    help_topic = 'config_auditoria'
    """Visor de eventos de auditoría con actualización periódica y control del número de eventos mostrados.
    Notas:
    - Esta clase forma parte de la interfaz gráfica de la aplicación.
    - Los métodos incluyen validaciones y manejo de errores para una UX robusta.
    """

    def __init__(self, parent=None, default_n: int = 200):
        """Descripción: Realiza ' '.
        Args:
            self: Instancia de la clase.
            parent: Widget padre de Qt (opcional).
            default_n: Parámetro.
        Returns:
            None.
        """
        super().__init__(parent)
        self.setWindowTitle('Auditoría del servidor')
        self.resize(800, 420)

        # --- Layout principal
        lay = QtWidgets.QVBoxLayout(self)

        # --- Cabecera con contador y selector N
        top = QtWidgets.QWidget(self)
        h = QtWidgets.QHBoxLayout(top)
        h.setContentsMargins(0, 0, 0, 0)
        self.lbl_count = QtWidgets.QLabel('Eventos: 0', top)
        h.addWidget(self.lbl_count)
        h.addStretch(1)
        h.addWidget(QtWidgets.QLabel('Mostrar últimos N:', top))
        self.sb_n = QtWidgets.QSpinBox(top)
        self.sb_n.setRange(1, 1000)
        self.sb_n.setValue(int(default_n))
        h.addWidget(self.sb_n)
        lay.addWidget(top)

        # --- Lista de eventos
        self.list = QtWidgets.QListWidget(self)
        try:
            f = self.list.font()
            f.setFamily('Consolas')
            f.setStyleHint(QtGui.QFont.Monospace)
            f.setFixedPitch(True)
            self.list.setFont(f)
        except Exception:
            pass
        self.list.setUniformItemSizes(True)
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        lay.addWidget(self.list, 1)

        # --- Temporizador + refresco
        self._last_count = -1
        self._last_n = -1
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(800)
        self._timer.timeout.connect(self._refresh)
        self._timer.start()
        self.sb_n.valueChanged.connect(lambda _v=None: self._refresh(force=True))
        self._refresh(force=True)

        # --- Botonera: OK + Ayuda ---
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok,
            parent=self
        )
        btns.accepted.connect(self.accept)
        # Añade botón "Ayuda" al extremo derecho y atajo F1 (idempotente)
        self._install_help_button(btns)
        lay.addWidget(btns)

        # --- Atajos opcionales coherentes con el resto de diálogos ---
        try:
            QtWidgets.QShortcut(QtGui.QKeySequence('Return'), self, self.accept)
            QtWidgets.QShortcut(QtGui.QKeySequence('Enter'), self, self.accept)
            QtWidgets.QShortcut(QtGui.QKeySequence('Esc'), self, self.reject)
        except Exception:
            pass

    def _format_line(self, ev: dict) -> str:
        """Descripción: Realiza 'line'.
        Args:
            self: Instancia de la clase.
            ev: Evento o diccionario de auditoría.
        Returns:
            None.
        """
        try:
            import datetime
            ts = float(ev.get('ts', 0) or 0)
            t = datetime.datetime.fromtimestamp(ts).strftime('%H:%M:%S') if ts > 0 else '--:--:--'
        except Exception:
            t = '--:--:--'
        action = str(ev.get('action', ''))
        parts = []
        for k, v in ev.items():
            if k in ('ts', 'action'):
                continue
            try:
                parts.append(f'{k}={v}')
            except Exception:
                pass
        return f'[{t}] {action} ' + ' '.join(parts)

    def _refresh(self, force: bool = False):
        """Descripción: Realiza la operación.
        Args:
            self: Instancia de la clase.
            force: Parámetro.
        Returns:
            None.
        """
        try:
            total = audit_count()
        except Exception:
            total = 0
        n = int(self.sb_n.value())
        if force or total != self._last_count or n != self._last_n:
            try:
                evs = audit_latest(n)
            except Exception:
                evs = []
            self.list.clear()
            if evs:
                self.list.addItems([self._format_line(e) for e in evs])
            self.lbl_count.setText(f'Eventos: {total} · Mostrando: {len(evs)}')
            self._last_count = total
            self._last_n = n


class TokenDialog(HelpableDialogMixin, QtWidgets.QDialog):
    help_topic = 'token_dialog'  # ← fuerza la ayuda a token_dialog.html
    """Resumen: [auto] Clase `TokenDialog`.

Atributos:
    (documentar atributos relevantes).
"""

    def __init__(self, parent=None, cfg: dict=None):
        """Descripción: Realiza ' '.

Args:
    self: Instancia de la clase.
    parent: Widget padre de Qt (opcional).
    cfg: Diccionario de configuración de la aplicación.

Returns:
    None."""
        super().__init__(parent)
        self.setWindowTitle('Calcular Token')
        self.setModal(True)
        self.cfg = cfg or {}
        lay = QtWidgets.QVBoxLayout(self)
        form = QtWidgets.QFormLayout()
        self.chk_enable = QtWidgets.QCheckBox('Habilitar token')
        self.chk_enable.setChecked(bool(self.cfg.get('server_token_enabled', False)))
        form.addRow('', self.chk_enable)
        self.ed_url = QLineEdit(self)
        self.ed_url.setPlaceholderText('Ej.: /?path=MiCarpeta%5CMiExe.exe&silent=1')
        form.addRow('URL', self.ed_url)
        self.ed_key = QLineEdit(self)
        self.ed_key.setEchoMode(QLineEdit.Password)
        self.ed_key.setPlaceholderText('Clave (Base64 URL-safe recomendada)')
        prot = self.cfg.get('server_token_key_protected', '')
        if prot:
            try:
                raw = dpapi_unprotect_user(prot)
                self.ed_key.setText(raw.decode('utf-8'))
            except Exception as e:
                # Clave heredada inválida / incompatible
                LOGGER.warning(
                    "No se pudo descifrar la clave de token guardada. "
                    "Se requiere generar una nueva."
                )
                self.ed_key.setText('')
        row_key = QtWidgets.QWidget(self)
        hk = QtWidgets.QHBoxLayout(row_key)
        hk.setContentsMargins(0, 0, 0, 0)
        self.chk_show = QtWidgets.QCheckBox('Ver clave')
        self.chk_show.toggled.connect(self._update_key_echo)
        self._update_key_echo(self.chk_show.isChecked())
        btn_gen = QPushButton('Generar clave', self)
        def _on_generate_key_local():
            reply = QtWidgets.QMessageBox.question(
                self,
                'Generar clave',
                '¿Seguro que quieres generar una nueva clave? Esto eliminará la clave actual.',
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if reply != QtWidgets.QMessageBox.Yes:
                return
            try:
                self.ed_key.setText(generate_secret_b64url(32))
            except Exception as e:
                try:
                    QtWidgets.QMessageBox.warning(self, 'Error', f'No se pudo generar la clave: {e}')
                except Exception:
                    pass
        self._on_generate_key = _on_generate_key_local
        btn_gen.clicked.connect(self._on_generate_key)
        hk.addWidget(self.ed_key, 1)
        hk.addWidget(self.chk_show)
        hk.addWidget(btn_gen)
        form.addRow('Clave', row_key)
        row_act = QtWidgets.QWidget(self)
        ha = QtWidgets.QHBoxLayout(row_act)
        ha.setContentsMargins(0, 0, 0, 0)
        btn_calc = QPushButton('Calcular Token', self)
        ha.addStretch(1)
        ha.addWidget(btn_calc)
        form.addRow('', row_act)
        self.ed_token = QLineEdit(self)
        self.ed_token.setReadOnly(True)
        form.addRow('Token', self.ed_token)
        row_cp = QtWidgets.QWidget(self)
        hc = QtWidgets.QHBoxLayout(row_cp)
        hc.setContentsMargins(0, 0, 0, 0)
        btn_copy_t = QPushButton('Copiar token…', self)
        btn_copy_u = QPushButton('Copiar URL…', self)
        hc.addStretch(1)
        hc.addWidget(btn_copy_t)
        hc.addWidget(btn_copy_u)
        form.addRow('', row_cp)
        lay.addLayout(form)
        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, self)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        self._install_help_button(btns)
        lay.addWidget(btns)
        self.resize(700, 260)

        def do_calc():
            """Descripción: Realiza 'calc'.

Args:
    (sin parámetros)

Returns:
    None."""
            url = (self.ed_url.text() or '').strip()
            secret = (self.ed_key.text() or '').strip()
            if not url or not secret:
                self.ed_token.setText('')
                return
            tok = compute_hmac_hex(url, secret)
            self.ed_token.setText(tok)
        btn_calc.clicked.connect(do_calc)
        btn_copy_t.clicked.connect(lambda: QtGui.QGuiApplication.clipboard().setText(self.ed_token.text()) if self.ed_token.text().strip() else None)

        def copy_url():
            """Descripción: Realiza 'url'.

Args:
    (sin parámetros)

Returns:
    dict."""
            u = (self.ed_url.text() or '').strip()
            t = (self.ed_token.text() or '').strip()
            if not u or not t:
                return
            if not u.startswith('/'):
                u = '/' + u
            sep = '&' if '?' in u else '?'
            try:
                port = int(getattr(self, 'cfg', {}).get('server_port', 8080) or 8080)
            except Exception as e:
                port = 8080
            full = f'https://127.0.0.1:{port}{u}{sep}token={t}'
            QtGui.QGuiApplication.clipboard().setText(full)
        btn_copy_u.clicked.connect(copy_url)

    def persisted_values(self) -> dict:
        """Descripción: Realiza 'values'.

Args:
    self: Instancia de la clase.

Returns:
    dict."""
        key_raw = (self.ed_key.text() or '').strip().encode('utf-8')
        prot = dpapi_protect_user(key_raw) if key_raw else ''
        return {'server_token_enabled': bool(self.chk_enable.isChecked()), 'server_token_key_protected': prot}

    def _update_key_echo(self, checked: bool):
        """
        Actualiza el modo de eco del campo de clave al marcar 'Ver clave'.
        """
        try:
            self.ed_key.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password)
            self.ed_key.repaint()
        except Exception as e:
            LOGGER.exception('[auto] Exception capturada en TokenDialog::_update_key_echo')

