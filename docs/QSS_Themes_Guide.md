# Guía de Temas QSS – Heimdall Desktop

Esta guía explica cómo funciona el sistema de **temas QSS** de Heimdall Desktop y cómo puedes crear tus propios temas personalizados de forma segura y sencilla, **sin tocar código Python**.

---

## 1. ¿Qué es un tema QSS?

Un tema QSS es un archivo de texto con extensión `.qss` que define **la apariencia visual** de la aplicación:

- Colores de fondo
- Colores de texto
- Bordes
- Radios de esquina
- Estados *hover*, *pressed*, *selected*, etc.

QSS (*Qt Style Sheets*) funciona de forma similar a CSS, pero está adaptado a widgets de Qt.

---

## 2. Dónde se cargan los temas

Cuando seleccionas **"Tema del sistema"** en la aplicación:

- Heimdall Desktop busca un archivo llamado:

```
styles.qss
```

- Este archivo debe estar en el **directorio principal de la aplicación** (donde está `main.py`).
- El contenido del archivo se aplica a toda la interfaz en caliente.

Si el archivo no existe o está vacío, no ocurre ningún error.

---

## 3. Estructura básica de un archivo QSS

Un archivo QSS está formado por **reglas**. Cada regla tiene:

- Un selector (qué widget se ve afectado)
- Un conjunto de propiedades visuales

Ejemplo mínimo:

```css
QWidget {
    background: #202020;
    color: #ffffff;
}
```

Esto cambia el fondo y el texto de toda la aplicación.

---

## 4. Selectores más usados en Heimdall Desktop

Estos son los widgets principales que puedes personalizar:

### Aplicación completa

```css
QWidget { }
QMainWindow, QDialog { }
```

### Campos de texto

```css
QLineEdit, QComboBox, QTextEdit, QPlainTextEdit { }
QLineEdit:focus, QComboBox:focus { }
```

### Botones

```css
QPushButton { }
QPushButton:hover { }
QPushButton:pressed { }
```

### Árbol principal (lista de accesos)

```css
QTreeWidget { }
QTreeWidget::item:selected { }
```

### Pestañas

```css
QTabWidget::pane { }
QTabBar::tab { }
QTabBar::tab:selected { }
QTabBar::tab:hover { }
```

### Barras de progreso

```css
QProgressBar { }
QProgressBar::chunk { }
```

### Cabeceras de listas y tablas

```css
QHeaderView::section { }
QHeaderView::section:hover { }
```

---

## 5. Propiedades visuales más comunes

Puedes usar, entre otras:

```css
background: #RRGGBB;
color: #RRGGBB;
border: 1px solid #RRGGBB;
border-radius: 6px;
padding: 4px;
```

Consejos:

- Usa **fondos oscuros con texto claro** o **fondos claros con texto oscuro**.
- Evita colores muy saturados para áreas grandes.
- Reserva los colores vivos para selecciones o foco.

---

## 6. Cómo crear tu propio tema paso a paso

1. Copia uno de los temas oficiales (`.qss`).
2. Renómbralo a:

```
styles.qss
```

3. Ábrelo con un editor de texto.
4. Cambia colores poco a poco.
5. Guarda el archivo.
6. Selecciona **Tema del sistema** en la aplicación.

Los cambios se aplican inmediatamente cuando se vuelve a seleccionar el tema.

---

## 7. Buenas prácticas

- Cambia **un color cada vez**.
- Mantén buen contraste entre texto y fondo.
- Usa comentarios para documentar tus cambios:

```css
/* Color principal del tema */
QWidget {
    background: #1e2a38;
}
```

- Si algo no te gusta, vuelve al tema anterior.

---

## 8. Errores comunes (y cómo evitarlos)

❌ Usar texto oscuro sobre fondo oscuro
✅ Solución: aumenta el contraste

❌ Bordes invisibles
✅ Solución: usa un color de borde ligeramente distinto al fondo

❌ Colores chillones en grandes zonas
✅ Solución: colores suaves + acentos

---

## 9. Filosofía del sistema de temas

- Los temas internos son **seguros y estables**.
- Los temas QSS externos están pensados para:
  - Usuarios avanzados
  - Personalización completa
  - Experimentación sin riesgo

Nada de lo que hagas en un QSS puede romper la aplicación.

---

## 10. Ejemplo final completo

```css
QWidget {
    background: #243447;
    color: #e6edf3;
}

QTreeWidget::item:selected {
    background: #6cb6ff;
    color: #0b1b2b;
}
```

---

¡Disfruta personalizando Heimdall Desktop!

---

# Apéndice A – Temas oficiales de Heimdall Desktop

Este apéndice describe los **temas oficiales incluidos en Heimdall Desktop**.  
Estos temas están implementados internamente mediante `ThemeManager` y sirven como:

- Referencia visual
- Base técnica
- Punto de partida para crear temas QSS personalizados

Los temas oficiales están pensados para ser **seguros, coherentes y estables**.

---

## A.1 Tema Claro (`THEME_LIGHT`)

### Descripción
Tema claro moderno, limpio y equilibrado. Está diseñado para priorizar la legibilidad y una experiencia visual cómoda durante el día.

### Características visuales
- Fondo principal claro
- Texto oscuro de alto contraste
- Bordes suaves y discretos
- Color de selección azul estándar
- Sensación ligera y ordenada

### Recomendado para
- Uso diurno
- Entornos bien iluminados
- Usuarios nuevos
- Personalizaciones ligeras (cambiar color de acento, radios, bordes)

---

## A.2 Tema Oscuro (`THEME_DARK`)

### Descripción
Tema oscuro neutral, inspirado en interfaces modernas. Reduce la fatiga visual sin llegar al negro absoluto.

### Características visuales
- Fondos gris oscuro (no negro puro)
- Texto claro y suave
- Botones y paneles bien diferenciados
- Azul suave para foco y selección

### Recomendado para
- Uso prolongado
- Trabajo nocturno
- Usuarios técnicos
- Base ideal para crear temas oscuros personalizados

---

## A.3 Tema Alto Contraste (`THEME_HIGH_CONTRAST`)

### Descripción
Tema diseñado **principalmente para accesibilidad**. Prioriza la visibilidad absoluta sobre la estética.

### Características visuales
- Fondo negro puro
- Texto amarillo de alto contraste
- Bordes gruesos y claramente definidos
- Colores muy diferenciados entre estados

### Recomendado para
- Usuarios con dificultades visuales
- Situaciones de baja visibilidad
- Escenarios donde la legibilidad es crítica

---

## A.4 Tema del Sistema (`THEME_SYSTEM`)

### Descripción
Tema especial que **no define colores internamente**. Este tema permite personalización completa sin tocar el código.

### Características
- Control total por el usuario
- Editable con cualquier editor de texto
- No requiere conocimientos de Python
- No puede romper la aplicación
- Permite experimentar libremente

### Recomendado para
- Usuarios avanzados
- Creadores de temas
- Adaptaciones personales o branding

---

## A.5 Tema del Sistema Anfitrión (`THEME_HOST_SYSTEM`)

### Descripción
Tema que intenta adaptarse al **aspecto visual del sistema operativo**, especialmente en Windows.

### Características
- Integración visual con el sistema
- Apariencia más “nativa”
- Resultado dependiente de la plataforma

### Recomendado para
- Usuarios que prefieren coherencia con el sistema
- Integración visual con Windows

---

## A.6 Relación entre temas oficiales y temas QSS

Los temas oficiales sirven como:

- Referencia de contraste
- Ejemplos de equilibrio visual
- Base conceptual para crear estilos externos

Puedes:
- Clonar visualmente un tema oficial en QSS
- Ajustar únicamente colores de acento
- Combinar ideas entre varios temas (fondos de uno, selección de otro)

---

## A.7 Recomendación para crear tu primer tema

Si es tu primera vez creando un tema personalizado:

1. Empieza copiando el **tema claro** o **tema oscuro**.
2. Cambia solo el color de selección.
3. Ajusta el color del fondo principal.
4. Prueba el resultado unos minutos antes de seguir modificando.

Pequeños cambios bien medidos producen mejores resultados que modificaciones radicales.

---

Este apéndice completa la guía principal y sirve como **documentación estable y de referencia** para el sistema de temas de Heimdall Desktop.

