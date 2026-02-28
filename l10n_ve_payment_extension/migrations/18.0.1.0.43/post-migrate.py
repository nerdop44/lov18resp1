import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Forzar actualización del nombre de reporte de retención en todas las traducciones."""
    _logger.info("V8.6 Migration: Actualizando nombres de reportes de retención...")

    # Buscar el ID del reporte retention_voucher_action
    cr.execute("""
        SELECT res_id FROM ir_model_data
        WHERE module = 'l10n_ve_payment_extension'
          AND name = 'retention_voucher_action'
    """)
    result = cr.fetchone()
    if result:
        report_id = result[0]
        new_name = 'Comprobante de Retención con Sello y Firma'

        # En Odoo 17+, campos translate=True almacenan JSONB con idioma como clave
        # Intentar actualizar como JSONB incluyendo todos los idiomas posibles
        try:
            cr.execute("""
                UPDATE ir_act_report_xml
                SET name = jsonb_build_object('en_US', %s, 'es_VE', %s, 'es_ES', %s)
                WHERE id = %s
            """, (new_name, new_name, new_name, report_id))
            _logger.info("V8.6 Migration: Reporte %d actualizado con JSONB: '%s'", report_id, new_name)
        except Exception as e:
            _logger.warning("V8.6 Migration: JSONB falló (%s), intentando texto plano...", e)
            # El cursor está en savepoint, retry con texto plano
            cr.execute("SAVEPOINT report_name_fix")
            try:
                cr.execute("""
                    UPDATE ir_act_report_xml
                    SET name = %s
                    WHERE id = %s
                """, (new_name, report_id))
                cr.execute("RELEASE SAVEPOINT report_name_fix")
                _logger.info("V8.6 Migration: Reporte %d actualizado como texto: '%s'", report_id, new_name)
            except Exception as e2:
                cr.execute("ROLLBACK TO SAVEPOINT report_name_fix")
                _logger.error("V8.6 Migration: No se pudo actualizar reporte: %s", e2)
    else:
        _logger.warning("V8.6 Migration: No se encontró retention_voucher_action en ir_model_data")
