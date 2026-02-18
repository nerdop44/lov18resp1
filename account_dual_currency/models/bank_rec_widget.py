import ast
import markupsafe

from odoo import _, api, fields, models, tools, Command
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.models import check_method_name
from odoo.addons.web.controllers.utils import clean_action
from odoo.tools import html2plaintext
from odoo.tools.misc import formatLang



class BankRecWidget(models.Model):
    _inherit = "bank.rec.widget"

    # def _lines_widget_recompute_exchange_diff(self):
    #     for rec in self:
    #         pass