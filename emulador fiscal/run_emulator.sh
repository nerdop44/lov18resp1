#!/bin/bash

echo "Verificando dependencias del Emulador..."

# Verificar si Python3 está instalado
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python3 no está instalado."
    exit 1
fi

# Verificar si Tkinter está instalado
python3 -c "import tkinter" &> /dev/null

if [ $? -ne 0 ]; then
    echo "⚠️  Tkinter no detectado. Intentando instalar..."
    
    # Detectar gestor de paquetes (básico para Debian/Ubuntu/Fedora)
    if command -v apt-get &> /dev/null; then
        echo "📦 Instalando python3-tk usando apt..."
        sudo apt-get update
        sudo apt-get install -y python3-tk
    elif command -v dnf &> /dev/null; then
        echo "📦 Instalando python3-tkinter usando dnf..."
        sudo dnf install -y python3-tkinter
    else
        echo "❌ No se pudo instalar Tkinter automáticamente. Por favor instale 'python3-tk' manualmente."
        read -p "Presione Enter para salir..."
        exit 1
    fi
    
    # Verificar de nuevo
    python3 -c "import tkinter" &> /dev/null
    if [ $? -ne 0 ]; then
         echo "❌ Error: La instalación falló o requiere reinicio de terminal."
         exit 1
    fi
fi

echo "✅ Dependencias OK. Iniciando Emulador..."
python3 pyfiscal_emulator.py
