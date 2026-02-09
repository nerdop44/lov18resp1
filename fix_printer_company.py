
import sys
import odoo
from odoo import api, SUPERUSER_ID

# Database name from filestore
DB_NAME = 'tbriceno65-animalcenter-prueba1-28011079'

# Initialize Odoo
odoo.tools.config.parse_config(['-c', '/home/odoo/.config/odoo/odoo.conf'])
registry = odoo.modules.registry.Registry.new(DB_NAME)

with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    try:
        sys.stderr.write("UPDATING PRINTER COMPANIES...\n")
        
        # 1. Update the schema first (if module update didn't run, we might need to add column manually temporarily or assume module update will fix it)
        # But for this script to run via python directly, we assume the code change is deployed and we force column creation?
        # No, better to let Odoo handle schema via module upgrade.
        # But I can't trigger module upgrade easily from here without `odoo-bin -u`.
        # I will use SQL to add the column if it doesn't exist, to allow data fixing before full upgrade.
        cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name='x_pos_fiscal_printer' AND column_name='company_id'")
        if not cr.fetchone():
            sys.stderr.write("Adding company_id column manually...\n")
            cr.execute("ALTER TABLE x_pos_fiscal_printer ADD COLUMN company_id INTEGER")
            cr.execute("ALTER TABLE x_pos_fiscal_printer ADD CONSTRAINT x_pos_fiscal_printer_company_id_fkey FOREIGN KEY (company_id) REFERENCES res_company(id)")
        
        # 2. Find usage in pos.config
        # Field in pos.config is x_fiscal_printer_id (Many2one to x.pos.fiscal.printer)
        configs = env['pos.config'].search([('x_fiscal_printer_id', '!=', False)])
        
        for config in configs:
            printer = config.x_fiscal_printer_id
            company = config.company_id
            sys.stderr.write(f"Assigning Printer {printer.name} (ID: {printer.id}) to Company {company.name} (ID: {company.id})...\n")
            # Use SQL to avoid ORM constraints if field is not yet in ORM's loaded registry
            cr.execute("UPDATE x_pos_fiscal_printer SET company_id = %s WHERE id = %s", (company.id, printer.id))
            
        # 3. Handle orphans (assign to first active company or main company)
        cr.execute("SELECT id FROM x_pos_fiscal_printer WHERE company_id IS NULL")
        orphans = cr.fetchall()
        if orphans:
             main_company = env['res.company'].search([], limit=1)
             sys.stderr.write(f"Assigning {len(orphans)} orphan printers to Main Company {main_company.name} (ID: {main_company.id})...\n")
             for orphan in orphans:
                 cr.execute("UPDATE x_pos_fiscal_printer SET company_id = %s WHERE id = %s", (main_company.id, orphan[0]))

        cr.commit()
        sys.stderr.write("UPDATE COMPLETE.\n")

    except Exception as e:
        cr.rollback()
        sys.stderr.write(f"Error updating printers: {e}\n")
