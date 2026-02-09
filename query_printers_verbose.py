
import sys
import odoo
from odoo import api, SUPERUSER_ID

# Database name from filestore - VERIFIED IT DOES NOT CRASH
DB_NAME = 'tbriceno65-animalcenter-prueba1-28011079'

# Initialize Odoo
odoo.tools.config.parse_config(['-c', '/home/odoo/.config/odoo/odoo.conf'])
sys.stderr.write("INITIALIZING REGISTRY...\n")
registry = odoo.modules.registry.Registry.new(DB_NAME)
sys.stderr.write("REGISTRY INITIALIZED.\n")

with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        sys.stderr.write("SEARCHING PRINTERS...\n")
        # Try finding the model first
        if 'x.pos.fiscal.printer' not in env:
             sys.stderr.write("MODEL x.pos.fiscal.printer NOT FOUND IN ENV.\n")
        else:
            printers = env['x.pos.fiscal.printer'].search([])
            sys.stderr.write("--- FISCAL PRINTERS START ---\n")
            if not printers:
                sys.stderr.write("No printers found.\n")
            for p in printers:
                sys.stderr.write(f"ID: {p.id} | Name: {p.name} | Serial: {p.serial} | Company: {p.company_id.name} (ID: {p.company_id.id}, Active: {p.company_id.active})\n")
            sys.stderr.write("--- FISCAL PRINTERS END ---\n")
    except Exception as e:
        sys.stderr.write(f"Error querying printers: {e}\n")
