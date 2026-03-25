# Contexto del Proyecto: DEVENALSA (Odoo 18)

## Estrella del Norte
Estabilización y despliegue de la localización venezolana Fase 92 en Odoo.sh para Devenalsa.

## Configuración del Entorno
- **Repositorio Local**: `/home/nerdop/Laboratorio/Clientes Odoo/Por Cimas/Devenalsa`
- **Submódulo Localización**: `lov18resp1` (rama remota `nerdop44/lov18resp1`)
- **Rama de Trabajo (Verdad)**: `devenalsa`
- **Repositorio Odoo.sh**: `tbriceno65/Devenalsa`
- **SSH Alias Odoo.sh**: `25365911`

## Variables de Sincronización
[REPO_SUBMODULE_PATH]: /home/nerdop/Laboratorio/Clientes Odoo/Por Cimas/Devenalsa/lov18resp1
[MAIN_REPO_SSH]: git@github.com:tbriceno65/Devenalsa.git
[SUBMODULE_PATH_IN_MAIN]: lov18resp1

## Reglas Obligatorias para el Agente (A.I. Traceability & Handoff)
1. **Lectura Fundamental de Contexto**: Todo agente de IA, al inicializar una sesión o retomar este proyecto, DEBE leer y asimilar íntegramente este documento ANTES de ejecutar o proponer cualquier acción. Esto evitará perder el hilo, ejecutar código heredado y sufrir alucinaciones que pongan en riesgo el proyecto.
2. **La Regla de Oro**: La rama `devenalsa` del submódulo es la **Fuente de Verdad única**. Los despliegues a `Producción` y `prueba-02` del maestro SIEMPRE deben rastrear esta rama tras pasar por verificaciones ("Green Build").
3. **Protocolo de Relevo Predictivo (Handoff)**: Si el agente prevé que la interacción requiere de muchos pasos o la cuota/contexto de sesión está por expirar, el agente debe generar de manera proactiva un archivo de "estado de relevo" detallando lo que se estaba haciendo, las dependencias manipuladas y las tareas pendientes. De este modo, el siguiente agente leerá dicho contexto inicializando donde quedó el anterior.
4. **Idioma Estricto**: Toda comunicación con el usuario, elaboración de planes, comentarios y cualquier artefacto generado debe realizarse **estrictamente en idioma español**.
5. **Plan de Acción y Aprobación Previa (Control Total)**: El agente está **obligado** a elaborar y someter a revisión un plan detallado de la solución propuesta ANTES de realizar cualquier modificación, escritura o borrado de código. Es mandatorio no proceder de ninguna forma con los cambios sin haber recibido la aprobación explícita del usuario.

## Bitácora
- [2026-03-20 10:40]: **PURGA INTEGRAL**. Eliminación de contexto v162 discordante. Restauración absoluta a Fase 92 (v92). Rama de trabajo fijada en `devenalsa`.
- [2026-03-25]: **Actualización de Entorno**. Repositorio movido a nueva ruta local `/home/nerdop/Laboratorio/Clientes Odoo/Por Cimas/Devenalsa`. Se establecen Reglas de Agente obligatorias para asegurar la trazabilidad y el relevo de sesiones.
