import odoo
from odoo import api, SUPERUSER_ID
import sys

odoo.tools.config.parse_config(['-c', '/etc/odoo.conf'])
registry = odoo.registry('tbriceno65-animalc-produccion-29159705') # the user said tbriceno65-animalc.odoo.com, but locally we don't have this DB.
