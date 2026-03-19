# Sesión de trabajo — Compilador Semestre 5

## Estado actual del proyecto

### Archivos clave
| Archivo | Descripción |
|---|---|
| `original.html` | HTML base original — NO modificar nunca |
| `compilador-final.html` | HTML de producción: original + fuentes offline embebidas |
| `app.py` | Entry point Python con pywebview |
| `app.spec` | Config PyInstaller para generar el exe |
| `dist/app.exe` | Ejecutable final para Windows |

---

## Lo que se hizo en esta sesión

### 1. Exe 100% offline
- El HTML cargaba Inconsolata desde Google Fonts → requería internet.
- Se descargaron las 5 variantes (300/400/500/600/700) y se embebieron como base64.
- `compilador-final.html` = `original.html` + fuentes embebidas. Nada más.

### 2. Corrección app.spec
- El logo real es `Logo_compilador.jpg.jpeg` (extensión doble).
- `app.spec` apuntaba a `Logo_compilador.jpg` → corregido.

### 3. Cómo regenerar el exe
```bash
cd "ruta/del/proyecto"
python -m PyInstaller app.spec --noconfirm
# El exe queda en dist/app.exe
# Cerrar app.exe antes si está abierto
```

---

## En progreso
- [ ] Revisar y corregir solapamiento de nodos hijos en el árbol sintáctico (AST)

---

## Pendiente
- [ ] Agregar syntax highlighting al editor (buffer con colores por tipo de token)
  - Hacerlo SOBRE original.html sin romper AST ni gráfica de tokens
  - Colores propuestos: VS Code Dark+ (keyword azul, string salmón, número verde, etc.)
- [ ] Fases siguientes del compilador: semántico, código intermedio, optimización
