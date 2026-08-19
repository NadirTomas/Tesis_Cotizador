@echo off
REM Paso 12: script de arranque para CotizaLaser
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)
uvicorn app.main:app --reload
