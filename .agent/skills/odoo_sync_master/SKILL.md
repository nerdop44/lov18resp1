---
name: odoo_sync_master
description: Sincronizador genérico de submódulos Odoo.sh. Gestiona entornos, SSH y ramas para múltiples clientes.
---

# Odoo Sync Master (Surgical Submodule Deployment)

Este skill automatiza el despliegue quirúrgico de submódulos en Odoo.sh. Permite mantener la coherencia entre el repositorio del cliente (main) y el repositorio de la localización (submodule) sin afectar otros archivos.

## Configuración Inicial (OBLIGATORIA)

Antes de la primera ejecución en un nuevo proyecto, el agente DEBE solicitar al usuario los siguientes parámetros y guardarlos en `.agent/project_context.md` (o en una variable segura si el skill lo requiere):

1.  **SSH de Producción/Prueba**: La URL o alias SSH de los repositorios Odoo.sh.
2.  **Entornos**: Nombres de los entornos (ej. `Produccion`, `Prueba`, `Staging`).
3.  **Ramas de Localización**: La rama remota en el repositorio de submódulo que corresponde a cada entorno.
4.  **Ruta del Submódulo**: La ruta relativa dentro del repositorio principal de Odoo.sh.

## Instrucciones de Uso

### 1. Preparación del Despliegue
- El agente debe verificar `git status` en el submódulo para asegurar que los cambios estén listos.
- Se debe validar que la rama actual coincida con el entorno de destino.

### 2. Ejecución del Script de Sincronización
El skill utiliza un script (`odoo_sync.py`) que realiza los siguientes pasos:
1.  **Push al Submódulo**: Sube los cambios a la rama master del repositorio de localización.
2.  **Push a la Rama de Entorno**: Sube los mismos cambios a la rama específica del entorno (ej. `Produccion`).
3.  **Sincronización Quirúrgica**:
    - Clona el repositorio principal en un directorio temporal.
    - Actualiza SOLO el submódulo específico.
    - Hace commit del nuevo hash y empuja al repositorio principal.

### 3. Versionamiento Obligatorio (CRÍTICO)
Odoo.sh solo ejecuta `-u` (upgrade) sobre módulos cuya **versión en `__manifest__.py`** cambió entre builds. Si no se incrementa la versión, los cambios en vistas XML, datos, traducciones PO y security NO se aplican a la base de datos.

**Regla**: Incrementar SIEMPRE el último dígito de la versión en `__manifest__.py` de CADA módulo modificado antes del commit de despliegue:
```python
# Ejemplo: de 18.0.1.0.83 → 18.0.1.0.84
'version': "18.0.1.0.84",
```

### 4. Verificación Post-Despliegue
- El agente debe recordar al usuario realizar un **Upgrade** del módulo en Odoo.sh una vez que el build sea exitoso.
- El agente debe monitorear el hash del submódulo sincronizado.

## Script Base Adaptable

El script `scripts/odoo_sync.py` debe ser parametrizado para cada proyecto leyendo del contexto o solicitando variables al inicio.

## Reglas de Seguridad
- **NUNCA** exponer claves SSH privadas en los logs.
- **SIEMPRE** usar directorios temporales para el clonado quirúrgico y borrarlos al terminar.
