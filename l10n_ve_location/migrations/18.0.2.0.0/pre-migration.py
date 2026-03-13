
def migrate(cr, version):
    # Adopción de estados de Venezuela existentes para evitar UniqueViolation
    # Esto busca estados con códigos estándar de Venezuela y les asigna el XML ID de este módulo
    # para que Odoo los trate como registros propios y los actualice en lugar de intentar crearlos.
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
