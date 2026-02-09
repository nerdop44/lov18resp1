
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
        sys.stderr.write("UPDATING PRINTER COMPANIES (VIA SQL)...\n")
        
        # 1. Ensure company_id column exists
        cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name='x_pos_fiscal_printer' AND column_name='company_id'")
        if not cr.fetchone():
            sys.stderr.write("Adding company_id column to x_pos_fiscal_printer...\n")
            cr.execute("ALTER TABLE x_pos_fiscal_printer ADD COLUMN company_id INTEGER")
            cr.execute("ALTER TABLE x_pos_fiscal_printer ADD CONSTRAINT x_pos_fiscal_printer_company_id_fkey FOREIGN KEY (company_id) REFERENCES res_company(id)")
        
        # 2. Check for x_fiscal_printer_id in pos_config
        cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name='pos_config' AND column_name='x_fiscal_printer_id'")
        if cr.fetchone():
            sys.stderr.write("Found x_fiscal_printer_id in pos_config. Linking printers...\n")
            # Update printers based on pos_config usage
            # We select distinct printer_id and company_id from pos_config where printer is set
            cr.execute("""
                UPDATE x_pos_fiscal_printer p
                SET company_id = c.company_id
                FROM pos_config c
                WHERE c.x_fiscal_printer_id = p.id
            """)
            sys.stderr.write(f"Updated {cr.rowcount} printers from pos_config linkage.\n")
        else:
            sys.stderr.write("Column x_fiscal_printer_id NOT FOUND in pos_config. Cannot infer company from usage.\n")
            
        # 3. Handle orphans (assign to first active company)
        cr.execute("SELECT id FROM x_pos_fiscal_printer WHERE company_id IS NULL")
        orphans = cr.fetchall()
        if orphans:
             # Find main company ID
             cr.execute("SELECT id, name FROM res_company ORDER BY id LIMIT 1")
             main_company = cr.fetchone()
             if main_company:
                 sys.stderr.write(f"Assigning {len(orphans)} orphan printers to Main Company {main_company[1]} (ID: {main_company[0]})...\n")
                 for orphan in orphans:
                     cr.execute("UPDATE x_pos_fiscal_printer SET company_id = %s WHERE id = %s", (main_company[0], orphan[0]))
        
        cr.commit()
        sys.stderr.write("UPDATE COMPLETE.\n")

    except Exception as e:
        cr.rollback()
        sys.stderr.write(f"Error updating printers: {e}\n")
