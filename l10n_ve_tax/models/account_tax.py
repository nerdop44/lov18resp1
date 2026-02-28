from odoo.tools.float_utils import float_round
from odoo import api, models, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import formatLang

import logging

_logger = logging.getLogger(__name__)


class AccountTax(models.Model):
    _inherit = "account.tax"

    @api.model
    def _prepare_tax_totals(
        self, base_lines, currency, tax_lines=None, is_company_currency_requested=False
    ):
        _logger.criltical("¡¡¡MI METODO _prepare_tax_totals SE ESTÁ EJECUTANDO!!!") # Línea agregada

        """
        This function adds the alternate currency tax amounts to tax_totals.
        In it, the parent function is executed 2 times, once for the original
        currency and once for the alternate currency.

        The data that is brought is not recalculated, that is, it comes from the lines of the entry
        ------
        Parameters: (Parameters inherited)
            base_lines: tree of dict
            currency: res.currency
        ------
        Returns: (Return inherited)
            dict: Now returns additionally:
            "subtotal": float
            "formatted_subtotal": str
            "discount_amount": float
            "foreign_subtotal": float
            "foreign_formatted_subtotal": str
            "formatted_discount_amount": str
            "groups_by_foreign_subtotal": dict
            "foreign_discount_amount": float
            "foreign_formatted_discount_amount": str
            "foreign_subtotals": tree of dict
            "foreign_amount_untaxed": float
            "foreign_amount_total": float
            "foreign_formatted_amount_untaxed": str
            "foreign_formatted_amount_total": str
        """
        # Verifica que base_lines no esté vacío
        _logger.debug("Preparing tax totals with base_lines: %s, currency: %s", base_lines, currency)
        
        if not base_lines:
            return {
                "subtotals": [],
                "foreign_subtotals": [],
                "amount_untaxed": 0.0,
                "formatted_amount_untaxed": "",
                # Agrega otros campos necesarios con valores por defecto
            }
        
        foreign_currency = self.env.company.currency_foreign_id or False
        if not foreign_currency:
            _logger.error("No foreign currency configured in the company")
            raise ValidationError(_("No foreign currency configured in the company"))

        # Base Currency
        res = super()._prepare_tax_totals(
            base_lines,
            currency,
            tax_lines,
            is_company_currency_requested=is_company_currency_requested,
        )
        # Registro de depuración para los totales en moneda base
        _logger.debug("Base Tax Totals: %s", res)
        
        res_without_discount = res.copy()
        has_discount = not currency.is_zero(sum([line["discount"] for line in base_lines]))

        if has_discount:
            base_without_discount = [line.copy() for line in base_lines if line]
            for base_line in base_without_discount:
                base_line["discount"] = 0

            res_without_discount = super()._prepare_tax_totals(
                base_without_discount,
                currency,
                tax_lines,
                is_company_currency_requested=is_company_currency_requested,
            )

        foreign_base_lines, foreign_tax_lines = self.get_foreign_base_tax_lines(
            base_lines, tax_lines, foreign_currency
        )

        # Foreign Currency
        foreign_taxes = super()._prepare_tax_totals(
            foreign_base_lines,
            foreign_currency,
            foreign_tax_lines,
            is_company_currency_requested=is_company_currency_requested,
        )
        _logger.debug("Foreign Tax Totals: %s", foreign_taxes)
        
        # Registro de depuración para los totales en moneda extranjera
       

        foreign_taxes_without_discount = foreign_taxes.copy()
        if has_discount:
            foreign_without_discount = [line.copy() for line in foreign_base_lines if line]
            for foreign_base_line in foreign_without_discount:
                foreign_base_line["discount"] = 0

            foreign_taxes_without_discount = super()._prepare_tax_totals(
                foreign_without_discount,
                foreign_currency,
                foreign_tax_lines,
                is_company_currency_requested=is_company_currency_requested,
            )

        res["groups_by_foreign_subtotal"] = foreign_taxes.get("groups_by_subtotal") # Usar .get() para evitar KeyError si no existe
        res["foreign_subtotals"] = foreign_taxes.get("subtotals", [])
        res["foreign_amount_untaxed"] = foreign_taxes.get("amount_untaxed", 0.0)
        res["foreign_amount_total"] = foreign_taxes.get("amount_total", 0.0)
        res["foreign_formatted_amount_untaxed"] = foreign_taxes.get("formatted_amount_untaxed", "")
        res["foreign_formatted_amount_total"] = foreign_taxes.get("formatted_amount_total", "")

        res["show_discount"] = self.env.company.show_discount_on_moves

        res["subtotal"] = res_without_discount.get("amount_untaxed", 0.0)
        res["formatted_subtotal"] = formatLang(self.env, res["subtotal"], currency_obj=currency)

        res["foreign_subtotal"] = foreign_taxes_without_discount.get("amount_untaxed", 0.0)
        res["foreign_formatted_subtotal"] = formatLang(
            self.env, res["foreign_subtotal"], currency_obj=foreign_currency
        )

        res["discount_amount"] = res.get("amount_untaxed", 0.0) - res_without_discount.get("amount_untaxed", 0.0)

        res["formatted_discount_amount"] = formatLang(
            self.env, res["discount_amount"], currency_obj=currency
        )
        res["foreign_discount_amount"] = (
            foreign_taxes.get("amount_untaxed", 0.0) - foreign_taxes_without_discount.get("amount_untaxed", 0.0)
        )
        res["foreign_formatted_discount_amount"] = formatLang(
            self.env, res["foreign_discount_amount"], currency_obj=foreign_currency
        )
# Asegúrate de que estos totales formateados estén en el nivel superior de 'res'
        res["formatted_amount_total"] = res.get("formatted_amount_total", "0.00") # Toma el valor de la moneda base
        res["foreign_formatted_amount_total"] = foreign_taxes.get("formatted_amount_total", "0.00") # Toma el valor de la moneda extranjera

        # Incluye la información de los grupos de impuestos
        res["groups"] = res.get("groups", {}) # Asegúrate de que la clave 'groups' exista
        if "groups_by_subtotal" in foreign_taxes:
            # Asigna los grupos de impuestos en moneda extranjera usando el nombre del subtotal 'foreign_subtotals'
            res["groups"]["foreign_subtotals"] = foreign_taxes["groups_by_subtotal"].get("foreign_subtotals", [])

        
        # Registro de depuración final antes de retornar
        _logger.debug("Final Tax Totals: %s", res)
        
        return res

    @api.model
    def _get_tax_totals_summary(self, base_lines, currency, company, cash_rounding=None):
        """
        Extensión de Odoo 18 que inyecta los campos bimonetarios en tax_totals.
        En Odoo 18, _compute_tax_totals llama a _get_tax_totals_summary en lugar de
        _prepare_tax_totals, por lo que debemos extender este método para añadir
        los campos bimonetarios necesarios para los libros fiscales.
        """
        # Llama al método estándar de Odoo 18
        res = super()._get_tax_totals_summary(
            base_lines=base_lines,
            currency=currency,
            company=company,
            cash_rounding=cash_rounding,
        )

        if not res:
            return res

        foreign_currency = company.currency_foreign_id or False
        if not foreign_currency:
            return res

        try:
            # Calcular totales foráneos directamente desde los registros de líneas
            # El 'record' en base_lines es un account.move.line con foreign_subtotal y foreign_price_total
            foreign_amount_untaxed = 0.0
            foreign_amount_total = 0.0
            groups_by_foreign_subtotal = {}

            for base_line in base_lines:
                record = base_line.get("record")
                if not record:
                    continue
                # Sumamos subtotal foráneo (sin impuestos) y total foráneo (con impuestos)
                if hasattr(record, 'foreign_subtotal'):
                    foreign_amount_untaxed += record.foreign_subtotal or 0.0
                if hasattr(record, 'foreign_price_total'):
                    foreign_amount_total += record.foreign_price_total or 0.0

                # Construir groups_by_foreign_subtotal para los libros fiscales
                # La estructura que espera el reporte es:
                # { "Nombre subtotal": [{ "tax_group_id": id, "tax_group_base_amount": float, "tax_group_amount": float }] }
                if hasattr(record, 'tax_ids') and record.tax_ids:
                    for tax in record.tax_ids:
                        subtotal_name = tax.mapped('invoice_repartition_line_ids.factor_percent')
                        group_id = tax.tax_group_id.id if tax.tax_group_id else False
                        if not group_id:
                            continue
                        base_amount = record.foreign_subtotal or 0.0
                        tax_amount = (record.foreign_price_total or 0.0) - base_amount

                        # Agregar al diccionario de grupos
                        for subtotal in res.get("subtotals", []):
                            key = subtotal.get("name", "Untaxed Amount")
                            if key not in groups_by_foreign_subtotal:
                                groups_by_foreign_subtotal[key] = []
                            # Buscar si ya existe un entry para este grupo
                            found = False
                            for entry in groups_by_foreign_subtotal[key]:
                                if entry.get("tax_group_id") == group_id:
                                    entry["tax_group_base_amount"] += base_amount
                                    entry["tax_group_amount"] += tax_amount
                                    found = True
                                    break
                            if not found:
                                groups_by_foreign_subtotal[key].append({
                                    "tax_group_id": group_id,
                                    "tax_group_base_amount": base_amount,
                                    "tax_group_amount": tax_amount,
                                })

            res["foreign_amount_untaxed"] = foreign_amount_untaxed
            res["foreign_amount_total"] = foreign_amount_total or (foreign_amount_untaxed + (foreign_amount_total - foreign_amount_untaxed if foreign_amount_total > foreign_amount_untaxed else 0.0))
            res["groups_by_foreign_subtotal"] = groups_by_foreign_subtotal
            res["foreign_subtotals"] = []
            res["foreign_formatted_amount_untaxed"] = formatLang(self.env, foreign_amount_untaxed, currency_obj=foreign_currency)
            res["foreign_formatted_amount_total"] = formatLang(self.env, foreign_amount_total, currency_obj=foreign_currency)

        except Exception as e:
            _logger.warning("Error calculating foreign tax totals (bimonetary): %s", e)

        return res


    def get_foreign_base_tax_lines(self, base_lines, tax_lines, currency):
        foreign_base_lines = [line.copy() for line in base_lines if line]
        foreign_tax_lines = None
        if tax_lines:
            foreign_tax_lines = [line.copy() for line in tax_lines if line]
        taxes = []
        for base_line in foreign_base_lines:
            is_exists_foreign_price = "foreign_price" in base_line["record"]

            if is_exists_foreign_price:
                base_line["price_unit"] = base_line["record"].foreign_price
                base_line["price_subtotal"] = base_line["record"].foreign_subtotal
                base_line["currency"] = currency
            else:
                base_line["price_unit"] = base_line["record"].price_unit
                base_line["price_subtotal"] = base_line["record"].price_subtotal
                base_line["currency"] = base_line["record"].currency_id

            if base_line["taxes"]:
                taxes.append(
                    {
                        "tax": base_line["taxes"][0],
                        "price": base_line["price_unit"],
                        "base": base_line["price_subtotal"],
                    }
                )

        tax_values_tree = []
        for base_line in foreign_base_lines:
            tax_values_tree += self._compute_taxes_for_single_line(base_line)[1]

        round_globally = self.env.company.tax_calculation_rounding_method == "round_globally"

        if foreign_tax_lines:
            for tax_line in foreign_tax_lines:
                tax_line["currency"] = currency
                tax_line["tax_amount"] = 0.0
                amount = 0.0
                for tax in tax_values_tree:
                    if tax["tax_repartition_line"].id == tax_line["tax_repartition_line"].id:
                        if not round_globally:
                            amount += float_round(
                                tax["amount"], precision_digits=currency.decimal_places
                            )
                        else:
                            amount += tax["amount"]

                tax_line["tax_amount"] = float_round(
                    amount, precision_digits=currency.decimal_places
                )

        return foreign_base_lines, foreign_tax_lines
