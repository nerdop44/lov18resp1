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

2.  **Cálculo de Checksum (LRC) Híbrido**:
    - **Comandos de Cabecera e Información (`i`)**: El LRC es `DATA ^ ETX`. El byte **STX (2) NO entra** en la sumatoria XOR. (Validado con ACKs en v94/v95).
    - **Comandos de Venta y Pago (`!`, ` `, `"`, `#`, `2`)**: El LRC **SÍ DEBE incluir al STX (2)**. `STX ^ DATA ^ ETX`. Esto es lo que produce el "Resultado 9" esperado por el firmware para autorizar la venta.

3.  **Apertura Documental Estricta**:
    - Se requiere una ráfaga de 6 encabezados para garantizar la apertura: `iR*`, `iS*`, `i00`, `i01`, `i02`, `i03`.
    - El comando `i03` (Información de Referencia) suele actuar como el disparador final para que la impresora entre en estado de factura.

4.  **Estructura de Trama de Venta**:
    - Formato: `[Tag][Precio(10)][Cantidad(8)]|[Opción:Código]|[Descripción(30)]`.
    - Los pipes `|` son opcionales según el modelo, pero usarlos alinea el protocolo con la v16 estable.

## 🚫 Tabú de Errores (Lo que NO se debe repetir)

- **ERROR 01**: Calcular un solo XOR para todos los comandos. El hardware es sensible al tipo de comando para el checksum.
- **ERROR 02**: Olvidar que el precio tiene 2 decimales implícitos (Precio * 100) y la cantidad 3 (Cantidad * 1000).
- **ERROR 03**: Usar `padEnd` en la descripción. La trama debe terminar exactamente donde termina el texto o en el límite de 30/40 caracteres.
- **ERROR 04**: Ignorar la respuesta `NAK (21)`. Un NAK en el ítem `!` suele ser un error de Checksum o de apertura de documento incompleta.

## 🛠️ Instrucciones para Nuevos Agentes

1.  **PRIMER PASO**: Leer íntegramente este `SKILL.md` antes de proponer cualquier cambio al `printing_mixin.js`.
2.  **CONSTRUCCIÓN**: Siempre usar la función `toBytes` con lógica híbrida si el hardware lo requiere.
3.  **TRAZABILIDAD**: Cada versión del módulo Odoo debe reflejar el avance en el manifest y en el plan de implementación.
4.  **REGLA DE ORO**: Si las cabeceras dan ACK y el ítem da NAK, el problema es el Checksum del ítem o la falta de `i03`. No revertir a XOR sin STX para los ítems si ya se probó que fallan.

---
*Este skill es acumulativo. Actualizar con cada nuevo hito confirmado.*
