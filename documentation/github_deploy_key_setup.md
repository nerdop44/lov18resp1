# Configuración de Deploy Key para Rebuilds Automáticos en Odoo.sh

## Problema
El script `update_odoosh.sh` no puede hacer push al repositorio `AnimalCenter` porque el servidor de Odoo.sh no tiene una clave SSH con permisos de escritura.

## Solución
Agregar la clave SSH del servidor de Odoo.sh como Deploy Key en GitHub.

## Pasos para Configurar

### 1. Copiar la Clave Pública

La clave pública ya fue generada en el servidor de Odoo.sh:

```
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIJ8cBj5MC4mxDOXx/0TIBaPCQ9knHpqpZZ8xu0yMjhn1 odoosh-animalcenter-deploy
```

### 2. Agregar Deploy Key en GitHub

1. Ve a: https://github.com/tbriceno65/AnimalCenter/settings/keys
2. Haz clic en **"Add deploy key"** (botón verde)
3. Completa el formulario:
   - **Title:** `Odoo.sh Prueba Server - Auto Rebuild`
   - **Key:** Pega la clave pública de arriba
   - ✅ **Marca "Allow write access"** (MUY IMPORTANTE)
4. Haz clic en **"Add key"**

### 3. Verificar que Funciona

Una vez agregada la clave, ejecuta este comando para probar:

```bash
ssh 27984180@tbriceno65-animalcenter-prueba-27984180.dev.odoo.com \
  "cd ~/src/user && git remote -v && ssh -T git@github.com 2>&1 | head -5"
```

Deberías ver un mensaje como: `Hi tbriceno65/AnimalCenter! You've successfully authenticated...`

### 4. Disparar Rebuild

Después de agregar la clave, usa este comando para disparar rebuilds:

```bash
cd /home/nerdop/laboratorio/LocVe18v2
./tools/trigger_odoosh_rebuild.sh
```

## Alternativa: Usar la Clave "pajarolandia" Existente

Si prefieres usar la clave "pajarolandia-LocVe18v2" que ya existe en GitHub:

1. Necesitas encontrar la clave privada correspondiente
2. Copiarla al servidor de Odoo.sh en `~/.ssh/id_pajarolandia`
3. Actualizar el SSH config para usar esa clave

## Notas

- La clave "pajarolandia-LocVe18v2" ya tiene permisos de lectura/escritura en GitHub
- Fue agregada el 28 de enero de 2026
- Si encuentras esa clave privada, sería más rápido usarla
- De lo contrario, agregar la nueva clave `odoosh-animalcenter-deploy` es la mejor opción
