import webview
import os
import sys

def get_path(relative_path):
    # Esta función permite que el EXE encuentre los archivos internos
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def main():
    # Ruta al HTML inteligente
    path = get_path('compilador-final.html')
    
    # Creamos la ventana
    window = webview.create_window(
        'Compilador - Semestre 5', 
        path,
        width=1200,
        height=800,
        background_color='#1e1e1e'
    )
    webview.start()

if __name__ == '__main__':
    main()