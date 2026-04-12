# Changelog

Todos los cambios notables de este proyecto se documentan en este archivo.
The format is based on Keep a Changelog, and this project adheres to Semantic Versioning.

\---

## [0.21.0](https://github.com/naidel/heimdall-desktop/releases/tag/v0.21.0) - 2026-04-12

* Corregido error al cargar los datos de la configuración.

\---

## [0.20.1](https://github.com/naidel/heimdall-desktop/releases/tag/v0.20.1) - 2026-04-12

### Español 🇪🇸

#### 🎨 Temas y apariencia

* Soporte completo para temas QSS externos cargados desde fichero.
* El tema `THEME\_SYSTEM` ahora funciona como cargador de QSS definidos por el usuario.
* Recarga dinámica del tema al aplicar cambios sin reiniciar la aplicación.
* Colección de nuevos temas oficiales (azul, verde, rojo, solarized, ámbar, retro, minimalista, accesible).
* Documentación añadida para creación de temas personalizados.

#### ⚙️ Diálogo de Configuración

* El botón **Aplicar** ahora aplica los cambios sin cerrar el diálogo.
* Sincronización inmediata de todas las pestañas tras pulsar Aplicar.
* Corrección de ejecuciones duplicadas de señales Qt.

#### 📦 Importar / Exportar configuración

* Corregido el error "No hay configuración cargada" al exportar.
* Flujo completo de importación con estado candidato hasta Aplicar / OK.
* Eliminados mensajes duplicados durante la importación.
* Exportación siempre refleja la configuración activa real.

#### 🌐 Pestaña Servidor

* Refactor completo para heredar directamente de QWidget.
* Eliminación de widgets internos huérfanos.
* Implementación correcta de populate\_from\_cfg.
* Sincronización en caliente de checkboxes y resúmenes al aplicar.
* Corrección de errores visuales y de atributos inexistentes.

#### 🧠 Arquitectura interna

* Contrato unificado de pestañas (`populate\_from\_cfg`).
* Mejor gestión del estado del diálogo de configuración.

\---

### English 🇬🇧

#### 🎨 Themes \& Appearance

* Full support for external QSS themes loaded from file.
* `THEME\_SYSTEM` now acts as a user-defined QSS loader.
* Dynamic theme reload when applying changes without restart.
* New official theme collection (blue, green, red, solarized, amber, retro, minimal, accessible).
* Added documentation for custom theme creation.

#### ⚙️ Configuration Dialog

* **Apply** button now applies changes without closing the dialog.
* Immediate tab synchronization after applying changes.
* Fixed duplicated Qt signal executions.

#### 📦 Import / Export Configuration

* Fixed false "No configuration loaded" message on export.
* Complete import flow with candidate state until Apply / OK.
* Removed duplicated import messages.
* Export always reflects the real active configuration.

#### 🌐 Server Tab

* Complete refactor to inherit directly from QWidget.
* Removed orphan internal widgets.
* Correct implementation of populate\_from\_cfg.
* Live synchronization of checkboxes and summaries on apply.
* Fixed visual bugs and missing attribute errors.

#### 🧠 Internal Architecture

* Unified configuration tab contract (`populate\_from\_cfg`).
* Improved configuration dialog state handling.

\---

\---

## 0.16.3b

* Primera beta
* Añadida pestaña Acerca de con licencia y changelog

## 0.15.1b

* Añadido `app\_meta.py`.
* Nuevos documentos: LICENSE.txt

## 0.1.1b

* Añadido `main.py` (docstrings en español generados automáticamente).
* Nuevos documentos: ARCHITECTURE.md, CONFIGURATION.md, HTTP\_API.md, SECURITY\_NOTES.md, CODE\_COMMENTS.md.
* README simplificado con guía rápida.

