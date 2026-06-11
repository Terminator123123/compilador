# Compilador — Semestre 5

IDE de escritorio para análisis léxico, sintáctico y semántico. Construido con Python + pywebview.

## Estructura del proyecto

```
compilador/
├── app.py                    # Entry point — lanza la ventana desktop
├── app.spec                  # Configuración de PyInstaller
├── compilador-final.html     # UI principal (producción)
├── prism.css                 # Syntax highlighting (estilos)
├── prism.js                  # Syntax highlighting (lógica)
├── assets/
│   └── Logo_compilador.jpeg  # Logo de la app
├── docs/
│   └── original.html         # HTML base de referencia (no modificar)
└── .gitignore
```

## Requisitos

- Python 3.8+
- `pip install pywebview pyinstaller`

## Generar el ejecutable (.exe)

```bash
python -m PyInstaller app.spec --noconfirm
```

El exe queda en `dist/app.exe`.

> Cerrar `app.exe` antes de regenerar si está abierto.

## Ejecutar en modo desarrollo

```bash
python app.py
```
