# Guiones de Presentación — Compilador Semestre 5

---

## GUION 1 — TÚ (Parte técnica: arquitectura y el ejecutable)

---

**[APERTURA]**

"Buenas, voy a explicar cómo construimos este proyecto y las decisiones técnicas que tomamos para que funcione como una aplicación de escritorio real, sin depender de internet ni de un servidor."

---

**[QUÉ ES EL PROYECTO]**

"Construimos un IDE de escritorio — una aplicación con ventana propia, como cualquier programa instalado en Windows — que analiza código fuente y lo pasa por las fases clásicas de un compilador: léxica, sintáctica y semántica."

"La interfaz la hicimos completamente en HTML, CSS y JavaScript puro — sin frameworks, sin React, sin librerías externas. Todo el código de análisis está escrito a mano. El reto era: ¿cómo hacemos que eso corra como aplicación de escritorio sin depender de un navegador?"

---

**[PYWEBVIEW — EL PUENTE]**

"La solución fue **pywebview**. Es una librería de Python que actúa como contenedor: toma un archivo HTML y lo abre dentro de una ventana nativa del sistema operativo usando el motor de renderizado que ya tiene instalado Windows — en este caso EdgeHTML o WebView2. No instala un navegador aparte, usa el del sistema."

"Nuestro `app.py` hace tres cosas:"

1. "Resuelve rutas con `get_path()`. Esta función tiene una lógica crítica: cuando el programa corre como `.exe`, PyInstaller extrae los archivos a una carpeta temporal en memoria llamada `_MEIPASS`. La función detecta si existe `sys._MEIPASS` — que solo existe en tiempo de ejecución del `.exe` — y arma la ruta desde ahí. Si no existe, usa la ruta normal del proyecto. Sin esto, el ejecutable no encontraría el HTML y no cargaría nada."

2. "Crea la ventana con `webview.create_window()`, pasando la ruta al HTML, el título, dimensiones y el color de fondo `#1e1e1e` para que coincida con el tema oscuro."

3. "Lanza el loop con `webview.start()`."

"Son 15 líneas de Python. El trabajo real está en el HTML."

---

**[DE SCRIPT A .EXE — PYINSTALLER]**

"Para el ejecutable usamos **PyInstaller** con modo `--onefile`. Lo que hace es empaquetar en un solo binario: el intérprete de Python, todas las dependencias de pywebview, y los archivos estáticos del proyecto."

"La configuración está en `app.spec`. Lo más importante es la sección `datas`, que declara qué archivos no-Python hay que incluir adentro:"

```
datas=[
  ('compilador-final.html', '.'),
  ('prism.css', '.'),
  ('prism.js', '.'),
  ('assets/Logo_compilador.jpeg', '.')
]
```

"El punto `.` como destino significa que se extraen en la raíz de `_MEIPASS`, que es donde `get_path()` los va a buscar."

"Dos parámetros importantes más en el spec: `console=False` suprime la ventana negra de terminal — sin esto el `.exe` abriría dos ventanas. Y `upx=True` activa compresión UPX sobre los binarios internos para reducir el tamaño final."

"El comando para generar es:"

```
python -m PyInstaller app.spec --noconfirm
```

"Y el `.exe` queda en `dist/`. Pesa alrededor de 13MB porque lleva Python adentro."

---

**[100% OFFLINE — SIN LLAMADAS EXTERNAS]**

"Una decisión de diseño central fue que todo funcione sin internet. Hay tres niveles donde esto aplica:"

"**Primero, las fuentes.** En lugar de cargar Inconsolata desde Google Fonts con un `<link>` externo, la convertimos a base64 y la embebimos directamente en el CSS con `@font-face { src: url('data:font/ttf;base64,...') }`. El archivo HTML tiene 5 assets embebidos en base64 — fuentes e imágenes — así que se abre igual con o sin red."

"**Segundo, el syntax highlighting.** Los archivos `prism.css` y `prism.js` son copias locales de la librería Prism. No apuntan a ningún CDN. PyInstaller los incluye adentro del `.exe` igual que el HTML."

"**Tercero, y más importante: el analizador.** El lexer y el parser están implementados en JavaScript puro dentro del propio HTML. No hay ningún `fetch()`, ningún `XMLHttpRequest`, ningún WebSocket. No se manda el código a ningún servidor para analizarlo. Todo el procesamiento ocurre localmente, en el motor de JavaScript de la ventana pywebview. Por eso la respuesta es instantánea — no hay latencia de red porque no hay red."

---

**[FLUJO DE COMPILACIÓN EN TIEMPO REAL]**

"El análisis se dispara con `Ctrl+Enter` — hay un listener de teclado: `document.addEventListener('keydown', e => { if (e.ctrlKey && e.key === 'Enter') compile(); })`. También con el botón de compilar."

"Cuando se ejecuta `compile()`, la función toma el texto de los dos editores, concatena los tokens de ambos, y los pasa primero al lexer y después al parser. El resultado — tabla de tokens, estadísticas, árbol AST y log de reglas — se renderiza todo junto al final, sin recargar nada."

---

**[CIERRE]**

"En resumen: HTML y JavaScript para la interfaz y la lógica de compilación, pywebview para convertirlo en app de escritorio nativa, PyInstaller para empaquetarlo en un solo `.exe` autocontenido. Sin internet, sin servidor, sin dependencias externas en tiempo de ejecución. Todo adentro del binario."

---
---

## GUION 2 — TU COMPAÑERA (Parte funcional: qué hace el compilador)

---

**[APERTURA]**

"Voy a explicar qué hace el compilador por dentro — cómo funciona el análisis, qué reconoce y cómo está implementado cada componente."

---

**[QUÉ ANALIZA]**

"El compilador acepta código fuente en varios lenguajes y lo pasa por las dos primeras fases de compilación: léxica y sintáctica. Tiene dos editores en paralelo para poder analizar y comparar dos fragmentos de código al mismo tiempo."

---

**[FASE 1 — ANÁLISIS LÉXICO]**

"La primera fase es el **análisis léxico**. El lexer — la función `lex()` — lee el código fuente carácter por carácter, usando un índice `i` que avanza con cada llamada a `adv()`. A medida que avanza, agrupa los caracteres en tokens y les asigna tipo, valor, número de línea y columna."

"El lexer reconoce en este orden de prioridad:"

- **Comentarios** — `//`, `#` para línea, y `/* */` para bloque
- **Strings** — comillas simples, dobles, triples, y f-strings de Python como `f"hola {nombre}"`
- **Números** — con soporte para hexadecimal `0xFF`, binario `0b1010`, octal `0o77`, notación científica `1.5e10`
- **Identificadores y palabras clave** — empieza con `/[a-zA-Z_$]/`, sigue acumulando alfanuméricos, y al final consulta un `Set` de más de 60 palabras reservadas para saber si es keyword o identificador
- **Operadores** — primero busca operadores de 3 caracteres como `===`, `!==`, `**=`, después de 2 como `==`, `>=`, `&&`, `=>`, y por último los de 1 carácter
- **Símbolos** — paréntesis, llaves, corchetes, punto y coma, coma
- **Errores léxicos** — cualquier carácter que no encaje en ninguna categoría queda como token de tipo `unknown`

"Cada token se muestra en la tabla con su valor, tipo, clasificación, sub-clasificación, y la posición exacta — línea y columna — donde aparece en el código fuente."

"Al costado hay estadísticas en tiempo real: total de tokens, desglose por tipo, y una gráfica de torta dibujada con Canvas API que muestra la proporción de cada categoría. Al hacer click en cualquier estadística, la tabla se filtra para mostrar solo esos tokens."

---

**[FASE 2 — ANÁLISIS SINTÁCTICO]**

"La segunda fase es el **análisis sintáctico**. Toma la lista de tokens del lexer — filtrando los comentarios — y verifica que estén organizados según las reglas gramaticales del lenguaje."

"El método que implementamos es un **parser de descenso recursivo**. Funciona así: hay una función para cada construcción del lenguaje — `parseFn()` para funciones, `parseStmt()` para sentencias, `parseExprNode()` para expresiones — y cada una llama a las demás según lo que necesita. Es recursivo porque una expresión puede contener otra expresión, y así sucesivamente."

"El parser construye un **árbol de sintaxis abstracta (AST)**. Cada nodo del árbol tiene una etiqueta — el nombre de la construcción — y puede tener hijos. Por ejemplo, un nodo `if` tiene como hijos la condición, el bloque then, y opcionalmente el bloque else."

"Ese árbol se dibuja con Canvas API — cada nodo es un rectángulo redondeado, y las líneas entre ellos son las conexiones padre-hijo. El color de cada nodo varía según su tipo: verde para el nodo raíz PROGRAMA, violeta para clases, rojo para returns, amarillo para operadores. Se puede hacer zoom con `Ctrl+scroll` o con los botones."

"Al lado del árbol está el **log de reglas**. Cada fila muestra: qué se detectó, en qué línea del código, y la regla gramatical formal que se aplicó. Esas reglas usan la notación `→` que significa 'se compone de'. Por ejemplo `FuncDef → tipo ID '(' Params ')' Bloque` dice exactamente de qué partes está hecha una declaración de función. Es la gramática libre de contexto del lenguaje escrita en forma legible."

"También aparece en el encabezado un código de posición como `L3-n12`. Eso significa: primera producción en la línea 3, árbol con 12 nodos en total. Es un resumen rápido del análisis."

"El parser maneja errores con try/catch: si no puede parsear algo, lo descarta, incrementa el contador de errores y sigue intentando. Así puede reportar múltiples errores en lugar de detenerse al primero."

---

**[FASE 3 — SEMÁNTICO]**

"La tercera fase, el **análisis semántico**, está marcada como 'en desarrollo'. En un compilador completo esta fase verificaría que el código tiene sentido lógico — que las variables estén declaradas antes de usarse, que los tipos sean compatibles en las operaciones, que no se llame a una función con el número de argumentos incorrecto. La sección ya está preparada en la interfaz para implementarla."

---

**[DETECCIÓN AUTOMÁTICA DE LENGUAJE]**

"Una función que hace el compilador más útil es `detectLang()`. Cuando se ejecuta el análisis, aplica una serie de expresiones regulares sobre el código fuente y le da puntos a cada lenguaje según los patrones que encuentra:"

- Python: `def nombre(`, `from X import`, `f"..."`, `elif`, `None/True/False`
- JavaScript: `const/let/var`, arrow functions `=>`, `console.log`, `undefined`
- C/C++: `#include`, `int main(`, `std::`, `cout`, `nullptr`
- Java: `public class`, `System.out.println`, `public static void main`

"Al final compara los puntajes y muestra el lenguaje con mayor puntuación. Esto permite que el compilador sea multi-lenguaje sin necesitar configuración manual."

---

**[LA INTERFAZ]**

"La interfaz tiene tema oscuro con color base `#1e1e1e`, la misma paleta de VS Code, porque los editores de código lo usan por legibilidad. El editor resalta la sintaxis en tiempo real con Prism.js mientras escribís. Los atajos de teclado incluyen `Ctrl+Enter` para compilar. Y todas las secciones tienen zoom independiente — editor, tabla de tokens y árbol AST — controlado con `Ctrl+scroll` o botones, sin que interfieran entre sí."

---

**[CIERRE]**

"En resumen: es un compilador funcional de las dos primeras fases, con un lexer capaz de reconocer múltiples lenguajes, un parser de descenso recursivo que construye un AST visual, detección automática de lenguaje, y todo renderizado en tiempo real sin ninguna dependencia de red."

---
