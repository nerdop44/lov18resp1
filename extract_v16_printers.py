
import json
import odoo
from odoo import api, SUPERUSER_ID
import sys

# Try to find the database name
try:
    import odoo.tools.config
    # Odoo.sh usually has the db name in the environment or we can list dbs
    # We'll try to find the one matching the project
    dbs = odoo.service.db.list_dbs(True)
    # Filter for the likely main db
    target_db = next((db for db in dbs if 'tbriceno65-animalcenter-prueba-27984180' in db or 'main' in db), dbs[0] if dbs else None)
    
    if not target_db:
        print(json.dumps({"error": "No database found"}))
        sys.exit(1)
        
    registry = odoo.modules.registry.Registry.new(target_db)
    with registry.cursor() as cr:
        env = api.Environment(cr, SUPERUSER_ID, {})
        
        # 1. Fetch Printers
        printers = env['x.pos.fiscal.printer'].search([])
        printers_data = []
        for p in printers:
            printers_data.append({
                'id': p.id,
                'name': p.name,
                'serial': p.serial,
                'serial_port': p.serial_port,
                'flag_21': p.flag_21,
                'connection_type': p.connection_type,
                'api_url': p.api_url,
                'x_fiscal_commands_time': p.x_fiscal_commands_time,
                # We need company linking. v16 might not have company_id directly if it was missing?
                # But we can check if it exists
                'company_id': p.company_id.id if 'company_id' in p else None,
                'company_name': p.company_id.name if 'company_id' in p and p.company_id else None
            })
            
        # 2. Fetch POS Configs to link printers if company_id is missing on printer
        configs = env['pos.config'].search([('x_fiscal_printer_id', '!=', False)])
        config_links = []
        for c in configs:
            config_links.append({
                'pos_config_id': c.id,
                'pos_config_name': c.name,
                'company_id': c.company_id.id,
                'company_name': c.company_id.name,
                'printer_id': c.x_fiscal_printer_id.id
            })
            
        result = {
            'source_db': target_db,
            'printers': printers_data,
            'links': config_links
        }
        
        print(json.dumps(result, indent=4))

except Exception as e:
    print(json.dumps({"error": str(e)}))
