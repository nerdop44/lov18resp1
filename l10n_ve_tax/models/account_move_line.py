from odoo import api, fields, models, Command, _
from odoo.tools import float_compare
from odoo.exceptions import UserError
from datetime import date, timedelta
import traceback

import logging

_logger = logging.getLogger(__name__)


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    config_deductible_tax = fields.Boolean()

    not_deductible_tax = fields.Boolean(default=False)