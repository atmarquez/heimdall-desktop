# Documentación técnica – Heimdall Desktop

## Visión general

Heimdall Desktop está diseñado con una arquitectura modular y desacoplada, donde cada paquete
cumple una responsabilidad bien definida.

## Estructura del proyecto

```
heimdall_desktop/
├── main.py                    # Punto de entrada
├── app_meta.py                # Metadatos para "Acerca de"
├── config.json                # Configuración persistente
├── ui/                        # Interfaz gráfica
│   ├── main_window.py
│   ├── tree.py
│   ├── helpers.py
│   ├── help.py
│   ├── roles.py
│   ├── dialogs/
│   │   ├── create_url_dialog.py
│   │   ├── create_shortcut_dialog.py
│   │   └── special_commands_dialog.py
│   ├── config/
│   │   ├── dialog.py
│   │   ├── general.py
│   │   ├── appearance.py
│   │   ├── quick_buttons.py
│   │   ├── scripts.py
│   │   ├── server.py
│   │   ├── log.py
│   │   └── about.py
│   └── server/
│       ├── dialogs.py
│       ├── summaries.py
│       └── patches.py
├── core/                      # Lógica de negocio
│   ├── app_controller.py
│   ├── shortcuts.py
│   ├── scripts.py
│   ├── scheduler.py
│   └── autostart.py
├── server/                    # Servidor HTTP/HTTPS
│   ├── http.py
│   ├── security.py
│   ├── audit.py
│   └── throttle.py
├── config/
│   └── service.py
├── logutils/
│   ├── setup.py
│   └── memory.py
```

## Principios de diseño

- Separación estricta UI / lógica
- Un diálogo por fichero
- El `AppController` coordina el ciclo de vida
- El servidor no depende de la UI
- Imports explícitos y sin dependencias ocultas

## Flujo de ejecución

1. `main.py` configura logging y crea `MainWindow`
2. `MainWindow` inicializa `AppController`
3. Interacciones del usuario se delegan a módulos core
4. Scripts y servidor se gestionan fuera de la UI

## Convenciones

- python >= 3.10
- Código legible y modular
- Manejo explícito de errores
