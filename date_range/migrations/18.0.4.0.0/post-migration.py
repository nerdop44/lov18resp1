import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    if not version:
        return

    # Verificar si la tabla de la relación m2m existe antes de migrar
    cr.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'date_range_res_company_rel'")
    if cr.fetchone():
        _logger.info("Migrating date_range company_id from many2many relation")
        # Actualizar company_id desde la relación m2m si la columna company_id está vacía
        cr.execute("""
            UPDATE date_range dr
            SET company_id = drrcr.res_company_id
            FROM date_range_res_company_rel drrcr,
                 date_range_type drt
            WHERE
                dr.id = drrcr.date_range_id
                AND drt.id = dr.type_id
                AND (drt.company_id IS NULL OR drt.company_id = drrcr.res_company_id)
                AND dr.company_id IS NULL
        """)

    # Actualizar la regla de registro usando el Environment
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    rule = env.ref("date_range.date_range_comp_rule", raise_if_not_found=False)
    if rule:
        rule.domain_force = "['|',('company_id', 'in', company_ids),('company_id','=',False)]"
