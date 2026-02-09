
import sys
import odoo
from odoo import api, SUPERUSER_ID

# Database name from filestore
DB_NAME = 'tbriceno65-animalcenter-prueba1-28011079'

# Initialize Odoo
odoo.tools.config.parse_config(['-c', '/home/odoo/.config/odoo/odoo.conf'])
registry = odoo.modules.registry.Registry.new(DB_NAME)

with registry.cursor() as cr:
    try:
        sys.stderr.write("LISTING COLUMNS FOR x_pos_fiscal_printer...\n")
        cr.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'x_pos_fiscal_printer'")
        columns = cr.fetchall()
        for col in columns:
            sys.stderr.write(f"Column: {col[0]} | Type: {col[1]}\n")
            
        sys.stderr.write("QUERYING DATA (limit 5)...\n")
        # Query all columns
        cr.execute("SELECT * FROM x_pos_fiscal_printer LIMIT 5")
        rows = cr.fetchall()
        for row in rows:
            sys.stderr.write(f"Row: {row}\n")

    except Exception as e:
        sys.stderr.write(f"Error querying SQL: {e}\n")
