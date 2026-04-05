# Heimdall Desktop

Heimdall Desktop es un lanzador de aplicaciones para Windows desarrollado en Python con PySide6.
Proporciona una interfaz gráfica avanzada para organizar accesos, ejecutar scripts, manejar comandos
especiales de Windows y exponer un servidor HTTP/HTTPS embebido para automatización.

## Características principales

* Interfaz gráfica moderna basada en PySide6
* Organización flexible de accesos por carpetas o vista plana
* Creación y gestión de accesos directos (.lnk) y accesos web (.url)
* Botones rápidos configurables
* Ejecución de scripts de pre‑arranque y post‑salida
* Integración con el Menú Inicio de Windows
* Catálogo de comandos especiales (shell:, ms-settings:, .msc, CLSID)
* Servidor HTTP/HTTPS integrado con seguridad, auditoría y limitación
* Auto-inicio configurable con Windows
* Sistema de logging avanzado

## Requisitos

* Windows 10 / 11
* Python 3.10 o superior

## Puesta en marcha

1. Ejecuta la aplicación (`python main.py` o el ejecutable empacado).
2. Configura las opciones en **Opciones → Servidor** (puerto, ámbito local / TLS, token, etc.).
3. Crea accesos en la carpeta base (ver **Opciones → Generales**).
4. Prueba el servidor con una URL como:

```
   http://127.0.0.1:8080/?path=MiCarpeta%5CMiExe.exe\\\&close=1
   ```

Si el **token** está habilitado, añade `token=...` o usa cabecera `X-Launcher-Token`.

## Documentación

* [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
* [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)
* [`docs/HTTP\\\_API.md`](docs/HTTP_API.md)
* [`docs/SECURITY\\\_NOTES.md`](docs/SECURITY_NOTES.md)
* [`docs/CODE\\\_COMMENTS.md`](docs/CODE_COMMENTS.md)
* [`docs/CHANGELOG.md`](docs/CHANGELOG.md)

  ## Archivo con docstrings

  Se ha generado automáticamente `main.py` con *docstrings* en español (Google-style) para facilitar la lectura. Úsalo como referencia y completa las descripciones donde sea necesario.

  *Última actualización: 2026-03-01 18:07*

  ## Licencia

  Este proyecto se distribuye bajo la **GNU General Public License versión 3 (GPLv3)**.
Consulta el archivo LICENSE para más información.

  ## Estado del proyecto

  Proyecto activo, arquitectura modular y preparado para ampliaciones futuras.

  ## Autor

  Naidel

