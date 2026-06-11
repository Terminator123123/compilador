# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('frontend', 'frontend'),
    ],
    hiddenimports=[
        # Flask y Werkzeug
        'flask',
        'flask.templating',
        'werkzeug',
        'werkzeug.serving',
        'werkzeug.debug',
        'werkzeug.routing',
        'jinja2',
        'click',
        # pywebview
        'webview',
        'webview.platforms',
        'webview.platforms.winforms',
        # Backend del compilador
        'backend',
        'backend.server',
        'backend.lexer',
        'backend.parser',
        'backend.semantic',
        'backend.ast_nodes',
        'backend.codegen',
        'backend.optimizer',
        'backend.object_code',
        'backend.grammar',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'email', 'xml', 'pydoc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Compilador',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='frontend/assets/Logo_compilador.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Compilador',
)
