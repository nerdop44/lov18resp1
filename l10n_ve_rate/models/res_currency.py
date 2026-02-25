# from odoo import models, fields, api, _
# from odoo.exceptions import UserError, ValidationError


# class ResCurrency(models.Model):
#     _inherit = "res.currency"

#     def _convert(self, from_amount, to_currency, company, date, round=True, custom_rate=0.0):
#         """Returns the converted amount of ``from_amount``` from the currency
#            ``self`` to the currency ``to_currency`` for the given ``date`` and
#            company.

#            :param company: The company from which we retrieve the convertion rate
#            :param date: The nearest date from which we retriev the conversion rate.
#            :param round: Round the result or not
#         """
#         self, to_currency = self or to_currency, to_currency or self
#         assert self, "convert amount from unknown currency"
#         assert to_currency, "convert amount to unknown currency"
#         assert company, "convert amount from unknown company"
#         assert date, "convert amount from unknown date"
#         # apply conversion rate
#         if self == to_currency:
#             to_amount = from_amount
#         elif from_amount:
#             if custom_rate > 0:
#                 to_amount = from_amount * custom_rate 
#             else:
#                 to_amount = from_amount * self._get_conversion_rate(self, to_currency, company, date)
#         else:
#             return 0.0

#         # apply rounding
#         return to_currency.round(to_amount) if round else to_amount
    

# En tu módulo personalizado, en el archivo donde heredas res.currency
# Por ejemplo: l10n_ve_localization/models/currency.py o similar

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ResCurrency(models.Model):
    _inherit = "res.currency"

    # MODIFICACIÓN SUGERIDA AQUÍ:
    # Hacemos que 'company' y 'date' sean opcionales en la firma del método
    # y los inferimos si no se proporcionan.
    def _convert(self, from_amount, to_currency, company=None, date=None, round=True, custom_rate=0.0):
        """Returns the converted amount of ``from_amount``` from the currency
            ``self`` to the currency ``to_currency`` for the given ``date`` and
            company.

            :param company: The company from which we retrieve the convertion rate.
                            If None, it will try to infer from self.env.company.
            :param date: The nearest date from which we retrieve the conversion rate.
                         If None, it will use today's date.
            :param round: Round the result or not
            :param custom_rate: Optional custom conversion rate to use.
        """
        self, to_currency = self or to_currency, to_currency or self
        assert self, "convert amount from unknown currency"
        assert to_currency, "convert amount to unknown currency"

        # --- INICIO DE LA LÓGICA DE INFERENCIA ---
        # Si 'company' no se proporciona, usa la compañía actual del entorno.
        if not company:
            company = self.env.company
        assert company, "convert amount from unknown company (could not infer)" # Mantenemos el assert por si falla la inferencia

        # Si 'date' no se proporciona, usa la fecha actual.
        if not date:
            date = fields.Date.context_today(self)
        assert date, "convert amount from unknown date (could not infer)" # Mantenemos el assert por si falla la inferencia
        # --- FIN DE LA LÓGICA DE INFERENCIA ---

        # apply conversion rate
        if self == to_currency:
            to_amount = from_amount
        elif from_amount:
            if custom_rate > 0:
                to_amount = from_amount * custom_rate
            else:
                to_amount = from_amount * self._get_conversion_rate(self, to_currency, company, date)
        else:
            return 0.0

        # apply rounding
        return to_currency.round(to_amount) if round else to_amount
