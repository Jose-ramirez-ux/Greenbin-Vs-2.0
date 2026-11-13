@echo off
REM GreenBin - inicia el backend local del panel web (Windows)
REM Usa Python 3.13: con 3.14/3.15 todavia faltan paquetes precompilados (pydantic-core).
cd /d "%~dp0"
if not exist .venv\Scripts\uvicorn.exe (
  if exist .venv rmdir /s /q .venv
  echo Creando el entorno de Python 3.13 por primera vez...
  py -3.13 -m venv .venv
  if errorlevel 1 goto :sinpython
  .venv\Scripts\python -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)
if "%GREENBIN_TOKEN%"=="" set /p GREENBIN_TOKEN=Clave que usara la Raspberry Pi (--token): 
echo.
echo Panel: http://localhost:8000   (Ctrl+C para detener)
echo.
.venv\Scripts\uvicorn app:app --host 0.0.0.0 --port 8000
pause
goto :eof
:sinpython
echo.
echo No se encontro Python 3.13. Instalelo con:   py install 3.13
echo y vuelva a abrir este archivo.
pause
goto :eof
:error
echo.
echo No se pudieron instalar los paquetes. Revise el mensaje de arriba.
if exist .venv rmdir /s /q .venv
pause
