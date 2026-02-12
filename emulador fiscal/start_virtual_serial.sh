#!/bin/bash
# Script AVANZADO para secuestrar un puerto serial físico y redirigirlo al emulador
# Esto hace que Chrome vea el puerto virtual como si fuera hardware real.

PORT_POS="/tmp/ttyPOS"
PORT_EMU="/tmp/ttyEMU"
TARGET_DEV="/dev/ttyS0"
BACKUP_DEV="/dev/ttyS0.original"

echo "--- INICIANDO SECUESTRO DE PUERTO SERIAL PARA CHROME ---"
echo "🖥️  Odoo usará: $TARGET_DEV (redirigido)"
echo "🖨️  Emulador usará: $PORT_EMU"
echo "--------------------------------------------------------"

# Función de limpieza para restaurar el sistema al salir
cleanup() {
    echo -e "\n--- Restaurando sistema ---"
    sudo rm -f "$TARGET_DEV"
    if [ -e "$BACKUP_DEV" ]; then
        sudo mv "$BACKUP_DEV" "$TARGET_DEV"
        echo "✅ Puerto $TARGET_DEV restaurado."
    fi
    rm -f "$PORT_POS" "$PORT_EMU"
    kill $SOCAT_PID 2>/dev/null
    exit
}

# Capturar Ctrl+C
trap cleanup SIGINT

# 1. Backup del puerto real si no se ha hecho ya
if [ ! -e "$BACKUP_DEV" ]; then
    echo "Guardando backup de $TARGET_DEV..."
    sudo mv "$TARGET_DEV" "$BACKUP_DEV"
fi

# 2. Iniciar socat en segundo plano
rm -f "$PORT_POS" "$PORT_EMU"
socat -d -d PTY,link="$PORT_POS",raw,echo=0,mode=666 PTY,link="$PORT_EMU",raw,echo=0,mode=666 &
SOCAT_PID=$!

sleep 1

# 3. Crear el puente falso en /dev/ttyS0
PTS_DEV=$(readlink -f "$PORT_POS")
sudo ln -sf "$PTS_DEV" "$TARGET_DEV"
sudo chmod 666 "$TARGET_DEV"

echo "🎯 ¡ÉXITO! Ahora selecciona '$TARGET_DEV' en Chrome."
echo "Presiona Ctrl+C para detener y restaurar el puerto original."

wait $SOCAT_PID
