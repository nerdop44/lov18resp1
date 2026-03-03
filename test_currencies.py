import odoo
from odoo import api, SUPERUSER_ID
odoo.tools.config.parse_config(['-c', '/etc/odoo.conf'])
registry = odoo.registry('tbriceno65-animalc-produccion-29159705')
with registry.cursor() as cr:
    env = api.Environment(cr, SUPERUSER_ID, {})
    company = env.company
    print(f"Company ID: {company.id}, Name: {company.name}")
    print(f"currency_id: {company.currency_id.id}, name: {company.currency_id.name}, symbol: {company.currency_id.symbol}")
    print(f"currency_id_dif: {company.currency_id_dif.id}, name: {company.currency_id_dif.name}, symbol: {company.currency_id_dif.symbol}")
