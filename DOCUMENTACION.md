# Documentación Técnica Completa — Compilador SM
> Semestre 5 · Diseño de Compiladores · Corte 1

---

## Índice

1. [Visión general: qué es este proyecto](#1-visión-general-qué-es-este-proyecto)
2. [Arquitectura de capas: la analogía de la fábrica](#2-arquitectura-de-capas-la-analogía-de-la-fábrica)
3. [Cómo funciona 100% offline (sin internet)](#3-cómo-funciona-100-offline-sin-internet)
4. [app.py — El portero](#4-apppy--el-portero)
5. [app.spec — El manual de empaque](#5-appspec--el-manual-de-empaque)
6. [compilador-final.html — El corazón del sistema](#6-compilador-finalhtml--el-corazón-del-sistema)
   - 6.1 [CSS y diseño visual](#61-css-y-diseño-visual)
   - 6.2 [Estructura HTML (el esqueleto)](#62-estructura-html-el-esqueleto)
   - 6.3 [El Léxico: `lex(src)`](#63-el-léxico-lexsrc)
   - 6.4 [Clasificadores de tokens](#64-clasificadores-de-tokens)
   - 6.5 [El Parser: `parse(tokens)`](#65-el-parser-parsetokens)
   - 6.6 [El Árbol Sintáctico (AST): render y canvas](#66-el-árbol-sintáctico-ast-render-y-canvas)
   - 6.7 [El gráfico de torta (Pie Chart)](#67-el-gráfico-de-torta-pie-chart)
   - 6.8 [Detección automática de lenguaje](#68-detección-automática-de-lenguaje)
   - 6.9 [El editor con syntax highlighting](#69-el-editor-con-syntax-highlighting)
   - 6.10 [Sistema de zoom](#610-sistema-de-zoom)
   - 6.11 [Barra de estado (Status Bar)](#611-barra-de-estado-status-bar)
   - 6.12 [La función `compile()`](#612-la-función-compile)
7. [Flujo completo de ejecución (de principio a fin)](#7-flujo-completo-de-ejecución-de-principio-a-fin)
8. [Por qué cada decisión técnica](#8-por-qué-cada-decisión-técnica)
9. [Posibles optimizaciones y mejoras futuras](#9-posibles-optimizaciones-y-mejoras-futuras)
10. [Confirmación offline: qué hay embebido y por qué no se rompe nada](#10-confirmación-offline-qué-hay-embebido-y-por-qué-no-se-rompe-nada)
11. [Cómo regenerar el exe](#11-cómo-regenerar-el-exe)

---

## 1. Visión general: qué es este proyecto

Este proyecto implementa las **dos primeras fases de un compilador**:

| Fase | Nombre | Qué hace |
|------|--------|----------|
| 1 | **Análisis Léxico** | Divide el código fuente en tokens (las palabras del idioma) |
| 2 | **Análisis Sintáctico** | Verifica que esas palabras formen oraciones válidas (AST) |

Está empaquetado como una **aplicación de escritorio** para Windows (`.exe`) que funciona **completamente offline**. Por dentro es una página web (HTML + CSS + JavaScript) mostrada a través de una ventana nativa de Python usando `pywebview`.

La metáfora perfecta para entenderlo: **es como un libro con ventana de cristal**. El libro (HTML) contiene todo el conocimiento y las reglas del compilador; la ventana (pywebview) permite verlo como si fuera un programa de escritorio normal, sin necesitar un navegador externo.

---

## 2. Arquitectura de capas: la analogía de la fábrica

Imagina una fábrica de procesamiento de texto con estas líneas de producción:

```
┌─────────────────────────────────────────────────────────────────┐
│                        USUARIO                                  │
│              Escribe código en el editor                        │
└───────────────────────┬─────────────────────────────────────────┘
                        │ texto plano
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│   CINTA TRANSPORTADORA 1 — Léxico  lex(src)                     │
│   Rompe el texto en piezas: tokens                              │
│   Salida: [{t:'keyword', v:'if', ln:1, col:1}, ...]             │
└───────────────────────┬─────────────────────────────────────────┘
                        │ array de tokens
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│   CINTA TRANSPORTADORA 2 — Sintaxis  parse(tokens)              │
│   Verifica que las piezas encajen según la gramática            │
│   Salida: árbol AST + log de producciones                       │
└───────────────────────┬─────────────────────────────────────────┘
                        │ AST (objeto JSON con nodos)
                        ▼
┌─────────────────────────────────────────────────────────────────┐
│   PANTALLAS DE VISUALIZACIÓN                                    │
│   - Tabla de tokens     (fase léxica)                           │
│   - Pie chart           (distribución porcentual)               │
│   - Canvas AST          (árbol dibujado)                        │
│   - Log de producciones (reglas gramaticales aplicadas)         │
└─────────────────────────────────────────────────────────────────┘
```

Y encima de todo esto, **la capa de presentación**:

```
┌─────────────────────────────────────────────────────────────────┐
│   app.py (pywebview)  →  abre ventana Windows                   │
│   compilador-final.html  →  toda la lógica                      │
│   app.spec + PyInstaller  →  empaqueta todo en .exe             │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Cómo funciona 100% offline (sin internet)

### El problema original

El HTML original cargaba la fuente tipográfica **Inconsolata** así:

```html
<link href="https://fonts.googleapis.com/css2?family=Inconsolata..." rel="stylesheet">
```

Eso requería internet. Si no hay conexión → la fuente no carga → la app se ve rota.

### La solución: fuentes embebidas en base64

Se descargaron los 5 pesos de Inconsolata (300/400/500/600/700) y se convirtieron a base64 (un formato de texto que representa archivos binarios). Luego se incrustaron directamente en el CSS:

```css
@font-face {
  font-family: 'Inconsolata';
  font-weight: 400;
  src: url('data:font/ttf;base64,AAAEAAAA...'); /* miles de caracteres */
}
```

**Metáfora**: Es como imprimir un diccionario entero dentro del libro en lugar de decir "consulta el diccionario de la biblioteca". La biblioteca puede estar cerrada; el libro nunca.

### ¿Qué más es offline?

| Recurso | Cómo se maneja |
|---------|---------------|
| Fuente Inconsolata | Embebida en base64 dentro del HTML |
| Logo del compilador | Incluido en el exe por PyInstaller |
| Toda la lógica JS | Está dentro del HTML, no en CDN |
| Canvas, CSS, HTML | Todo es nativo del navegador (WebView2 incluido en Windows 10+) |
| `prism.css` / `prism.js` | Incluidos en el exe vía `app.spec` datas |

**No hay ninguna llamada a internet** en ningún momento del ciclo de vida de la app.

---

## 4. `app.py` — El portero

```python
import webview
import os
import sys

def get_path(relative_path):
    # Cuando el exe está corriendo, los archivos se extraen a una
    # carpeta temporal llamada _MEIPASS. Esta función encuentra esa ruta.
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def main():
    path = get_path('compilador-final.html')
    window = webview.create_window(
        'Compilador - Semestre 5',
        path,
        width=1200,
        height=800,
        background_color='#1e1e1e'  # evita destello blanco al cargar
    )
    webview.start()
```

**¿Por qué `_MEIPASS`?**
Cuando PyInstaller crea el exe, comprime todos los archivos dentro de él. Al ejecutarse, los extrae a una carpeta temporal (`_MEIPASS`). Sin esta función, el exe buscaría `compilador-final.html` en el directorio actual del usuario y no lo encontraría.

**¿Por qué `background_color='#1e1e1e'`?**
Sin eso, mientras el HTML carga habría un destello blanco. Con el color de fondo ya configurado en la ventana nativa, la transición es invisible.

**¿Por qué `pywebview` y no Electron/Tauri?**
- pywebview usa **WebView2** (el motor de Edge, ya instalado en Windows 10+). No necesita empaquetar Chromium (que pesa ~100MB extra).
- Es Python puro. No requiere Node.js ni Rust.
- Resultado: el exe pesa ~30MB en lugar de ~200MB.

---

## 5. `app.spec` — El manual de empaque

```python
a = Analysis(
    ['app.py'],           # punto de entrada
    datas=[
        ('compilador-final.html', '.'),     # HTML principal → raíz del exe
        ('prism.css', '.'),                  # estilos de Prism (reservados)
        ('prism.js', '.'),                   # script de Prism (reservado)
        ('assets/Logo_compilador.jpeg', '.') # imagen del logo
    ],
)

exe = EXE(
    ...,
    name='compilador SM',          # nombre del archivo resultante
    console=False,                  # sin ventana de consola negra
    upx=True,                      # compresión UPX → exe más pequeño
    icon=['Logo_compilador.ico'],   # icono del exe en Windows Explorer
)
```

**¿Qué hace cada campo?**

- `datas`: le dice a PyInstaller "estos archivos no son código Python, pero también deben ir dentro del exe". Cada tupla es `(origen, destino_dentro_del_exe)`.
- `console=False`: evita que aparezca una ventana negra de consola al abrir el exe.
- `upx=True`: UPX es un compresor de ejecutables. Reduce el tamaño del exe comprimiendo binarios.
- `icon`: el ícono `.ico` que Windows muestra en el explorador de archivos y en la barra de tareas.

---

## 6. `compilador-final.html` — El corazón del sistema

Este es el archivo más importante. Contiene **todo**: estilos, estructura visual, y los ~1200 líneas de JavaScript que implementan el compilador.

### 6.1 CSS y diseño visual

El tema visual sigue el estilo **VS Code Dark+**. Las variables CSS principales:

```css
:root {
  --bg-main: #1e1e1e;          /* fondo oscuro principal */
  --lexico-color: #FD91C7;     /* rosa/magenta para fase léxica */
  --sintactico-color: #57FF00; /* verde neón para fase sintáctica */
  --font: 'Inconsolata', monospace;
}
```

**¿Por qué variables CSS?**
Permiten cambiar el tema completo cambiando un solo valor. Cada elemento que use `var(--lexico-color)` cambia automáticamente.

**El editor con syntax highlighting** usa una técnica de **overlay**:

```html
<!-- Capa de colores (debajo, no interactiva) -->
<pre id="codeHighlight" aria-hidden="true">
  <code id="codeHighlightCode"></code>
</pre>

<!-- Capa transparente donde escribe el usuario (encima) -->
<textarea id="codeInput" style="-webkit-text-fill-color: transparent;"></textarea>
```

**Metáfora**: Es como escribir en papel de calco encima de una hoja con colores. El usuario escribe en el papel transparente, pero ve los colores de abajo.

La clave técnica: el `textarea` tiene el texto pero lo muestra **transparente** (`-webkit-text-fill-color: transparent`). El `cursor` (palito que parpadea) sigue siendo visible porque es independiente del color del texto. El `<pre>` de abajo muestra el mismo texto pero con los `<span>` de colores.

### 6.2 Estructura HTML (el esqueleto)

```
<body>
├── #pieTooltip              ← tooltip del gráfico de torta
├── .topbar                  ← barra superior con logo, botones de fase, Compilar
├── .main
│   ├── #view-lexico         ← vista de análisis léxico
│   │   ├── .sidebar         ← estadísticas, pie chart, tabla resumen
│   │   ├── .editor-panel    ← editor de código (overlay)
│   │   └── .table-panel     ← tabla de tokens
│   ├── #view-sintactico     ← vista de análisis sintáctico
│   │   ├── .sidebar         ← métricas: nodos, producciones, profundidad
│   │   ├── .editor-panel    ← editor espejo (misma funcionalidad)
│   │   └── .table-panel     ← canvas AST + log de producciones
│   ├── #view-semantico      ← placeholder (próximamente)
│   ├── #view-intermedio     ← placeholder (próximamente)
│   └── #view-optimizacion   ← placeholder (próximamente)
└── .statusbar               ← barra inferior: estado, líneas, chars, errores
```

**¿Por qué vistas separadas en lugar de una sola?**
Cada fase del compilador tiene su propia interfaz. Mostrar/ocultar con `display:flex/none` es instantáneo y mantiene el estado (el código del editor no se borra al cambiar de fase).

### 6.3 El Léxico: `lex(src)`

El léxico es **el análisis más fundamental** del compilador. Su trabajo: convertir una cadena de texto plano en una lista de tokens significativos.

**Metáfora**: Imagina que tienes el texto `"hola mundo 42"`. El léxico es como un escáner que pasa carácter por carácter y dice: `"hola"` → es un identificador, `"mundo"` → es un identificador, `"42"` → es un número.

```javascript
function lex(src) {
  const toks = [];
  let i = 0,   // posición actual en el string
      ln = 1,  // línea actual
      col = 1; // columna actual

  const adv = () => {
    if (src[i] === '\n') { ln++; col = 1; }
    else col++;
    i++;
  };
  // ...
}
```

El léxico opera como una **máquina de estados**. En cada iteración mira el carácter actual `src[i]` y decide qué tipo de token empieza:

| Condición | Tipo de token | Ejemplo |
|-----------|--------------|---------|
| `/*` | Comentario bloque | `/* esto */` |
| `//` o `#` | Comentario línea | `// esto` o `# esto` |
| `"""` o `'''` | String triple | `"""docstring"""` |
| `f"` o `f'` | f-string (Python) | `f"hola {nombre}"` |
| `"` o `'` | String normal | `"hola"` |
| dígito o `.` seguido de dígito | Número | `42`, `3.14`, `0xFF` |
| letra, `_` o `$` | Keyword o Identificador | `if`, `miVariable` |
| todo lo demás | Operador, símbolo, o desconocido | `+`, `{`, `@` |

**¿Por qué este orden importa?**
El orden de las condiciones es crítico. Si el lexer evaluara primero "es una letra" antes de "es una keyword", nunca clasificaría `if` como keyword. Si evaluara números antes que `.`, nunca reconocería `.15` como número válido. El orden es una **decisión de diseño con consecuencias reales**.

Cada token producido tiene esta estructura:
```javascript
{ t: 'keyword',     // tipo
  v: 'if',          // valor (el texto original)
  ln: 3,            // línea donde aparece
  col: 5 }          // columna donde aparece
```

**Los tipos de token:**

| Tipo | Qué representa |
|------|---------------|
| `keyword` | Palabra reservada del lenguaje |
| `identifier` | Nombre de variable, función, clase |
| `number` | Literal numérico (int, float, hex, binario) |
| `string` | Cadena de texto |
| `operator` | Operador (`+`, `==`, `->`, `**=`, etc.) |
| `symbol` | Separador (`;`, `{`, `}`, `(`, `)`, etc.) |
| `comment` | Comentario |
| `unknown` | Carácter no reconocido → error léxico |

### 6.4 Clasificadores de tokens

Una vez que el léxico produce tokens, estas funciones los enriquecen con información semántica para la tabla:

```javascript
function getClasif(tk)    // clasificación principal (ej. "Palabra clave de control")
function getSubClasif(tk) // subclasificación (ej. "Condicional")
function getKWClasif(v)   // clasifica keywords por categoría
function getNumClasif(v)  // "Número entero", "Número flotante", "Número hexadecimal"...
function getOpClasif(v)   // "Aritmético", "Relacional", "Lógico", "Asignación"...
```

**¿Por qué separar esto del léxico?**
El léxico solo necesita saber "¿es esto un token válido?". Las clasificaciones detalladas son para **mostrar al usuario**. Mezclar presentación con análisis haría el código más difícil de mantener.

### 6.5 El Parser: `parse(tokens)`

El parser toma el array de tokens del léxico y verifica que formen **estructuras gramaticales válidas**. Su salida es un **AST (Abstract Syntax Tree)** — un árbol donde cada nodo representa una construcción del lenguaje.

**Metáfora**: Si el léxico es como reconocer las palabras de un idioma, el parser es como verificar que esas palabras formen oraciones gramaticalmente correctas. `"El gato come"` → válido. `"Gato el come"` → inválido.

#### Arquitectura: Recursive Descent Parser

El parser usa la técnica de **descenso recursivo**. Cada función corresponde a una regla gramatical, y las funciones se llaman entre sí (recursivamente) para construir el árbol.

```
parseProgram()
  └─ parseDecl()
       ├─ parseFn()      → if(def/function)
       │    ├─ parseParams()
       │    └─ parseBlockChildren()
       │         └─ parseDecl() (recursivo)
       ├─ parseCls()     → if(class)
       ├─ parseVarDecl() → if(tipo identifier)
       └─ parseStmt()
            ├─ parseIf()
            ├─ parseWhile()
            ├─ parseFor()
            ├─ parsePrintStmt()
            └─ parseExprNode()
                 └─ cadena de precedencia:
                    parseAssignNode()
                      └─ parseTernaryNode()
                           └─ parseOrNode()
                                └─ parseAndNode()
                                     └─ parseEqNode()
                                          └─ parseRelNode()
                                               └─ parseAddNode()
                                                    └─ parseMulNode()
                                                         └─ parseUnaryNode()
                                                              └─ parsePostfixNode()
                                                                   └─ parsePrimaryNode()
```

#### La cadena de precedencia de operadores

Esta es una de las partes más elegantes del parser. **La precedencia de operadores** (que `*` se evalúa antes que `+`) se implementa como una cadena de funciones donde **cada función solo conoce lo que está "por encima" de ella**:

- `parseOrNode` → maneja `||` y `or` (la menor precedencia entre operadores binarios)
- `parseAndNode` → maneja `&&` y `and`
- `parseEqNode` → maneja `==`, `!=`, `===`, `!==`
- `parseRelNode` → maneja `<`, `>`, `<=`, `>=`
- `parseAddNode` → maneja `+`, `-`
- `parseMulNode` → maneja `*`, `/`, `%`, `**` (la mayor precedencia)

**¿Por qué funciona?** Porque `parseMulNode` se llama dentro de `parseAddNode`. Cuando el parser evalúa `2 + 3 * 4`, primero llama a `parseAddNode`, que llama a `parseMulNode` para su operando izquierdo. `parseMulNode` consume `3 * 4` completo. Cuando regresa a `parseAddNode`, el árbol resultante tiene `*` como hijo de `+`, que es exactamente la precedencia correcta.

#### Funciones auxiliares del parser

```javascript
function cur()      // mira el token actual sin consumirlo
function peek(n)    // mira n tokens hacia adelante (lookahead)
function adv()      // consume y devuelve el token actual
function eat(e)     // consume y verifica que sea del tipo/valor esperado
function match(...v) // true si el token actual coincide con alguno de los valores
function N(label, children, meta) // crea un nodo del AST
function lg(ok, msg, rule, ln)    // agrega entrada al log de producciones
```

### 6.6 El Árbol Sintáctico (AST): render y canvas

El AST es dibujado en un elemento `<canvas>` usando la API Canvas 2D del navegador.

#### Paso 1: Layout (`astLayout`)

Calcula el **ancho necesario** para cada nodo de manera bottom-up (de hijos a raíz):
- El ancho de un nodo hoja = ancho del texto + padding
- El ancho de un nodo interno = max(ancho del texto, suma de anchos de hijos + gaps)

```javascript
function astLayout(n) {
  n.children.forEach(astLayout); // primero calcular los hijos
  const totalW = n.children.reduce((s,c) => s + c._w, 0)
                 + (n.children.length - 1) * AST_H_GAP;
  const selfW = measureText(n.label, ...) + 8;
  n._w = Math.max(selfW, totalW);
}
```

#### Paso 2: Posicionamiento (`astAssignPos`)

Asigna coordenadas `x, y` reales a cada nodo de manera top-down (de raíz a hijos):
- La raíz se coloca en el centro superior
- Cada hijo se desplaza horizontalmente para que el grupo de hijos quede centrado bajo el padre

```javascript
const AST_V_GAP = 52;  // distancia vertical entre niveles
const AST_H_GAP = 16;  // espacio mínimo horizontal entre hermanos
```

#### Paso 3: Dibujo (`astDrawNode`)

Para cada nodo dibuja:
1. Las **líneas de conexión** a sus hijos (con curvas Bézier suaves)
2. La **forma del nodo** (rectángulo redondeado para nodos normales, elipse para operadores)
3. El **texto** del label con el color apropiado

```javascript
function nodeStyle(n) {
  // Cada tipo de nodo tiene su color:
  // - funciones → azul (#569CD6)
  // - keywords de control → rojo (#C678DD)
  // - operadores → naranja (#F5A623)
  // - literales → verde (#B5CEA8)
  // - etc.
}
```

**¿Por qué Canvas en lugar de SVG o HTML?**
Canvas es más eficiente para dibujar muchos elementos dinámicos (el árbol puede tener cientos de nodos). SVG crearía miles de elementos DOM. HTML con `div` sería imposible de posicionar correctamente para estructuras de árbol arbitrarias.

**¿Por qué `devicePixelRatio`?**
En pantallas de alta densidad (Retina, pantallas 4K), el canvas aparecería borroso si no se escala. Al multiplicar el tamaño en píxeles por `devicePixelRatio` y reducir con CSS, el dibujo queda nítido.

### 6.7 El gráfico de torta (Pie Chart)

```javascript
const PIE_TYPES = [
  {t:'identifier', lbl:'Identificador', col:'#FF6B6B'},
  {t:'string',     lbl:'Literales',     col:'#4ECDC4'},
  {t:'operator',   lbl:'Operadores',    col:'#FFE66D'},
  // ...
];
```

`drawPie()` dibuja un **donut chart** (torta con agujero central) en canvas. Cada segmento corresponde al porcentaje de tokens de ese tipo sobre el total.

El array `pieSegments` guarda las coordenadas angulares de cada segmento para el **hover**: cuando el mouse pasa sobre la torta, se calcula el ángulo del cursor y se muestra el tooltip con el nombre y porcentaje del segmento.

### 6.8 Detección automática de lenguaje

```javascript
function detectLang(src) {
  const scores = {python:0, javascript:0, 'c/c++':0, java:0};

  // Python: def, from...import, f-strings, None/True/False
  if (/def\s+\w+\s*\(/.test(src)) scores.python += 3;
  // JavaScript: const/let/var, arrow functions, console.log
  if (/\b(const|let|var)\s+\w+\s*=/.test(src)) scores.javascript += 3;
  // C/C++: #include, int main(), cout, cin
  if (/#include\s*[<"]/.test(src)) scores['c/c++'] += 4;
  // Java: public class, System.out.println, public static void main
  if (/public\s+static\s+void\s+main/.test(src)) scores.java += 5;

  // Gana el de mayor puntaje
  const best = Object.entries(scores).sort((a,b) => b[1]-a[1])[0];
  return best[1] > 0 ? best[0] : 'auto';
}
```

Usa **regexes con puntaje acumulativo**. Cada patrón que coincide suma puntos. Al final gana el lenguaje con más puntos. Esto hace la detección **robusta a código mixto** o ambiguo.

### 6.9 El editor con syntax highlighting

**El truco del overlay** ya se explicó en §6.1. Ahora la parte de JavaScript:

```javascript
function lexHighlight(src) {
  // Corre el mismo léxico pero en lugar de tokens, genera HTML con <span>
  // Cada tipo de token tiene su color VS Code Dark+:
  // keyword  → #569CD6  (azul)
  // string   → #CE9178  (salmón/naranja)
  // number   → #B5CEA8  (verde claro)
  // comment  → #6A9955  (verde oscuro)
  // operator → #D4D4D4  (gris claro)
}

function updateHighlight() {
  const src = codeInput.value;
  codeHighlightCode.innerHTML = escH(lexHighlight(src));
}
```

**¿Por qué `escH()`?**
Antes de insertar el texto en el HTML, se escapan los caracteres especiales (`<`, `>`, `&`). Si el usuario escribe `int x = a < b;`, el `<` podría romper el HTML del overlay. Con `escH()` se convierte a `&lt;` que se muestra correctamente.

**El scroll sincronizado:**
```javascript
function syncHighlightScroll() {
  codeHighlight.scrollTop = codeInput.scrollTop;
  codeHighlight.scrollLeft = codeInput.scrollLeft;
}
```

El overlay debe desplazarse exactamente igual que el textarea. Si el usuario hace scroll, el fondo de colores también se mueve.

**El Tab key:**
```javascript
function handleTab(e) {
  if (e.key === 'Tab') {
    e.preventDefault(); // evita que Tab cambie el foco al siguiente elemento
    const start = this.selectionStart;
    const end = this.selectionEnd;
    // Inserta 4 espacios en la posición del cursor
    this.value = this.value.substring(0, start) + '    ' + this.value.substring(end);
    this.selectionStart = this.selectionEnd = start + 4;
  }
}
```

Sin esto, Tab mueve el foco al botón siguiente. Con esto, Tab inserta 4 espacios como en cualquier editor de código.

### 6.10 Sistema de zoom

Cada panel tiene su propio nivel de zoom independiente:

```javascript
let zC = 1;   // zoom editor léxico (codeInput)
let zT = 1;   // zoom tabla de tokens
let zA = 1;   // zoom AST (canvas)
let zC2 = 1;  // zoom editor sintáctico (codeInput2)

// Constantes
const ZS = 0.1;  // step: cada clic sube/baja 10%
const ZMN = 0.5; // mínimo: 50%
const ZMX = 3;   // máximo: 300%
```

`zI(t)` → zoom in, `zO(t)` → zoom out, `zR(t)` → reset a 100%.

`applyZ(t)` aplica el zoom cambiando `fontSize` en CSS y redibuja el AST si aplica.

### 6.11 Barra de estado (Status Bar)

```javascript
function setStatus(s, msg) {
  // s puede ser: 'idle', 'run', 'ok', 'err'
  // Cambia el color del punto y el texto
}
```

| Estado | Color | Significado |
|--------|-------|-------------|
| `idle` | Azul tenue | Esperando |
| `run` | Amarillo | Compilando |
| `ok` | Verde | Sin errores |
| `err` | Rojo | Errores encontrados |

### 6.12 La función `compile()`

Esta es la **directora de orquesta**. Coordina todo el proceso:

```javascript
function compile() {
  const src = codeInput.value || codeInput2.value; // lee el código
  if (!src.trim()) { setStatus('idle', 'Nada que compilar'); return; }

  setStatus('run', 'Compilando…');

  // 1. Análisis léxico
  allToks = lex(src);

  // 2. Actualizar visualizaciones léxicas
  renderTokTable();   // tabla de tokens
  renderStats();      // contadores del sidebar
  drawPie();          // gráfico de torta
  updateExtraInfo();  // líneas, chars, errores

  // 3. Análisis sintáctico
  const {ast, log, nodeCount, errorCount} = parse(allToks);

  // 4. Actualizar visualizaciones sintácticas
  astData = ast;
  renderAST(ast);     // dibuja el árbol en canvas
  renderLog(log);     // muestra las producciones gramaticales

  // 5. Actualizar métricas
  // (nodos, producciones, profundidad, estado, errores)

  // 6. Detectar lenguaje
  document.getElementById('langLabel').textContent = detectLang(src);

  // 7. Actualizar estado final
  setStatus(hasErr ? 'err' : 'ok', ...);
}
```

**¿Por qué no hay un `debounce` activando `compile()` automáticamente al escribir?**
El compilado automático se activa via `Ctrl+Enter` o el botón "Compilar". El highlight se actualiza en tiempo real (con debounce de 400ms), pero el análisis completo solo cuando el usuario lo pide. Esto evita que el compilador se ejecute con código incompleto mientras el usuario está escribiendo.

---

## 7. Flujo completo de ejecución (de principio a fin)

```
1. Usuario hace doble clic en "compilador SM.exe"
   │
2. Windows extrae los archivos a C:\Users\...\AppData\Local\Temp\_MEI12345\
   │  (compilador-final.html, prism.css, prism.js, Logo_compilador.jpeg)
   │
3. app.py se ejecuta:
   │  get_path() → encuentra la ruta correcta con _MEIPASS
   │  webview.create_window() → abre ventana nativa de Windows
   │  webview.start() → carga el HTML en WebView2 (motor de Edge)
   │
4. compilador-final.html se renderiza:
   │  CSS aplica el tema oscuro
   │  Fuentes Inconsolata cargan desde base64 (sin internet)
   │  JS inicializa: initPieCanvas(), tryLoadLogoPath(), updateLineNums()
   │
5. Usuario escribe código en el editor:
   │  updateHighlight() → lexHighlight() → colores en tiempo real
   │  updateLineNums() → actualiza los números de línea
   │  syncHighlightScroll() → mantiene overlay alineado
   │
6. Usuario presiona "Compilar" (o Ctrl+Enter):
   │  compile()
   │  ├─ lex(src) → array de tokens
   │  ├─ renderTokTable() → HTML de la tabla
   │  ├─ drawPie() → canvas del gráfico
   │  ├─ parse(tokens) → árbol AST + log
   │  ├─ renderAST(ast):
   │  │   ├─ astLayout() → calcula anchos
   │  │   ├─ astAssignPos() → asigna coordenadas
   │  │   └─ astDrawNode() → dibuja en canvas
   │  └─ setStatus() → actualiza barra de estado
   │
7. Usuario cambia a pestaña "Sintáctico":
   │  setPhase('sintactico') → oculta view-lexico, muestra view-sintactico
   │  El AST ya está dibujado (compile() ya corrió)
   │
8. Usuario cierra la ventana:
   └─ pywebview destruye la ventana
      Windows limpia la carpeta temporal _MEIPASS
```

---

## 8. Por qué cada decisión técnica

### ¿Por qué un solo archivo HTML?

Facilita el empaquetado con PyInstaller y la distribución. Un solo archivo = un solo `datas` entry. Si hubiera múltiples JS separados, cada uno necesitaría su propia entrada en `app.spec` y su propia lógica de resolución de ruta.

### ¿Por qué JavaScript puro y no React/Vue?

Para un proyecto académico de este tamaño, un framework añadiría complejidad sin beneficio real. Además, los frameworks requieren un proceso de build (npm, webpack, etc.) que complica el empaquetado con PyInstaller.

### ¿Por qué Canvas para el AST?

Alternativas consideradas:
- **SVG**: más declarativo pero el DOM se vuelve lento con >500 nodos
- **D3.js**: excelente para visualizaciones pero requería CDN (offline problem)
- **HTML divs**: imposible posicionar árbol arbitrario con precisión pixel
- **Canvas**: control total, alta performance, funciona offline. ✓

### ¿Por qué Recursive Descent Parser?

Es la técnica más **legible** para implementar un parser. Cada función del código corresponde a una regla gramatical, haciendo la correspondencia directa. Alternativas como parsers LALR o LL(1) requieren construir tablas de análisis que son más eficientes pero mucho más difíciles de implementar y debuggear.

### ¿Por qué el lexer detecta comentarios `#` (Python) y `//` (C/JS) y `/* */`?

El compilador es **polilíngüe** — funciona con Python, JavaScript, C/C++, Java. No detecta el lenguaje antes de lexear; simplemente entiende los patrones de los lenguajes más comunes. Esto hace la experiencia más fluida.

---

## 9. Posibles optimizaciones y mejoras futuras

### Performance

| Mejora | Descripción | Impacto |
|--------|-------------|---------|
| **Web Worker para el léxico/parser** | Mover `lex()` y `parse()` a un hilo separado usando `Worker` | Evita congelar la UI en archivos grandes |
| **Debounce en compile()** | Activar compilación automática con 600ms de delay tras el último keystroke | Feedback en tiempo real sin costo |
| **Caché del AST** | Si el código no cambió, no recalcular el árbol | Acelera el re-render al cambiar de fase |
| **Canvas virtualizado** | Solo dibujar los nodos visibles del AST (viewport culling) | Esencial para árboles de >1000 nodos |

### Funcionalidades pendientes

| Fase | Descripción |
|------|-------------|
| **Análisis Semántico** | Verificar tipos, scopes, variables no declaradas, funciones con argumentos incorrectos |
| **Código Intermedio** | Generar representación de tres direcciones (TAC): `t1 = a + b`, `t2 = t1 * c` |
| **Optimización** | Eliminación de código muerto, propagación de constantes, reducción de potencia |
| **Generación de código** | Traducir el TAC optimizado a ensamblador o bytecode |

### Mejoras al léxico

```javascript
// Actualmente: números en bases especiales se reconocen pero no se diferencian
// Mejora: distinguir entre decimal, hexadecimal, octal, binario
if (/^0x/i.test(v)) return 'Hexadecimal';
if (/^0b/i.test(v)) return 'Binario';
if (/^0o/i.test(v)) return 'Octal';

// Actualmente: strings multilinea de Python (""") se reconocen pero sin color interior
// Mejora: colorear interpolaciones f-string con color diferente
```

### Mejoras al parser

```javascript
// Actualmente: los errores de parseo lanzan excepciones silenciosas
// Mejora: recuperación de errores (error recovery)
// En lugar de abortar, el parser salta tokens hasta encontrar un punto seguro (;, })
// y continúa, reportando todos los errores en una sola pasada
```

### Mejoras al editor

- **Autocompletado**: basado en los identificadores ya definidos en el código
- **Go to definition**: click en un identificador salta a donde se declaró
- **Bracket matching**: resaltar el bracket que cierra al pararse sobre el que abre
- **Múltiples archivos**: tabs con diferentes archivos abiertos simultáneamente

### Mejoras al AST

- **Colapsar nodos**: click en un nodo para ocultar/mostrar su subárbol
- **Tooltip con info**: hover muestra tipo, línea, y valor del token
- **Exportar como imagen**: guardar el árbol como PNG
- **Layout horizontal**: opción para mostrar el árbol de izquierda a derecha

---

## 10. Confirmación offline: qué hay embebido y por qué no se rompe nada

**Checklist de dependencias externas = ninguna:**

- ✅ Fuente Inconsolata → embebida en base64 dentro del HTML (5 pesos × ~80KB cada una)
- ✅ Todo el JavaScript → inline en el HTML, no hay `<script src="https://...">` en el código activo
- ✅ Todo el CSS → inline en el HTML, no hay `@import url(https://...)`
- ✅ Logo → incluido en el exe via PyInstaller `datas`
- ✅ `prism.css` / `prism.js` → incluidos en el exe (aunque no se usan activamente, están ahí por si se necesitan)
- ✅ Motor WebView2 → viene con Windows 10 versión 1803+ y Windows 11 de fábrica

**¿Puede fallar algo?**

| Escenario | ¿Falla? | Por qué |
|-----------|---------|---------|
| Sin internet | No | Todo embebido |
| Windows 7 | Sí (probable) | WebView2 no está disponible en Win7 |
| Windows 10 v1803+ | No | WebView2 incluido |
| Windows 11 | No | WebView2 incluido |
| Antivirus bloquea el exe | Posible | PyInstaller genera exes que algunos AV detectan como falso positivo |
| Ruta con caracteres especiales | No | `get_path()` usa `os.path.join` que maneja esto |
| Pantalla <1200px de ancho | Parcial | El layout tiene `overflow:hidden`, puede requerir scroll horizontal |

---

## 11. Cómo regenerar el exe

Si modificas cualquier archivo fuente, regenera el exe así:

```bash
# 1. Cierra el exe si está abierto (o dará PermissionError)
taskkill /F /IM "compilador SM.exe"

# 2. Entra al directorio del proyecto
cd "ruta/del/proyecto"

# 3. Genera el exe
python -m PyInstaller app.spec --noconfirm

# El exe queda en:  dist/compilador SM.exe
```

**¿Por qué `python -m PyInstaller` y no solo `pyinstaller`?**
En algunos entornos de Windows, `pyinstaller` no está en el PATH del sistema pero sí disponible como módulo de Python. `python -m PyInstaller` siempre funciona si Python está instalado.

---

*Documento generado para el proyecto Compilador SM — Semestre 5, Corte 1.*
*Autor del código: Shalem Rolón. Documentación: Claude Sonnet 4.6.*
