---
name: hka_fiscal_expert
description: Repositorio maestro de conocimiento para el protocolo fiscal HKA/Z1F en Odoo.sh. Centraliza logros, evita regresiones y asegura la trazabilidad del Checksum (LRC) y estructura de tramas.
---

# HKA Fiscal Expert Skill

Este skill centraliza la experiencia acumulada en la integración de Odoo con impresoras fiscales HKA/Z1F (Específicamente modelos como HKA80). Su objetivo es prevenir la pérdida de contexto ante cambios de agente y evitar la repetición de errores de protocolo ya resueltos.

## 🏆 Base de Conocimiento de Logros (Hechos Validados)

1.  **Parámetros de Puerto (Crítico)**:
    - **Baudrate**: 19200 (Fijado tras Self-Test del hardware).
    - **Parity**: `"even"` (Mandatorio).
    - No intentar velocidades automáticas; forzar estos valores en el `setPort`.

2.  **Cálculo de Checksum (LRC) v16 Pure**:
    - **LRC = DATA ^ ETX**. El byte **STX (2) NUNCA entra** en la sumatoria XOR para ningún tipo de comando (Cabecera, Venta o Pago).
    - **VERDAD ABSOLUTA**: Se ha auditado el código fuente funcional de v16 y se ha confirmado que el STX queda fuera. Intentar incluirlo (Resultado 9) causa NAK (21) en los ítems de venta.

3.  **Apertura Documental Estricta**:
    - Se requiere una ráfaga de 6 encabezados para garantizar la apertura: `iR*`, `iS*`, `i00`, `i01`, `i02`, `i03`.
    - El comando `i03` (Información de Referencia) suele actuar como el disparador final para que la impresora entre en estado de factura.

4.  **Estructura de Trama de Venta (Alineación v16 Estricta)**:
    - Formato Estándar (Flag 21 = False): `[Tag][Precio(8)][Cantidad(5)]|[Opción:Código]|[Descripción(30)]`.
    - **Punto Crítico**: v16 usa por defecto 8 dígitos para el precio y 5 para la cantidad. Enviar 10/8 (formato extendido) sin que el flag_21 esté activo provoca un **NAK (21)** por error de sintaxis.
    - **REQUISITO MANDATORIO**: El precio enviado debe ser el **PRECIO BASE** (Sin impuestos).
    - **ESTÉTICA**: Las descripciones deben preservar el caso original (TitleCase).

## 🚫 Tabú de Errores (Lo que NO se debe repetir)

- **ERROR 01**: Incluir el STX en el cálculo del XOR (Basado en falsas premisas de "Resultado 9"). El hardware HKA80 en este entorno espera un LRC puro de la DATA y el ETX.
- **ERROR 02**: Olvidar que el precio tiene 2 decimales implícitos (Precio * 100) y la cantidad 3 (Cantidad * 1000).
- **ERROR 05**: Usar etiquetas en MAYÚSCULAS en los encabezados. v16 usa Label case (`Teléfono: `) para asegurar el ACK y la apertura del documento.

## 🛠️ Instrucciones para Nuevos Agentes

1.  **PRIMER PASO**: Leer íntegramente este `SKILL.md` antes de proponer cualquier cambio al `printing_mixin.js`.
2.  **CONSTRUCCIÓN**: Siempre usar la función `toBytes` con lógica híbrida si el hardware lo requiere.
3.  **TRAZABILIDAD**: Cada versión del módulo Odoo debe reflejar el avance en el manifest y en el plan de implementación.
4.  **REGLA DE ORO**: Si las cabeceras dan ACK y el ítem da NAK, el problema es el Checksum del ítem o la falta de `i03`. No revertir a XOR sin STX para los ítems si ya se probó que fallan.

---
*Este skill es acumulativo. Actualizar con cada nuevo hito confirmado.*
