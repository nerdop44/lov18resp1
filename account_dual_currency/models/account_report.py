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
from odoo import models, fields, api, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
from odoo.tools import config, date_utils, get_lang, float_compare, float_is_zero
from odoo.tools.float_utils import float_round
from odoo.tools.misc import formatLang, format_date, xlsxwriter
from odoo.tools.safe_eval import expr_eval, safe_eval
from odoo.models import check_method_name

class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    CURRENCY_DIF = None

    # search_template = fields.Char(string="Search Template", required=True, compute='_compute_search_template',
    #                               default='account_dual_currency.search_template_generic_currency_dif')

    def export_to_pdf(self, options):
        self.ensure_one()
        # As the assets are generated during the same transaction as the rendering of the
        # templates calling them, there is a scenario where the assets are unreachable: when
        # you make a request to read the assets while the transaction creating them is not done.
        # Indeed, when you make an asset request, the controller has to read the `ir.attachment`
        # table.
        # This scenario happens when you want to print a PDF report for the first time, as the
        # assets are not in cache and must be generated. To workaround this issue, we manually
        # commit the writes in the `ir.attachment` table. It is done thanks to a key in the context.
        if not config['test_enable']:
            self = self.with_context(commit_assetsbundle=True)

        base_url = self.env['ir.config_parameter'].sudo().get_param('report.url') or self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        rcontext = {
            'mode': 'print',
            'base_url': base_url,
            'company': self.env.company,
        }
        self = self.with_context(
            currency_dif=options.get('currency_dif', self.env.company.currency_id.symbol),
            currency_id_company_name=options.get('currency_id_company_name', self.env.company.currency_id.symbol),
        )
        print_mode_self = self.with_context(print_mode=True)

        body_html = print_mode_self.get_html(options, print_mode_self._get_lines(options))
        body = self.env['ir.ui.view']._render_template(
            "account_reports.print_template",
            values=dict(rcontext, body_html=body_html),
        )
        footer = self.env['ir.actions.report']._render_template("web.internal_layout", values=rcontext)
        footer = self.env['ir.actions.report']._render_template("web.minimal_layout", values=dict(rcontext, subst=True, body=markupsafe.Markup(footer.decode())))

        landscape = False
        if len(options['columns']) * len(options['column_groups']) > 5:
            landscape = True

        file_content = self.env['ir.actions.report']._run_wkhtmltopdf(
            [body],
            footer=footer.decode(),
            landscape=landscape,
            specific_paperformat_args={
                'data-report-margin-top': 10,
                'data-report-header-spacing': 10
            }
        )

        return {
            'file_name': self.get_default_report_filename('pdf'),
            'file_content': file_content,
            'file_type': 'pdf',
        }

    # def _compute_search_template(self):
    #     self.search_template = 'account_dual_currency.search_template_generic_currency_dif'


    def _get_options(self, previous_options=None):
        options = super()._get_options(previous_options)
        self.ensure_one()

        currency_id_company_name = 'Bs'
        currency_id_dif_name = 'USD'
        if self._context.get('allowed_company_ids'):
            company_id = self._context.get('allowed_company_ids')[0]
            company = self.env['res.company'].browse(company_id)
            if company:
                currency_id_company_name = company.currency_id.symbol if company.currency_id else 'Bs'
                currency_id_dif_name = company.currency_id_dif.symbol if company.currency_id_dif else 'USD'
        currency_dif = currency_id_company_name
        if previous_options:
            currency_dif = previous_options.get('currency_dif', currency_id_company_name)
        options['currency_dif'] = currency_dif
        options['currency_id_company_name'] = currency_id_company_name
        options['currency_id_dif_name'] = currency_id_dif_name
        
        return options

    @api.model
    def format_value(self, value, currency=False, blank_if_zero=True, figure_type=None, digits=1):
        """ Formats a value for display in a report (not especially numerical). figure_type provides the type of formatting we want.
        """
        if figure_type == 'none':
            return value

        if value is None:
            return ''

        if figure_type == 'monetary':
            currency = currency or self.env.company.currency_id
            if self._context.get('currency_dif'):
                if self._context.get('currency_dif') == self._context.get('currency_id_company_name'):
                    currency = self.env.company.currency_id
                else:
                    currency = self.env.company.currency_id_dif
            digits = None
        elif figure_type == 'integer':
            currency = None
            digits = 0
        elif figure_type in ('date', 'datetime'):
            return format_date(self.env, value)
        else:
            currency = None

        if self.is_zero(value, currency=currency, figure_type=figure_type, digits=digits):
            if blank_if_zero:
                return ''
            # don't print -0.0 in reports
            value = abs(value)

        if self._context.get('no_format'):
            return value

        formatted_amount = formatLang(self.env, value, currency_obj=currency, digits=digits)

        if figure_type == 'percentage':
            return f"{formatted_amount}%"

        return formatted_amount


    def _compute_formula_batch_with_engine_domain(self, options, date_scope, formulas_dict, current_groupby, next_groupby, offset=0, limit=None):
        return super()._compute_formula_batch_with_engine_domain(options, date_scope, formulas_dict, current_groupby, next_groupby, offset=offset, limit=limit)