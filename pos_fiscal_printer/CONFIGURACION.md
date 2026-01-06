# Guía de Configuración: Impresora Fiscal

Sigue estos pasos para configurar tu impresora fiscal en la nueva localización `LocVe18v2`.

## 1. Crear la Impresora Fiscal
1.  Dirígete a **Punto de Venta** > **Configuración** > **Impresoras Fiscales** (o busca "Impresoras Fiscales" en el menú principal).
2.  Haz clic en **Nuevo** y completa los campos:
    *   **Nombre**: Un nombre identificativo (ej. `Impresora Caja Principal`).
    *   **Serial**: El serial físico de la impresora (ej. `Z5B...`).
    *   **Puerto Serial**: La ruta del puerto en el servidor/PC (Linux: `/dev/ttyUSB0` o `/dev/ttyACM0`; Windows: `COM3`, `COM4`, etc.).
    *   **Tipo de Conexión**: Selecciona `USB Serial` (Recomendado para la mayoría de modelos HKA/Bixolon).
    *   **Flag 21**: Déjalo en `00` a menos que se indique lo contrario.

## 2. Vincular al Punto de Venta
1.  Ve a **Punto de Venta** > **Configuración** > **Ajustes** (o selecciona tu Punto de Venta específico y ve a sus *Ajustes*).
2.  Busca la sección de **Hardware** o **Impresora Fiscal**.
3.  Activa la opción **Usar Impresora Fiscal**.
4.  En el campo desplegable, selecciona la impresora que creaste en el paso anterior.
5.  Guarda los cambios.

## 3. Verificación
1.  Abre una **Nueva Sesión** en el POS.
2.  Realiza una venta de prueba.
3.  Al validar el pago, la impresora debería emitir el ticket fiscal.
4.  Al cerrar la sesión y realizar el **Cierre de Caja (Z)**, el sistema guardará un "Reporte Z" en Odoo.
5.  **Importante**: Este Reporte Z se enviará automáticamente al **Libro de Ventas** cuando generes el reporte del mes correspondiente.
