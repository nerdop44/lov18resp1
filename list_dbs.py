
import odoo
odoo.tools.config.parse_config(['-c', '/home/odoo/.config/odoo/odoo.conf'])
print("Databases:", odoo.service.db.list_dbs(True))
