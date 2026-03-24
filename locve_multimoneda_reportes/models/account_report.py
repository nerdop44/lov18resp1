# [LocVe] RC Multi-Moneda: Override del motor de reportes account.report
# Autor: Ing. Nerdo Pulido - Remake LocVe
# Versión: V7.2 - Fix chain if/elif + formatLang separado

from odoo import models, api
from odoo.tools.misc import formatLang, format_date
from odoo.tools.float_utils import float_is_zero


class AccountReport(models.AbstractModel):
    _inherit = 'account.report'

    def _get_options(self, previous_options=None, **kwargs):
        self.ensure_one()
        options = {'unfolded_lines': (previous_options or {}).get('unfolded_lines', [])}

        for initializer in self._get_options_initializers_in_sequence():
            initializer(options, previous_options=previous_options)

        options['buttons'] = sorted(options['buttons'], key=lambda x: x.get('sequence', 90))

        # Resolver nombres de monedas desde la empresa activa
        currency_id_company_name = 'Bs'
        currency_id_dif_name = 'USD'
        if self._context.get('allowed_company_ids'):
            company_id = self._context.get('allowed_company_ids')[0]
            company = self.env['res.company'].browse(company_id)
            if company:
                currency_id_company_name = company.currency_id.symbol or 'Bs'
                try:
                    currency_id_dif_name = company.currency_id_dif.symbol or 'USD'
                except Exception:
                    currency_id_dif_name = 'USD'

        # Preservar selección previa del usuario
        currency_dif = currency_id_company_name
        if previous_options and 'currency_dif' in previous_options:
            currency_dif = previous_options['currency_dif']

        rate_mode = (previous_options or {}).get('rate_mode', 'historical')

        options['currency_dif'] = currency_dif
        options['currency_id_company_name'] = currency_id_company_name
        options['currency_id_dif_name'] = currency_id_dif_name
        options['rate_mode'] = rate_mode

        # Botones de selector de Moneda y Tasa en la barra del reporte (Odoo 18)
        currency_label = currency_dif
        rate_label = 'Histórica' if rate_mode == 'historical' else 'Actualizada'

        options['buttons'].append({
            'name': f'En {currency_label}',
            'sequence': 80,
            'action': 'export_file',
            'action_param': 'toggle_currency_dif',
            'dropdown': {
                'title': 'Moneda del Reporte',
                'sequence': 80,
                'items': [
                    {'name': f'{currency_id_company_name} (Local)', 'action': 'set_currency_dif', 'action_param': currency_id_company_name},
                    {'name': f'{currency_id_dif_name} (Divisa)', 'action': 'set_currency_dif', 'action_param': currency_id_dif_name},
                ],
            },
        })

        if currency_dif == currency_id_dif_name:
            options['buttons'].append({
                'name': f'Tasa: {rate_label}',
                'sequence': 81,
                'action': 'export_file',
                'action_param': 'toggle_rate_mode',
                'dropdown': {
                    'title': 'Tasa a Utilizar',
                    'sequence': 81,
                    'items': [
                        {'name': 'Histórica (Registro)', 'action': 'set_rate_mode', 'action_param': 'historical'},
                        {'name': 'Actualizada (BCV/Hoy)', 'action': 'set_rate_mode', 'action_param': 'current'},
                    ],
                },
            })

        new_context = {
            **self._context,
            'currency_dif': currency_dif,
            'currency_id_company_name': currency_id_company_name,
        }
        self.env.context = new_context
        return options

    @api.model
    def format_value(self, options, value, figure_type=None, digits=1, blank_if_zero=True, **kwargs):
        """
        V7.2: Override de format_value con cadena if/elif unificada.
        Odoo 18 Enterprise signature: (self, options, value, figure_type, digits, blank_if_zero, **kwargs)
        """
        if figure_type == 'none':
            return value

        if value is None:
            return ''

        # Single clean if/elif chain — no double blocks that overwrite currency
        currency = kwargs.get('currency_obj')

        if figure_type == 'monetary':
            if not currency:
                currency = self.env.company.currency_id
                currency_dif = options.get('currency_dif') if isinstance(options, dict) else None
                currency_id_company_name = options.get('currency_id_company_name') if isinstance(options, dict) else None
                if currency_dif and currency_dif != currency_id_company_name:
                    try:
                        currency = self.env.company.currency_id_dif
                    except Exception:
                        pass
            digits = None  # formatLang usa currency.decimal_places
        elif figure_type == 'integer':
            currency = None
            digits = 0
        elif figure_type in ('date', 'datetime'):
            actual_date_value = value.get('value') if isinstance(value, dict) else value
            if not actual_date_value:
                return ''
            return format_date(self.env, actual_date_value)
        else:
            currency = None
            # digits se usa tal como fue pasado

        # Normalizar valor numérico (Enterprise puede pasar dicts con metadatos)
        actual_value = value.get('value', 0.0) if isinstance(value, dict) else (value or 0.0)

        # Zero check
        if figure_type == 'monetary' and currency:
            is_zero_val = currency.is_zero(actual_value)
        else:
            is_zero_val = float_is_zero(actual_value, precision_digits=digits or 2)

        if is_zero_val:
            if blank_if_zero:
                return ''
            actual_value = abs(actual_value)

        if self._context.get('no_format'):
            return actual_value

        # V7.2: Llamadas separadas a formatLang para evitar AssertionError
        if currency:
            formatted_amount = formatLang(self.env, actual_value, currency_obj=currency)
        else:
            formatted_amount = formatLang(self.env, actual_value, digits=digits or 2)

        if figure_type == 'percentage':
            return f"{formatted_amount}%"

        return formatted_amount

    def _dual_currency_query_get(self, options, date_scope, domain=None):
        """Puente para compatibilidad con Odoo 18 — reemplaza el antiguo _query_get."""
        query_obj = self._get_report_query(options, date_scope, domain=domain)
        return query_obj.from_clause, query_obj.where_clause, []
