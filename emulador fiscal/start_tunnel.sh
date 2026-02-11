#!/bin/bash
# Script para crear un túnel seguro para el emulador fiscal
# Esto soluciona los errores de "Private Network Access" de Chrome

echo "--- Iniciando Túnel para Emulador Fiscal ---"
echo "Asegúrate de que el emulador esté corriendo en el puerto 5000."

# Intentar usar localtunnel (no requiere registro)
if command -v npx &> /dev/null; then
    echo "Usando npx localtunnel..."
    npx localtunnel --port 5000
else
    echo "❌ Error: npx/node no está instalado. Instálalo o usa ngrok."
    echo "Comando sugerido: sudo apt install nodejs npm"
fi
