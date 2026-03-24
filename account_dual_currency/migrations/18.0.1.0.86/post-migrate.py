import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Recalcular tax_today para facturas en borrador que tienen tasa = 1.0 (valor incorrecto)."""
    _logger.info("V8.6 Migration: Recalculando tax_today para facturas con tasa incorrecta...")

    # Buscar la tasa VEF actual desde res_currency_rate
    cr.execute("""
        SELECT rc.id, rcr.rate
        FROM res_currency rc
        LEFT JOIN res_currency_rate rcr ON rcr.currency_id = rc.id
        WHERE rc.name IN ('VEF', 'VES', 'Bs')
        ORDER BY rcr.name DESC
        LIMIT 1
    """)
    result = cr.fetchone()
    if result and result[1]:
        vef_rate = result[1]
        _logger.info("V8.6 Migration: Tasa VEF encontrada: %s", vef_rate)

        # Actualizar tax_today en facturas borrador con tasa = 1.0
        cr.execute("""
            UPDATE account_move
            SET tax_today = %s
            WHERE state = 'draft'
              AND move_type IN ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
              AND (tax_today IS NULL OR tax_today <= 1.0)
              AND tax_today_edited = false
        """, (vef_rate,))
        count = cr.rowcount
        _logger.info("V8.6 Migration: %d facturas actualizadas con tasa %s", count, vef_rate)
    else:
        _logger.warning("V8.6 Migration: No se encontró moneda VEF/VES/Bs en el sistema")
