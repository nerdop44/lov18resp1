
import odoo
import odoo.service.db
import sys

try:
    odoo.tools.config.parse_config(['-c', '/home/odoo/.config/odoo/odoo.conf'])
    dbs = odoo.service.db.list_dbs(True)
    print("DATABASES FOUND:")
    for db in dbs:
        print(f"- {db}")
except Exception as e:
    print(f"Error listing DBs: {e}")
