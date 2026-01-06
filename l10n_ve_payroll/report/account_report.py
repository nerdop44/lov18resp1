import ast
import datetime
import io
import json
import logging
import math
import re
import base64
from ast import literal_eval
from collections import defaultdict
from functools import cmp_to_key

import markupsafe
from babel.dates import get_quarter_names
from dateutil.relativedelta import relativedelta

from odoo.addons.web.controllers.utils import clean_action
from odoo import models, fields, api, _, osv
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.tools import config, date_utils, get_lang, float_compare, float_is_zero
from odoo.tools.float_utils import float_round
from odoo.tools.misc import formatLang, format_date, xlsxwriter
from odoo.tools.safe_eval import expr_eval, safe_eval
from odoo.models import check_method_name

class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    def _get_options(self, previous_options=None):
        self.ensure_one()
        # Create default options.
        options = {'unfolded_lines': (previous_options or {}).get('unfolded_lines', [])}

        for initializer in self._get_options_initializers_in_sequence():
            initializer(options, previous_options=previous_options)

        # Sort the buttons list by sequence, for rendering
        options['buttons'] = sorted(options['buttons'], key=lambda x: x.get('sequence', 90))

        currency_id_company_name = 'Bs'
        currency_id_dif_name = 'USD'
        if self._context.get('allowed_company_ids'):
            company_id = self._context.get('allowed_company_ids')[0]
            company = self.env['res.company'].browse(company_id)
            if company:
                currency_id_company_name = company.currency_id.symbol
                currency_id_dif_name = company.currency_id_dif.symbol
        currency_dif = currency_id_company_name
        if previous_options:
            if "currency_dif" in previous_options:
                currency_dif = previous_options['currency_dif']
        options['currency_dif'] = currency_dif
        options['currency_id_company_name'] = currency_id_company_name
        options['currency_id_dif_name'] = currency_id_dif_name
        slip_ids = None
        employee_ids = None
        rule_employee_integral_ids = None
        rule_employee_retenido_ids = None
        rule_company_aporte_ids = None
        structure_ids = None
        #variables de nómina
        if previous_options:
            if "rule_employee_integral_ids" in previous_options:
                rule_employee_integral_ids = previous_options['rule_employee_integral_ids']
            if "rule_employee_retenido_ids" in previous_options:
                rule_employee_retenido_ids = previous_options['rule_employee_retenido_ids']
            if "employee_ids" in previous_options:
                 employee_ids = previous_options['employee_ids']
            if 'rule_company_aporte_ids' in previous_options:
                rule_company_aporte_ids = previous_options['rule_company_aporte_ids']
            if 'structure_ids' in previous_options:
                structure_ids = previous_options['structure_ids']
            if 'slip_ids' in previous_options:
                slip_ids = previous_options['slip_ids']
        new_context = {
            **self._context,
            'currency_dif': currency_dif,
            'currency_id_company_name': currency_id_company_name,
            'rule_employee_integral_ids': rule_employee_integral_ids,
            'rule_employee_retenido_ids': rule_employee_retenido_ids,
            'employee_ids': employee_ids,
            'rule_company_aporte_ids': rule_company_aporte_ids,
            'structure_ids': structure_ids,
        }
        self.env.context = new_context
        return options