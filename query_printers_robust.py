
import sys
import odoo
from odoo import api, SUPERUSER_ID

# Database name from logs
DB_NAME = 'p_tbriceno65_animalcenter_prueba1_28011079'

# Initialize Odoo
odoo.tools.config.parse_config(['-c', '/home/odoo/.config/odoo/odoo.conf'])
registry = odoo.modules.registry.Registry.new(DB_NAME)

with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        printers = env['x.pos.fiscal.printer'].search([])
        print("--- FISCAL PRINTERS START ---")
        if not printers:
            print("No printers found.")
        for p in printers:
            print(f"ID: {p.id} | Name: {p.name} | Serial: {p.serial} | Company: {p.company_id.name} (ID: {p.company_id.id}, Active: {p.company_id.active})")
        print("--- FISCAL PRINTERS END ---")
    except Exception as e:
        print(f"Error querying printers: {e}")
