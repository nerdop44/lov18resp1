
def migrate(cr, version):
    # --- SANEAMIENTO QUIRÚRGICO DE GEOGRAFÍA (V47) ---
    
    # 1. Limpieza de Parroquias Huérfanas
    cr.execute("""
        DELETE FROM res_country_parish
        WHERE id IN (
            SELECT p.id 
            FROM res_country_parish p
            JOIN (
                SELECT code, municipality_id, MIN(id) as keep_id
                FROM res_country_parish
                GROUP BY code, municipality_id
                HAVING COUNT(*) > 1
            ) dup ON p.code = dup.code AND p.municipality_id = dup.municipality_id
            WHERE p.id != dup.keep_id
            AND NOT EXISTS (SELECT 1 FROM res_partner WHERE parish_id = p.id)
            AND NOT EXISTS (SELECT 1 FROM ir_model_data WHERE model = 'res.country.parish' AND res_id = p.id)
        );
    """)

    # 2. Limpieza de Municipios Huérfanos
    cr.execute("""
        DELETE FROM res_country_municipality
        WHERE id IN (
            SELECT m.id 
            FROM res_country_municipality m
            JOIN (
                SELECT code, country_id, MIN(id) as keep_id
                FROM res_country_municipality
                WHERE country_id = (SELECT id FROM res_country WHERE code = 'VE')
                GROUP BY code, country_id
                HAVING COUNT(*) > 1
            ) dup ON m.code = dup.code AND m.country_id = dup.country_id
            WHERE m.id != dup.keep_id
            AND NOT EXISTS (SELECT 1 FROM res_partner WHERE municipality_id = m.id)
            AND NOT EXISTS (SELECT 1 FROM ir_model_data WHERE model = 'res.country.municipality' AND res_id = m.id)
        );
    """)

    # 3. Limpieza de Estados Huérfanos
    cr.execute("""
        DELETE FROM res_country_state
        WHERE id IN (
            SELECT s.id 
            FROM res_country_state s
            JOIN (
                SELECT code, country_id, MIN(id) as keep_id
                FROM res_country_state
                WHERE country_id = (SELECT id FROM res_country WHERE code = 'VE')
                GROUP BY code, country_id
                HAVING COUNT(*) > 1
            ) dup ON s.code = dup.code AND s.country_id = dup.country_id
            WHERE s.id != dup.keep_id
            AND NOT EXISTS (SELECT 1 FROM res_partner WHERE state_id = s.id)
            AND NOT EXISTS (SELECT 1 FROM ir_model_data WHERE model = 'res.country.state' AND res_id = s.id)
        );
    """)

    # --- ADOPCIÓN ATÓMICA UNIFICADA (V47) ---
    # Usamos DISTINCT ON para blindar contra cualquier duplicado remanente que tenga vínculos.
    
    # Estados
    cr.execute("""
        INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
        SELECT DISTINCT ON (row_num) 'res_country_state_' || sub.row_num, 'l10n_ve_location', 'res.country.state', sub.id, false
        FROM (
            SELECT id, row_number() OVER (ORDER BY id ASC) as row_num 
            FROM res_country_state 
            WHERE country_id = (SELECT id FROM res_country WHERE code = 'VE')
            AND code IN ('DC', 'AM', 'AZ', 'AP', 'AR', 'BA', 'BO', 'CB', 'CJ', 'DA', 'FC', 'GR', 'LR', 'MD', 'MR', 'MN', 'NE', 'PT', 'SC', 'TC', 'TR', 'VA', 'YC', 'ZU', 'DF')
        ) sub
        ON CONFLICT (module, name) DO UPDATE SET res_id = EXCLUDED.res_id;
    """)

    # Municipios
    cr.execute("""
        INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
        SELECT DISTINCT ON (m.code) 'res_country_municipality_' || m.code, 'l10n_ve_location', 'res.country.municipality', m.id, false
        FROM res_country_municipality m
        WHERE m.country_id = (SELECT id FROM res_country WHERE code = 'VE')
        AND m.code ~ '^[0-9]+$'
        ORDER BY m.code, m.id ASC
        ON CONFLICT (module, name) DO UPDATE SET res_id = EXCLUDED.res_id;
    """)

    # Parroquias
    cr.execute("""
        INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
        SELECT DISTINCT ON (m.code::int) 'res_country_parish_' || (m.code::int), 'l10n_ve_location', 'res.country.parish', m.id, false
        FROM res_country_parish m
        JOIN res_country_municipality mun ON m.municipality_id = mun.id
        WHERE mun.country_id = (SELECT id FROM res_country WHERE code = 'VE')
        AND m.code ~ '^[0-9]+$'
        ORDER BY m.code::int, m.id ASC
        ON CONFLICT (module, name) DO UPDATE SET res_id = EXCLUDED.res_id;
    """)
