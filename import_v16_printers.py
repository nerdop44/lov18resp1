
import json
import odoo
from odoo import api, SUPERUSER_ID
import sys

# Database name from filestore
DB_NAME = 'tbriceno65-animalcenter-prueba1-28011079'

# Initialize Odoo
odoo.tools.config.parse_config(['-c', '/home/odoo/.config/odoo/odoo.conf'])
registry = odoo.modules.registry.Registry.new(DB_NAME)

JSON_FILE = 'v16_printers.json'

def get_company_by_name(env, name):
    if not name:
        return env['res.company'].browse(1) # Default to main if unknown
    company = env['res.company'].search([('name', '=', name)], limit=1)
    if not company:
        # Try case insensitive or partial
        company = env['res.company'].search([('name', 'ilike', name)], limit=1)
    return company if company else env['res.company'].browse(1)

with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    try:
        with open(JSON_FILE, 'r') as f:
            data = json.load(f)
            
        print(f"Loaded {len(data['printers'])} printers from {data['source_db']}")
        
        printer_map = {} # v16_id -> v18_record
        
        # 1. Import Printers
        for p_data in data['printers']:
            serial = p_data['serial']
            company_name = p_data.get('company_name')
            
            # Find company
            company = get_company_by_name(env, company_name)
            
            # Check if printer exists
            printer = env['x.pos.fiscal.printer'].search([('serial', '=', serial)], limit=1)
            
            vals = {
                'name': p_data['name'],
                'serial': serial,
                'serial_port': p_data['serial_port'],
                'flag_21': p_data['flag_21'],
                'connection_type': p_data['connection_type'],
                'api_url': p_data['api_url'],
                'x_fiscal_commands_time': p_data['x_fiscal_commands_time'],
                'company_id': company.id
            }
            
            if printer:
                print(f"Updating printer {printer.name} ({serial}) Company: {company.name}")
                printer.write(vals)
            else:
                print(f"Creating printer {vals['name']} ({serial}) Company: {company.name}")
                printer = env['x.pos.fiscal.printer'].create(vals)
                
            printer_map[p_data['id']] = printer

        # 2. Link to POS Configs
        # We need to map v16 POS configs to v18 POS configs by Name
        for link in data['links']:
            pos_name = link['pos_config_name']
            v16_printer_id = link['printer_id']
            
            if v16_printer_id not in printer_map:
                print(f"Warning: Printer ID {v16_printer_id} not found in map for POS {pos_name}")
                continue
                
            v18_printer = printer_map[v16_printer_id]
            
            # Find POS in v18
            pos_config = env['pos.config'].search([('name', '=', pos_name)], limit=1)
            if pos_config:
                print(f"Linking POS '{pos_name}' to Printer '{v18_printer.name}'")
                # Update attributes
                pos_config.write({
                    'x_fiscal_printer_id': v18_printer.id,
                    'x_fiscal_printer_code': v18_printer.serial,
                    # Baudrate? Assuming 9600 or from v16 if we extracted it (we didn't extract baudrate in extract script, oops)
                    # We'll leave baudrate as is or default
                })
                # Check company match
                if pos_config.company_id.id != v18_printer.company_id.id:
                     print(f"  Note: POS Company ({pos_config.company_id.name}) differs from Printer Company ({v18_printer.company_id.name})")
            else:
                print(f"Warning: POS Config '{pos_name}' not found into v18")

        cr.commit()
        print("Import Complete.")

    except FileNotFoundError:
        print(f"Error: {JSON_FILE} not found. Run extraction first.")
    except Exception as e:
        cr.rollback()
        print(f"Error: {str(e)}")
