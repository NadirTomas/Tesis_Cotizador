#!/usr/bin/env bash
# Paso 12: script de arranque para CotizaLaser
if [ -f ".venv/bin/activate" ]; then
  source ".venv/bin/activate"
fi
uvicorn app.main:app --reload
