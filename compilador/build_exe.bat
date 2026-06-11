@echo off
cd /d "%~dp0"
echo Construyendo el .exe...
echo.
pyinstaller compilador.spec --clean --noconfirm
echo.
if exist "dist\Compilador\Compilador.exe" (
    echo Listo. El ejecutable esta en:
    echo   dist\Compilador\Compilador.exe
) else (
    echo Algo fallo. Revisa los mensajes de error arriba.
)
echo.
pause
