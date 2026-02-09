
import odoo
from odoo import api, SUPERUSER_ID
import sys

# Database name from filestore
DB_NAME = 'tbriceno65-animalcenter-prueba1-28011079'

# Initialize Odoo
odoo.tools.config.parse_config(['-c', '/home/odoo/.config/odoo/odoo.conf'])
registry = odoo.modules.registry.Registry.new(DB_NAME)

with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    print("Checking latest POS Orders...")
    
    # 1. Get latest order
    order = env['pos.order'].search([], order='id desc', limit=1)
    
    if not order:
        print("No POS orders found.")
    else:
        print(f"Latest Order: {order.name} (ID: {order.id}) Date: {order.date_order}")
        print(f"POS Config: {order.config_id.name}")
        
        # 2. Check Fiscal Fields (if any exist on pos.order)
        # We don't know the exact field names. Let's inspect the model fields.
        
        fiscal_fields = [f for f in order._fields if 'fiscal' in f or 'printer' in f or 'serial' in f]
        print(f"Fiscal Fields found on pos.order: {fiscal_fields}")
        
        for f in fiscal_fields:
            val = getattr(order, f)
            print(f"  {f}: {val}")
            
    # Check if module pos_fiscal_printer is installed according to ir_module_module
    mod = env['ir.module.module'].search([('name', '=', 'pos_fiscal_printer')])
    print(f"Module pos_fiscal_printer state: {mod.state}")

