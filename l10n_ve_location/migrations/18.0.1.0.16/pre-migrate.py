import logging

_logger = logging.getLogger(__name__)

def migrate(cr, version):
    _logger.info("Migrating location data: Binding existing Venezuelan States to XMLIDs")
    
    # 1. Definir los códigos de estados
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
    
    # 2. Obtener el ID de Venezuela
    cr.execute("SELECT id FROM res_country WHERE code = 'VE' LIMIT 1")
    ve_country = cr.fetchone()
    if not ve_country:
        return
    ve_id = ve_country[0]

    # 3. Vincular registros existentes
    for xmlid, code in ve_states.items():
        # Buscar si ya existe el estado por código
        cr.execute("SELECT id FROM res_country_state WHERE country_id = %s AND code = %s LIMIT 1", (ve_id, code))
        res = cr.fetchone()
        if res:
            state_id = res[0]
            # Verificar si ya tiene un XMLID
            cr.execute("SELECT id FROM ir_model_data WHERE model = 'res.country.state' AND res_id = %s", (state_id,))
            if not cr.fetchone():
                # Si no tiene XMLID, crearle el de l10n_ve_location para que Odoo no intente crear uno nuevo
                cr.execute("""
                    INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
                    VALUES (%s, 'l10n_ve_location', 'res.country.state', %s, true)
                """, (xmlid, state_id))
                _logger.info("Bound existing state %s to XMLID l10n_ve_location.%s", code, xmlid)
            else:
                # Si ya tiene XMLID pero de otro módulo (ej. l10n_ve_binaural o base), actualizarlo a l10n_ve_location
                cr.execute("""
                    UPDATE ir_model_data 
                    SET module = 'l10n_ve_location', name = %s
                    WHERE model = 'res.country.state' AND res_id = %s
                """, (xmlid, state_id))
                _logger.info("Updated XMLID for state %s to l10n_ve_location.%s", code, xmlid)

    # 4. Limpiar XMLIDs antiguos del módulo binaural para evitar conflictos
    cr.execute("""
        DELETE FROM ir_model_data 
        WHERE module = 'l10n_ve_binaural' 
        AND model IN ('res.country.state', 'res.country.municipality', 'res.country.parish')
    """)
