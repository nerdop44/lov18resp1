---
name: traceability_manager
description: Mantiene el contexto, detecta variables de entorno y asegura la trazabilidad entre sesiones.
---

# Traceability Manager (Global & Auto-discovery)

Este skill actúa como la "memoria viva" del proyecto. Su prioridad es mantener la continuidad sin interrogar constantemente al usuario.

## Regla Importante: Idioma
**EL IDIOMA DE TRABAJO ES ESPAÑOL.**

## Flujo de Trabajo

### 1. Fase de Descubrimiento (Inicio de Sesión)

Al iniciar, el agente debe leer `.agent/project_context.md`.

#### A. Si el contexto está incompleto o es nuevo:
El agente DEBE intentar **autocompletar** las variables buscando en el entorno:
1.  **Nombre del Repositorio**: Ejecutar `git remote -v` en los directorios de trabajo.
2.  **Rama Actual**: Ejecutar `git branch --show-current`.
3.  **Entorno Staging (Odoo.sh)**: Buscar en el historial de conversaciones recientes o archivos de configuración (`.conf`, `.ower`, etc.) patrones como `*.odoo.com`.
4.  **Credenciales**: Buscar referencias a credenciales en variables de entorno o archivos seguros conocidos (NO mostrar valores reales, solo referencias).

#### B. Validación (Política de Silencio)
-   **Primera Vez**: Si el contexto se acaba de generar o completar, mostrar un resumen al usuario y pedir confirmación: *"He detectado este entorno (Repo X, Rama Y, Staging Z). ¿Es correcto?"*.
-   **Sesiones Siguientes**: Si las variables detectadas coinciden con las del archivo de contexto, **PROCEDER EN SILENCIO**. No preguntar nada.
-   **Cambios Detectados**: SOLO si el agente detecta una discrepancia (ej. se cambió de rama `dev` a `master`, o de repo `lov18resp1` a `LocVe`), debe actualizar el contexto y notificar: *"Detecté un cambio de contexto a X. Actualizando trazabilidad."*.

### 2. Lógica de Localización
El agente debe leer la variable `[TIPO_LOCALIZACION]` del contexto y adaptar su comportamiento:
-   **`lov18resp1`**: Usar lógica base. Ignorar módulos extendidos (POS/Nómina extra).
-   **`LocVe`**: Habilitar lógica extendida para módulos adicionales.

### 3. Bitácora Automática
Cada acción relevante debe registrarse automáticamente en la bitácora del contexto.

### 4. Protocolo Anti-Congelamiento (Sesiones Largas)

En operaciones largas (múltiples archivos, commits, deploys), el agente DEBE:

1. **Dividir en sub-pasos confirmables**: Nunca ejecutar más de 3-4 archivos por ciclo de herramientas sin verificar.
2. **Publicar un checkpoint intermedio**: Cada vez que concluya un bloque de trabajo (ej. "Fixes 1-3 listos"), emitir un resumen con `notify_user` indicando estado y siguiente paso pendiente, AUNQUE el usuario no lo haya pedido.
3. **Siempre verificar antes de asumir**: Al regresar de un posible congelamiento, ejecutar `git status` y revisar archivos modificados antes de continuar.
4. **En caso de freeze detectado por el usuario**: Responder con:
   - Un resumen de qué se completó (`git status`, archivos nuevos/modificados).
   - Los pasos pendientes que faltan.
   - Una propuesta de plan de recuperación.
5. **Commits parciales son seguros**: Si el proceso se corta, hacer commit de lo aplicado hasta ese punto con mensaje `"WIP: [descripción]"` antes de continuar.

### 5. Gestión de Puntos de Retorno (Green State)

Cuando se alcance un "Green Build" (Build Verde) en Odoo.sh tras un periodo de inestabilidad, el agente DEBE:

1.  **Identificar el Hash Crítico**: Registrar el commit exacto del repositorio principal y de la localización que permitieron el verde.
2.  **Crear Punto de Rollback**: Generar una rama o tag de respaldo (ej. `stable-green-YYYYMMDD`) para facilitar el retorno inmediato ante futuras regresiones.
3.  **Actualizar el Contexto**: Registrar estos parámetros en `.agent/project_context.md` bajo una sección de "Estado Verde Actual".
4.  **Preservar Parámetros**: Si el éxito dependió de configuraciones específicas (ej. flags de compilación, versiones de dependencias), documentarlos explícitamente para evitar revertirlos accidentalmente.
### 6. Estándar de Despliegue (Source of Truth)

Para evitar regresiones y builds amarillos/naranjas en Odoo.sh:

1. **El repositorio del proyecto NO DEBE CLONARSE NI USARSE LOCALMENTE (`repo_krill`)**: Nunca intentes sincronizar usando una carpeta `repo_krill`.
2. **Push SOLO a Odoo.sh**: El código de la localización se sube a GitHub (`nerdop44/lov18resp1`) en sus respectivas ramas (ej. `Prueba`).
3. **Despliegue a Odoo.sh**: Odoo.sh (entorno staging) toma directamente de Github el código de la localización. Si necesitas forzar una recarga en Odoo.sh, usa el script proporcionado por el usuario o haz un commit vacío en la rama correcta (`Prueba`) de la localización. **NUNCA hagas push a la rama `master` del repositorio principal (krill.git)** en Odoo.sh, ya que creará un entorno de desarrollo no deseado.
4. **Limpieza de Build**: No se permiten `SyntaxWarnings` (ej. espacios tras `\`, `is` con literales). Cualquier advertencia detectada en los logs de Odoo.sh debe ser tratada como prioridad para mantener el estado "Green".
5. **Logs y Errores Reales**: Siempre verifica los logs internos de Odoo.sh (`/home/odoo/logs/update.log` o `odoo.log`) dentro de la instancia que esté fallando para encontrar el Traceback exacto, en lugar de adivinar el error.
