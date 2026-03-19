# Guiones de Presentación — Compilador Semestre 5

---

## GUION 1 — TÚ (Parte técnica: arquitectura y el ejecutable)

---

**[APERTURA]**

"Buenas, voy a explicar cómo construimos este proyecto y las decisiones técnicas que tomamos."

---

**[QUÉ ES EL PROYECTO]**

"Construimos un IDE de escritorio — una aplicación con ventana propia, como cualquier programa instalado — que analiza código fuente y lo pasa por tres fases de compilación: léxica, sintáctica y semántica."

"La interfaz la hicimos en HTML, CSS y JavaScript puro. Pero el reto era: ¿cómo hacemos que eso corra como una aplicación de escritorio sin depender de un navegador ni de internet?"

---

**[PYWEBVIEW — EL PUENTE]**

"La solución fue **pywebview**. Es una librería de Python que toma un archivo HTML y lo abre dentro de una ventana nativa del sistema operativo — en Windows usa el motor del sistema, en Mac usa WebKit."

"Entonces nuestro `app.py` hace básicamente tres cosas:"

1. "Detecta dónde están los archivos — eso lo maneja la función `get_path`, que tiene una lógica especial: cuando el programa corre como `.exe`, los archivos están en una carpeta temporal que PyInstaller crea en memoria, llamada `_MEIPASS`. `get_path` sabe distinguir si está corriendo como script o como ejecutable."

2. "Crea la ventana con `webview.create_window`, le pasa la ruta al HTML, el título, el tamaño y el color de fondo."

3. "Lanza todo con `webview.start()`."

"Son literalmente 15 líneas de código Python. El trabajo real está en el HTML."

---

**[DE SCRIPT A .EXE — PYINSTALLER]**

"Para convertirlo a ejecutable usamos **PyInstaller**. Esta herramienta toma tu script de Python y lo empaqueta junto con el intérprete de Python, todas las librerías que usa, y los archivos adicionales que necesita — en nuestro caso el HTML, el CSS, el JS y el logo."

"Todo eso queda dentro de un solo archivo `.exe` que pesa alrededor de 13MB."

"La configuración está en el archivo `app.spec`. Lo más importante ahí es la sección `datas`, que le dice a PyInstaller qué archivos incluir adentro del ejecutable:"

```
datas=[
  ('compilador-final.html', '.'),
  ('prism.css', '.'),
  ('prism.js', '.'),
  ('assets/Logo_compilador.jpeg', '.')
]
```

"Y el parámetro `console=False` hace que al abrir el `.exe` no aparezca una ventana negra de terminal — solo la ventana de la app."

"Para generarlo simplemente corremos:"

```
python -m PyInstaller app.spec --noconfirm
```

"Y el ejecutable queda en la carpeta `dist/`."

---

**[100% OFFLINE — SIN LLAMADAS EXTERNAS]**

"Una decisión clave fue que todo funciona sin internet. ¿Cómo lo logramos?"

"**Las fuentes tipográficas** están embebidas directamente en el HTML en formato `base64`. En lugar de cargar una fuente de Google Fonts con un `<link>` a internet, convertimos la fuente Inconsolata a base64 y la metimos en el CSS con `@font-face { src: url('data:font/ttf;base64,...') }`. Eso significa que aunque no haya red, la fuente siempre está ahí."

"**El analizador léxico** está implementado completamente en JavaScript dentro del HTML — la función `lex()`. No llama a ninguna API, no manda el código a un servidor. Todo el análisis ocurre en la máquina del usuario, en tiempo real."

"**El analizador sintáctico** igual — la función `parse()` implementa un parser de descenso recursivo en JavaScript puro."

"No hay ningún `fetch()`, ningún `XMLHttpRequest`, ningún CDN. El archivo HTML es completamente autosuficiente."

---

**[CIERRE]**

"En resumen: HTML para la interfaz, JavaScript para la lógica de compilación, pywebview para convertirlo en app de escritorio, y PyInstaller para empaquetarlo en un solo ejecutable. Sin internet, sin servidores, sin dependencias externas en tiempo de ejecución."

---
---

## GUION 2 — TU COMPAÑERA (Parte funcional: qué hace el compilador)

---

**[APERTURA]**

"Voy a explicar qué hace el compilador, cómo funciona por dentro y qué puede analizar."

---

**[QUÉ ANALIZA]**

"El compilador acepta código fuente en varios lenguajes — detecta automáticamente si es Python, JavaScript, C, Java u otros — y lo pasa por tres fases de análisis."

"Tiene dos áreas de código: una principal y una secundaria, para poder comparar dos fragmentos al mismo tiempo."

---

**[FASE 1 — ANÁLISIS LÉXICO]**

"La primera fase es el **análisis léxico**. El lexer lee el código carácter por carácter y lo divide en tokens — las unidades mínimas con significado."

"Reconoce estos tipos de tokens:"

- **Palabras clave** — `if`, `while`, `for`, `def`, `int`, `return`...
- **Identificadores** — nombres de variables y funciones
- **Números** — enteros, decimales, hexadecimales, binarios
- **Operadores** — `+`, `-`, `=`, `==`, `>=`, `&&`...
- **Símbolos** — paréntesis, corchetes, llaves, punto y coma
- **Strings** — texto entre comillas simples o dobles
- **Comentarios** — líneas con `//` o bloques `/* */`
- **Errores léxicos** — caracteres que no pertenecen al lenguaje

"Cada token se muestra en una tabla con su valor, tipo, clasificación, sub-clasificación, y la línea y columna donde aparece en el código."

"También muestra estadísticas visuales: cuántos tokens de cada tipo hay, con gráficas de torta y barras."

---

**[FASE 2 — ANÁLISIS SINTÁCTICO]**

"La segunda fase es el **análisis sintáctico**. Toma los tokens del paso anterior y verifica que estén ordenados correctamente según las reglas del lenguaje — la gramática."

"Implementamos un parser de **descenso recursivo**, que es uno de los métodos más usados en compiladores reales. El parser construye un árbol sintáctico — cada nodo representa una estructura del programa: una función, un bloque `if`, un `while`, una declaración de variable."

"El resultado se muestra como un árbol interactivo que se puede expandir y contraer. Al lado aparece un log con tres columnas: el mensaje de lo que se detectó, la línea del código donde ocurrió, y la **regla gramatical** que se aplicó."

"Esa columna de regla es la que puede parecer extraña al principio — muestra cosas como `Programa → Decl*` o `FuncDef → tipo ID '(' Params ')' Bloque`. Eso es notación formal de gramática: el símbolo `→` significa 'se compone de'. Es la manera técnica de decir, por ejemplo, que una función está formada por un tipo de retorno, un nombre, paréntesis con parámetros y un bloque de código. Cada vez que el parser reconoce una estructura — un if, un while, una función — registra exactamente qué regla usó para reconocerla. Eso es lo que vemos ahí."

"Reconoce estructuras de Python y de C/Java al mismo tiempo: funciones con `def` y con tipo de retorno, bloques con indentación y con llaves, bucles `for` y `while`, condicionales `if/else`."

---

**[FASE 3 — SEMÁNTICO]**

"La tercera fase, el **análisis semántico**, está marcada como 'en desarrollo'. En un compilador real esta fase verifica que el código tiene sentido — que no uses una variable sin declararla, que los tipos coincidan. Está preparada la sección para implementarla."

---

**[DETECCIÓN DE LENGUAJE]**

"Algo que le da valor al proyecto es la **detección automática de lenguaje**. Cuando pegas código, el sistema analiza patrones: si tiene `def` y `:` es Python, si tiene `{` y `;` es C o Java, si tiene `=>` o `const` es JavaScript. Le da una puntuación a cada lenguaje y muestra cuál es el más probable."

---

**[LA INTERFAZ]**

"La interfaz tiene un diseño tipo terminal con tema oscuro. El editor resalta la sintaxis en tiempo real mientras escribís. Podés filtrar los tokens por tipo haciendo click en las estadísticas. Y todo responde sin latencia porque no hay red — el análisis es instantáneo."

---

**[CIERRE]**

"En resumen: es un compilador de las dos primeras fases — léxico y sintáctico — que funciona en tiempo real, reconoce múltiples lenguajes, y corre como aplicación de escritorio sin necesitar internet."

---
