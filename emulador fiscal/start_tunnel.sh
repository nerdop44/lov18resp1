# Script para crear un túnel seguro para el emulador fiscal
# Usamos localhost.run porque es muy transparente con CORS y HTTPS

echo "--- Iniciando Túnel con LOCALHOST.RUN ---"
echo "Asegúrate de que el emulador esté corriendo en el puerto 5000."
echo "--------------------------------------------------------"
echo "🌐 BUSCA LA URL que termine en .lhr.life abajo"
echo "--------------------------------------------------------"

# Usar localhost.run (Túnel HTTPS directo)
ssh -R 80:localhost:5000 nokey@localhost.run
