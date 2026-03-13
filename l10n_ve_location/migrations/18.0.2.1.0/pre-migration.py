
def migrate(cr, version):
    # 1. Adoptar Estados (25 registros)
    # Se utiliza row_number() ordenado por ID para consistencia con res_country_state_data.xml
    cr.execute("""
        INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
        SELECT 'res_country_state_' || sub.row_num, 'l10n_ve_location', 'res.country.state', sub.id, false
        FROM (
            SELECT id, row_number() OVER (ORDER BY id) as row_num 
            FROM res_country_state 
            WHERE country_id = (SELECT id FROM res_country WHERE code = 'VE')
            AND code IN ('DC', 'AM', 'AZ', 'AP', 'AR', 'BA', 'BO', 'CB', 'CJ', 'DA', 'FC', 'GR', 'LR', 'MD', 'MR', 'MN', 'NE', 'PT', 'SC', 'TC', 'TR', 'VA', 'YC', 'ZU', 'DF')
        ) sub
        ON CONFLICT (module, name) DO UPDATE SET res_id = EXCLUDED.res_id;
    """)

    # 2. Adoptar Municipios (Adopción por código secuencial)
    # En el XML el ID res_country_municipality_X coincide con el campo code=X
    # Filtramos por país VE a través de la relación de estado para seguridad.
    cr.execute("""
        INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
        SELECT 'res_country_municipality_' || m.code, 'l10n_ve_location', 'res.country.municipality', m.id, false
        FROM res_country_municipality m
        WHERE m.country_id = (SELECT id FROM res_country WHERE code = 'VE')
        AND m.code ~ '^[0-9]+$'
        ON CONFLICT (module, name) DO UPDATE SET res_id = EXCLUDED.res_id;
    """)

    # 3. Adoptar Parroquias (Adopción por código secuencial)
    # En el XML res_country_parish_X tiene code=X (en el XML se usa el código numérico)
    cr.execute("""
        INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
        SELECT 'res_country_parish_' || (m.code::int), 'l10n_ve_location', 'res.country.parish', m.id, false
        FROM res_country_parish m
        JOIN res_country_municipality mun ON m.municipality_id = mun.id
        WHERE mun.country_id = (SELECT id FROM res_country WHERE code = 'VE')
        AND m.code ~ '^[0-9]+$'
        ON CONFLICT (module, name) DO UPDATE SET res_id = EXCLUDED.res_id;
    """)
