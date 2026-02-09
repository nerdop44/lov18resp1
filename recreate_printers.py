
import odoo
from odoo import api, SUPERUSER_ID
import sys

# Database name from filestore
DB_NAME = 'tbriceno65-animalcenter-prueba1-28011079'

# Initialize Odoo
odoo.tools.config.parse_config(['-c', '/home/odoo/.config/odoo/odoo.conf'])
registry = odoo.modules.registry.Registry.new(DB_NAME)

DATA = [
    {
        "pos_name": "ANIMAL CENTER - C3",
        "printer_name": "Impresora Candelaria",
        "serial": "Z8C5002200-I",
        "port": "CON2"
    },
    {
        "pos_name": "MASQUEMASCOTAS",
        "printer_name": "Impresora Quinta Crespo",
        "serial": "2302000418",
        "port": "CON1"
    },
    {
        "pos_name": "PAJAROLANDÍA 2000",
        "printer_name": "Impresora Casanova",
        "serial": "1100016301",
        "port": "CON4"
    },
    {
        "pos_name": "RED SEA 1",
        "printer_name": "Impresora Red SEA",
        "serial": "1907018138",
        "port": "CON3"
    }
]

with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    
    print("Recreating printers via SQL...")
    
    # Check available columns in pos_config
    cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name='pos_config'")
    pos_columns = set(row[0] for row in cr.fetchall())
    
    has_printer_id = 'x_fiscal_printer_id' in pos_columns
    has_printer_code = 'x_fiscal_printer_code' in pos_columns
    has_baudrate = 'x_fiscal_command_baudrate' in pos_columns
    
    if not has_printer_id:
        print("CRITICAL: x_fiscal_printer_id column missing in pos_config. Cannot link printers.")
        # We can still create the printers though.
    
    for item in DATA:
        pos_name = item['pos_name']
        
        # 1. Find POS Config
        cr.execute("SELECT id, company_id FROM pos_config WHERE name = %s", (pos_name,))
        pos_res = cr.fetchone()
        
        if not pos_res:
             # Try LIKE
            cr.execute("SELECT id, company_id FROM pos_config WHERE name ILIKE %s", (f"%{pos_name}%",))
            pos_res = cr.fetchone()
            
        if not pos_res:
            print(f"ERROR: POS '{pos_name}' not found. Skipping.")
            continue
            
        pos_id = pos_res[0]
        company_id = pos_res[1]
        
        print(f"POS '{pos_name}' found (ID: {pos_id})")
        
        # 2. Check/Create Printer
        cr.execute("SELECT id FROM x_pos_fiscal_printer WHERE serial = %s", (item['serial'],))
        printer_res = cr.fetchone()
        
        printer_id = None
        if printer_res:
            printer_id = printer_res[0]
            print(f"  Printer '{item['printer_name']}' exists. Updating...")
            cr.execute("""
                UPDATE x_pos_fiscal_printer
                SET name = %s, serial_port = %s, company_id = %s
                WHERE id = %s
            """, (item['printer_name'], item['port'], company_id, printer_id))
        else:
            print(f"  Creating Printer '{item['printer_name']}'...")
            cr.execute("""
                INSERT INTO x_pos_fiscal_printer (name, serial, serial_port, company_id, flag_21, connection_type, x_fiscal_commands_time, create_uid, write_uid, create_date, write_date)
                VALUES (%s, %s, %s, %s, '00', 'usb_serial', 750, %s, %s, NOW(), NOW())
                RETURNING id
            """, (item['printer_name'], item['serial'], item['port'], company_id, SUPERUSER_ID, SUPERUSER_ID))
            printer_id = cr.fetchone()[0]
            
        # 3. Link Printer to POS
        if has_printer_id:
            updates = ["x_fiscal_printer_id = %s"]
            params = [printer_id]
            
            if has_printer_code:
                updates.append("x_fiscal_printer_code = %s")
                params.append(item['serial'])
                
            params.append(pos_id)
            
            sql = f"UPDATE pos_config SET {', '.join(updates)} WHERE id = %s"
            cr.execute(sql, tuple(params))
            print(f"  Linked Printer to POS.")
        else:
            print("  Skipping link (field missing).")
            
    cr.commit()
    print("Migration Done.")
