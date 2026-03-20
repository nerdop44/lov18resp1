---
name: odoo_localization_suite
description: Orquestador maestro de localización Odoo.sh. Centraliza trazabilidad y despliegues quirúrgicos.
---

# Odoo Localization Suite (Master Orchestrator)

Este skill es el punto de entrada único para la gestión de proyectos de Odoo con localización venezolana en Odoo.sh. Su función es coordinar el flujo de trabajo entre los distintos módulos especializados.

## Componentes de la Suite

1.  **[Traceability Manager](file://./../traceability_manager/SKILL.md)**: Gestiona la memoria del proyecto, detecta el entorno y mantiene la bitácora de cambios.
2.  **[Odoo Sync Master](file://./../odoo_sync_master/SKILL.md)**: Ejecuta los despliegues quirúrgicos de submódulos hacia Odoo.sh (Prueba/Producción).

## Flujo de Trabajo Recomendado

### 1. Inicialización (Nuevo Proyecto)
Al detectar que se encuentra en un repositorio de Odoo, el agente debe:
- Consultar el archivo `.agent/project_context.md`.
- Si no existe, invocar al `traceability_manager` para realizar el **Discovery**.
- Configurar las rutas base y los remotos Git.

### 2. Desarrollo y Calidad
- Realizar cambios siguiendo los estándares de Odoo (XML, Python, PO).
- **CRÍTICO**: El agente debe recordar incrementar la versión en el `__manifest__.py` para que Odoo.sh procese el upgrade.

### 3. Sincronización y Validación
- Para enviar a **Prueba**: Invocar al `odoo_sycn_master` indicando la rama `Prueba`.
- Para enviar a **Producción**: Solicitar aprobación final del usuario y ejecutar la sincronización hacia la rama `Produccion`.

## Reglas de Oro de la Suite
- **Agnóstico**: No debe haber rutas "hardcodeadas" fuera del archivo de contexto.
- **Trazable**: Todo deploy debe dejar una marca en la bitácora.
- **Seguro**: Las operaciones de Git deben hacerse en directorios temporales.
