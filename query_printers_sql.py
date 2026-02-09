
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
        sys.stderr.write("CHECKING IF TABLE x_pos_fiscal_printer EXISTS...\n")
        cr.execute("SELECT to_regclass('x_pos_fiscal_printer')")
        if cr.fetchone()[0]:
            sys.stderr.write("TABLE EXISTS. QUERYING...\n")
            cr.execute("SELECT id, name, serial, company_id FROM x_pos_fiscal_printer")
            printers = cr.fetchall()
            sys.stderr.write("--- FISCAL PRINTERS SQL START ---\n")
            if not printers:
                sys.stderr.write("No printers found in table.\n")
            for p in printers:
                id, name, serial, company_id = p
                # Get company name
                cr.execute("SELECT name, active FROM res_company WHERE id = %s", (company_id,))
                company = cr.fetchone()
                comp_name = company[0] if company else "Unknown"
                comp_active = company[1] if company else "Unknown"
                sys.stderr.write(f"ID: {id} | Name: {name} | Serial: {serial} | Company: {comp_name} (ID: {company_id}, Active: {comp_active})\n")
            sys.stderr.write("--- FISCAL PRINTERS SQL END ---\n")
        else:
            sys.stderr.write("TABLE x_pos_fiscal_printer DOES NOT EXIST.\n")
            # Try finding related tables
            cr.execute("SELECT tablename FROM pg_tables WHERE tablename LIKE '%fiscal%printer%'")
            tables = cr.fetchall()
            sys.stderr.write(f"Found tables: {tables}\n")

    except Exception as e:
        sys.stderr.write(f"Error querying SQL: {e}\n")
