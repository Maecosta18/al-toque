@echo off
cd /d "%~dp0"
echo ============================================
echo   Al Toque - instalando y arrancando...
echo ============================================
echo.
echo Instalando dependencias (puede tardar un minuto la primera vez)...
pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo No se pudo instalar con "pip". Probando con "pip3"...
    pip3 install -r requirements.txt
)

if not exist al_toque.db (
    echo.
    echo Cargando datos de ejemplo...
    python seed.py
    if errorlevel 1 python3 seed.py
)

echo.
echo Abriendo el navegador en unos segundos...
start "" cmd /c "timeout /t 3 >nul && start http://localhost:5000"

echo.
echo ============================================
echo   Al Toque corriendo en http://localhost:5000
echo   Dejá esta ventana abierta mientras la uses.
echo   Para cerrarla: Ctrl+C y despues cualquier tecla.
echo ============================================
echo.
python app.py
if errorlevel 1 python3 app.py

pause
