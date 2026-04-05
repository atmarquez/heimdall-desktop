# Heimdall Desktop by Naidel

[![License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?logo=windows)](#)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/GUI-PySide6-41CD52?logo=qt)](https://doc.qt.io/qtforpython/)
[![Release](https://img.shields.io/github/v/release/atmarquez/heimdall-desktop)](https://github.com/atmarquez/heimdall-desktop/releases)
[![Status](https://img.shields.io/badge/Status-Stable-green)](#)

**Heimdall Desktop** es un lanzador avanzado de aplicaciones para Windows,
desarrollado en **Python** con **PySide6**.

Proporciona una interfaz gráfica potente y organizada para:

- Gestionar accesos a aplicaciones, scripts y ubicaciones especiales.
- Ejecutar comandos avanzados de Windows.
- Automatizar acciones locales o remotas mediante un servidor HTTP/HTTPS integrado.

El proyecto está orientado a **usuarios avanzados, técnicos y administradores**
que buscan un punto centralizado de control sin perder flexibilidad ni seguridad.

---

## 🌐 Documentación web:
https://atmarquez.github.io/heimdall-desktop/

---

## ✨ Características principales

- Interfaz gráfica moderna basada en **PySide6** (Qt).
- Organización flexible de accesos:
  - Por carpetas (estructura real del sistema de archivos).
  - Vista plana opcional.
- Creación y gestión de:
  - Accesos directos de Windows (`.lnk`).
  - Accesos web (`.url`).
- **Botones rápidos configurables** para carpetas y acciones frecuentes.
- Ejecución de:
  - Scripts de inicio (pre‑arranque).
  - Scripts de salida (post‑cierre).
  - Tareas programadas.
- **Integración con el Menú Inicio** de Windows.
- Catálogo extensible de **comandos especiales de Windows**:
  - `shell:`
  - `ms-settings:`
  - `.msc`
  - CLSID / GUID.
- **Servidor HTTP / HTTPS integrado** para automatización:
  - Soporte TLS.
  - Autenticación con token.
  - Whitelist de rutas y extensiones.
  - Auditoría de acciones.
  - Backoff / limitación ante errores.
- Auto‑inicio configurable con Windows.
- Sistema de **logging avanzado** y visor integrado.

---

## 🖥️ Requisitos

- **Windows 10 / Windows 11**
- **Python 3.10 o superior** (solo para ejecución desde código fuente)

---

## 🚀 Puesta en marcha

### Ejecución

Puedes ejecutar Heimdall Desktop de dos formas:

- Desde código fuente:

```bash
python main.py
```

- O mediante el ejecutable empacado (.exe).

## Configuración inicial recomendada

	1. Ejecuta la aplicación (`python main.py` o el ejecutable empacado).
	
	2. Configura la carpeta base de accesos en:
		Configuración → Generales

	3. Ajusta las opciones del servidor (si vas a usar automatización):
		Configuración → Servidor
		(puerto, alcance local, TLS, token, etc.)

	4. Crea accesos directos y accesos web dentro de la carpeta base configurada.

## Ejemplo de uso del servidor HTTP

Prueba el servidor con una URL como:
```
http://127.0.0.1:8080/?path=MiCarpeta%5CMiExe.exe&close=1
```

    Si el **token** está habilitado, añade `token=...` o usa cabecera `X-Launcher-Token`.

---

## 🖼️ Capturas

A continuación se muestran algunas capturas representativas de la interfaz y funcionalidades principales de **Heimdall Desktop**.

### 🪟 Pantalla principal

Vista principal de la aplicación en modo **por categorías**, mostrando:
- Árbol de accesos basado en carpetas reales del sistema.
- Vista jerárquica expandible/contraíble.
- Búsqueda integrada.
- Panel de botones rápidos a la derecha.

![Pantalla principal de Heimdall Desktop](docs/images/principal.png)

---

### ⚙️ Opciones · Generales

Pestaña de Configuración → Generales, donde se definen los parámetros básicos de la aplicación:
- Carpeta base de accesos.
- Comportamiento al ejecutar aplicaciones.
- Inicio automático con Windows.
- Opciones generales del lanzador.

![Configuración general](docs/images/configuración-genarales.png)

---

### 🎨 Opciones · Apariencia

Pestaña de Configuración → Apariencia, dedicada a la personalización visual:
- Tema claro, oscuro o del sistema.
- Icono de la aplicación.
- Tamaño y posición inicial de la ventana.
- Integración visual con Windows 10 / 11.

![Configuración de apariencia](docs/images/configuración-apariencia.png)

---

### ⚡ Opciones · Botones rápidos
Pestaña de Configuración → Botones rápidos, que permite definir accesos directos permanentes:
- Botones a carpetas frecuentes (Documentos, Descargas, etc.).
- Accesos personalizados definidos por el usuario.
- Modificación de nombre, ruta e icono.

![Configuración de botones rapidos](docs/images/configuración-botones.png)

---

### 🧩 Opciones · Scripts y tareas
Pestaña de Configuración → Scripts, orientada a automatización:
- Scripts de inicio (pre-arranque).
- Scripts de salida (post-cierre).
- Configuración del programador de tareas.
- Parámetros de ejecución, espera y timeout.

![Configuración de scripts](docs/images/configuración-scripts.png)

---

### 🧪 Opciones · Avanzado
Pestaña de Configuración → Avanzado, enfocada a mantenimiento y portabilidad:
- Exportación completa de la configuración a archivo JSON.
- Importación de configuraciones previas.
- Gestión del estado interno de la aplicación.

![Configuración de avanzado](docs/images/configuración-avanzado.png)

---

### 🌐 Opciones · Servidor HTTP / HTTPS

Pestaña de Configuración → Servidor, para el servidor embebido de automatización:
- Activación o desactivación del servidor.
- Puerto y alcance (local o red).
- Soporte TLS con certificados.
- Whitelist de rutas.
- Control de extensiones permitidas.
- Autenticación mediante token.
- Backoff y limitación ante errores.

![Configuración del servidor](docs/images/configuración-servidor.png)

---

### 🧾 Opciones · Auditoría y logs

Pestaña de Configuración → Log, donde se visualiza la actividad interna:
- Registro de ejecuciones.
- Errores y eventos relevantes.
- Auditoría de peticiones del servidor.
- Limpieza y consulta de logs.

![Logs y auditoría](docs/images/configuración-log.png)

---

### ℹ️ Opciones · Acerca de
Pestaña de Configuración → Acerca de, con información institucional:
- Datos del proyecto.
- Versión y build.
- Licencia GPLv3.
- Enlaces útiles.
- Acceso a la documentación y ayuda.

![Acerca de](docs/images/configuración-about.png)

---

## 📘 Documentación
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/CONFIGURATION.md`](docs/CONFIGURATION.md)
- [`docs/HTTP_API.md`](docs/HTTP_API.md)
- [`docs/SECURITY_NOTES.md`](docs/SECURITY_NOTES.md)
- [`docs/CODE_COMMENTS.md`](docs/CODE_COMMENTS.md)
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md)

## 🧾 Docstrings y comentarios
El archivo principal (main.py) contiene docstrings en español siguiendo el estilo Google-style, pensados para facilitar:
 - La lectura del código.
 - El mantenimiento.
 - La extensión futura del proyecto.

Se recomienda utilizarlos como referencia base al añadir nuevos módulos.
Úsalo como referencia y completa las descripciones donde sea necesario.

## ⚖️ Licencia

Este proyecto se distribuye bajo la **GNU General Public License versión 3 (GPLv3)**.
Consulta el archivo LICENSE para más información.

## 🟢 Estado del proyecto

 - Proyecto activo.
 - Arquitectura modular.
 - Preparado para ampliaciones futuras (nuevos tipos de accesos, integraciones, automatización avanzada).

## 👤 Autor

Antonio Teodomiro Márquez Muñoz (Naidel)
