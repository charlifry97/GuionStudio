# GuionStudio

Editor de guiones audiovisuales construido con Python, GTK 4 y Libadwaita.

## Novedades 1.0

- Reordenación de actos, secuencias y escenas desde el panel lateral mediante las flechas de cada elemento.
- Cada movimiento desplaza el bloque completo: el acto con sus secuencias y escenas, la secuencia con sus escenas o la escena con todo su contenido hasta el siguiente encabezado estructural.
- Icono de aplicación actualizado y registrado para GNOME/Linux.

## Requisitos de compilación en Ubuntu

Instala las herramientas y bibliotecas de desarrollo: GTK 4, Libadwaita, PyGObject, Meson, Ninja y los componentes de compilación de GResource.

La compilación sigue el flujo Meson habitual:

```bash
meson setup build
meson compile -C build
sudo meson install -C build
```

Para probar sin instalar en el sistema, usa un prefijo local:

```bash
meson setup build --prefix="$HOME/.local"
meson compile -C build
meson install -C build
```

El manifiesto Flatpak incluido está preparado para una compilación local desde el directorio del proyecto. Para distribuirlo públicamente todavía será necesario publicar el código en un repositorio remoto y definir una fuente versionada.


## Mejoras de la versión 1.0

- Normalización automática a mayúsculas de encabezados de acto, secuencia y escena, así como de rótulos de personajes y transiciones reconocidos por el editor.
- Conservación de mayúsculas y minúsculas normales en acción, diálogo y acotaciones.
- Nueva pestaña **Escaleta** en el panel lateral: reúne las escenas en orden, muestra una breve sinopsis inicial y permite saltar a cada escena.
- Contadores en vivo de palabras, páginas estimadas, párrafos, líneas y caracteres.
- Iconografía simbólica coherente para estructura, escaleta, personajes y locaciones.
- Datos de versión y autor actualizados: **1.0 — Carlos A. Rguez Padrón**.


## Novedades de la versión 1.1

- Fichas independientes para **Argumento**, **Sinopsis**, **Storyline** y **Logline**, guardadas dentro del proyecto `.guion`.
- Resaltado de selecciones de texto por categorías y colores configurables manualmente mediante códigos hexadecimales (por ejemplo `#F4D35E`).
- Filtro de lectura para mostrar solo el texto asociado a una categoría; el resto se oculta temporalmente sin borrarse.
- Persistencia de categorías y fragmentos resaltados al guardar y volver a abrir proyectos `.guion`.
- Menú de **Atajos de teclado** para consultar, modificar, quitar y restaurar combinaciones. Los cambios se guardan en la configuración del usuario.
- Atajos iniciales de resaltado: `Ctrl+Alt+H` aplica el resaltado activo; `Ctrl+Alt+1…4` filtra las primeras cuatro categorías; `Ctrl+Alt+0` vuelve a mostrar todo.

Las categorías iniciales son Investigación, Revisar, Personaje y Tema. Se pueden renombrar, cambiar de color o ampliar desde el botón de configuración del resaltador.


## Novedades de la versión 1.2

- Interfaz renovada con iconos, emojis y acceso directo a las herramientas narrativas.
- Sección de desarrollo de historia accesible desde la barra superior: argumento, sinopsis, storyline y logline.
- Los resaltados usan fondos con un 50 % de opacidad para conservar la legibilidad del texto.
- El panel de autocompletado utiliza una superficie translúcida para no ocultar por completo el contenido del guion.


## Novedades de la versión 1.3.1

- Nueva pantalla de inicio con identidad visual propia: paleta azul profundo, violeta y acento dorado, jerarquía tipográfica y tarjetas de herramientas.
- Accesos directos para crear un guion, abrir un proyecto, entrar al desarrollo narrativo y consultar los atajos.
- Lista de hasta ocho proyectos recientes, persistente entre sesiones y con apertura directa.
- Acceso a Inicio desde la barra superior y el menú de la aplicación.
- La pantalla de inicio permanece disponible como pestaña, sin interferir con los documentos abiertos.


## Novedades de la versión 1.4.0

**Inicio y navegación**
- La pantalla de inicio ocupa todo el espacio, usa emojis en sus tarjetas, y su pestaña queda fija (no se puede cerrar por error). Tiene su propia zona de avisos y lista de recientes con botón para quitar entradas.
- Selector **🎬 Guion | 📝 Historia** en la barra superior (Ctrl+Mayús+G / Ctrl+Mayús+H) y **Alt+Inicio** para volver al inicio.
- Las acciones que no aplican (guardar en Inicio, formato en la Historia…) se desactivan en vez de no hacer nada.

**Historia como espacio de trabajo**
- Argumento, sinopsis, storyline y logline ya no son una ventana modal: son un espacio de trabajo con panel lateral, área amplia de escritura, contadores y deshacer independiente por ficha. Se guarda dentro del `.guion`.

**Panel lateral con emojis**
- 🎭 Actos · 🎞️ Secuencias · 🎬 Escenas · 👤 Personajes · 📍 Locaciones; pestañas 🗂️ Estructura, 📋 Escaleta, 👥 Personajes y 📍 Locaciones, con contadores.
- Las flechas de mover se desactivan en los extremos; clic en un personaje/locación salta a la siguiente aparición.

**Fiabilidad**
- Guardado atómico, confirmación al cerrar pestañas o salir con cambios, sin duplicar proyectos abiertos, y los `.txt`/`.fountain` abiertos nunca se sobrescriben con formato de proyecto.
- Correcciones del editor (Tab/Mayús+Tab, Enter con autocompletado, resaltados, rendimiento): ver `INFORME_CAMBIOS.md`.

## Pruebas

```bash
python3 -m unittest discover -s tests -t .
```
Incluye pruebas de lógica y de interfaz sobre un GTK simulado (`tests/gtk_fake.py`); no sustituyen a una prueba manual en el escritorio.


## Novedades de la versión 1.4.1

- **Título del proyecto**: campo editable en el centro de la barra superior (F2). Se guarda en el `.guion`, aparece en la pestaña y en la ventana, y se propone como nombre de archivo y como título al exportar.
- **Historia → Word**: botón «📄 Guardar en Word…» en el espacio de la historia (o `Ctrl+Mayús+E`, o el menú) que genera un `.docx` con el título del proyecto y las fichas que tengan contenido. No requiere instalar nada adicional.
- Los botones de la cabecera (panel lateral 📑, inicio 🏠, nuevo ➕, guardar 💾) y la pestaña de Inicio ya no dependen del tema de iconos del sistema.
