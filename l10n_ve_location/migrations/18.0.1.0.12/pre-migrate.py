import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    _logger.info("Migrating location data: Critical cleanup for Venezuelan States (res.country.state)")
    
    # 1. Definir los códigos de estados que manejamos en nuestra data
    ve_state_codes = [
        'DC', 'AM', 'AZ', 'AP', 'AR', 'BA', 'BO', 'CB', 'CJ', 'DA', 
        'FC', 'GR', 'LR', 'MD', 'MR', 'MN', 'NE', 'PT', 'SC', 'TC', 
        'TR', 'VA', 'YC', 'ZU', 'DF'
    ]
    
    # 2. Obtener el ID de Venezuela
    cr.execute("SELECT id FROM res_country WHERE code = 'VE' LIMIT 1")
    ve_country = cr.fetchone()
    if not ve_country:
        _logger.warning("Venezuela country not found, skipping migration cleanup")
        return
    ve_id = ve_country[0]

    # 3. Transferencia de Propiedad de XMLIDs
    cr.execute("""
        UPDATE ir_model_data imd1
        SET module = 'l10n_ve_location'
        WHERE imd1.module = 'l10n_ve_binaural' 
        AND imd1.model IN ('res.country.state', 'res.country.municipality', 'res.country.parish')
        AND NOT EXISTS (
            SELECT 1 FROM ir_model_data imd2 
            WHERE imd2.module = 'l10n_ve_location' 
            AND imd2.name = imd1.name
            AND imd2.model = imd1.model
        )
    """)
    _logger.info("Successfully transferred %d XMLID records to l10n_ve_location", cr.rowcount)

    # 4. LIMPIEZA AGRESIVA DE DUPLICADOS
    for code in ve_state_codes:
        cr.execute("SELECT id FROM res_country_state WHERE country_id = %s AND code = %s", (ve_id, code))
        ids = [r[0] for r in cr.fetchall()]
        
        if len(ids) > 1:
            _logger.info("Found %d duplicate records for state code %s", len(ids), code)
            cr.execute("""
                SELECT res_id FROM ir_model_data 
                WHERE model = 'res.country.state' 
                AND module = 'l10n_ve_location' 
                AND res_id IN %s
            """, (tuple(ids),))
            id_with_xmlid = cr.fetchone()
            
            keep_id = id_with_xmlid[0] if id_with_xmlid else min(ids)
            to_delete = [i for i in ids if i != keep_id]
            cr.execute("DELETE FROM res_country_state WHERE id IN %s", (tuple(to_delete),))
            _logger.info("Deleted duplicate state records for %s: %s", code, to_delete)

    # 5. Borrar rastro de l10n_ve_binaural
    cr.execute("""
        DELETE FROM ir_model_data
        WHERE module = 'l10n_ve_binaural'
        AND model IN ('res.country.state', 'res.country.municipality', 'res.country.parish')
    """)
    _logger.info("Surgical removal of old binaural metadata completed")
