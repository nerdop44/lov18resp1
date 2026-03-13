import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    _logger.info("Migrating location data: Consolidating and binding Venezuelan States (Idempotent)")
    
    ve_states = {
        'res_country_state_1': 'DC', 'res_country_state_2': 'AM', 'res_country_state_3': 'AZ',
        'res_country_state_4': 'AP', 'res_country_state_5': 'AR', 'res_country_state_6': 'BA',
        'res_country_state_7': 'BO', 'res_country_state_8': 'CB', 'res_country_state_9': 'CJ',
        'res_country_state_10': 'DA', 'res_country_state_11': 'FC', 'res_country_state_12': 'GR',
        'res_country_state_13': 'LR', 'res_country_state_14': 'MD', 'res_country_state_15': 'MR',
        'res_country_state_16': 'MN', 'res_country_state_17': 'NE', 'res_country_state_18': 'PT',
        'res_country_state_19': 'SC', 'res_country_state_20': 'TC', 'res_country_state_21': 'TR',
        'res_country_state_22': 'VA', 'res_country_state_23': 'YC', 'res_country_state_24': 'ZU',
        'res_country_state_25': 'DF'
    }
    
    # 1. Obtener el ID de Venezuela
    cr.execute("SELECT id FROM res_country WHERE code = 'VE' LIMIT 1")
    ve_country = cr.fetchone()
    if not ve_country:
        return
    ve_id = ve_country[0]

    # 2. LIMPIEZA PREVENTIVA: Eliminar XMLIDs del módulo objetivo para estos registros específicos
    # Esto evita el error "duplicate key value violates unique constraint"
    xmlids = list(ve_states.keys())
    cr.execute("DELETE FROM ir_model_data WHERE module = 'l10n_ve_location' AND name IN %s", (tuple(xmlids),))
    _logger.info("Cleared existing XMLIDs for l10n_ve_location to prevent collisions")

    # 3. Vincular registros existentes
    for xmlid, code in ve_states.items():
        cr.execute("SELECT id FROM res_country_state WHERE country_id = %s AND code = %s LIMIT 1", (ve_id, code))
        res = cr.fetchone()
        if res:
            state_id = res[0]
            # Borrar cualquier otra referencia de este registro en ir_model_data (ej. de binaural)
            cr.execute("DELETE FROM ir_model_data WHERE model = 'res.country.state' AND res_id = %s", (state_id,))
            
            # Crear la nueva referencia limpia
            cr.execute("""
                INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
                VALUES (%s, 'l10n_ve_location', 'res.country.state', %s, true)
            """, (xmlid, state_id))
            _logger.info("Linked state %s to l10n_ve_location.%s", code, xmlid)

    # 4. Limpieza de huérfanos de otros modelos geográficos
    cr.execute("""
        DELETE FROM ir_model_data 
        WHERE module = 'l10n_ve_binaural' 
        AND model IN ('res.country.municipality', 'res.country.parish')
    """)
    _logger.info("Migration cleanup completed successfully")
