
def migrate(cr, version):
    # Mapeo explícito según res_country_state_data.xml de la localización operativa
    # Esto asegura que cada código se asigne a su XML ID exacto, evitando que Odoo
    # intente crear o renombrar registros de forma que colisionen con los existentes.
    state_mapping = {
        'DC': 'res_country_state_1', 'AM': 'res_country_state_2', 'AZ': 'res_country_state_3',
        'AP': 'res_country_state_4', 'AR': 'res_country_state_5', 'BA': 'res_country_state_6',
        'BO': 'res_country_state_7', 'CB': 'res_country_state_8', 'CJ': 'res_country_state_9',
        'DA': 'res_country_state_10', 'FC': 'res_country_state_11', 'GR': 'res_country_state_12',
        'LR': 'res_country_state_13', 'MD': 'res_country_state_14', 'MR': 'res_country_state_15',
        'MN': 'res_country_state_16', 'NE': 'res_country_state_17', 'PT': 'res_country_state_18',
        'SC': 'res_country_state_19', 'TC': 'res_country_state_20', 'TR': 'res_country_state_21',
        'VA': 'res_country_state_22', 'YC': 'res_country_state_23', 'ZU': 'res_country_state_24',
        'DF': 'res_country_state_25'
    }
    
    for code, xml_id in state_mapping.items():
        cr.execute("""
            INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
            SELECT %s, 'l10n_ve_location', 'res.country.state', id, false
            FROM res_country_state 
            WHERE country_id = (SELECT id FROM res_country WHERE code = 'VE')
            AND code = %s
            ON CONFLICT (module, name) DO UPDATE SET res_id = EXCLUDED.res_id;
        """, (xml_id, code))
