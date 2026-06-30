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
        
        company = self.env.company
        foreign_currency = company.currency_foreign_id or getattr(company, 'currency_id_dif', False) or self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        
        is_ves_foreign = foreign_currency and (foreign_currency.name in ['VES', 'VEF', 'Bs.', 'Bs'] or 'Bs' in (foreign_currency.symbol or ''))
        is_ves_company = company.currency_id and (company.currency_id.name in ['VES', 'VEF', 'Bs.', 'Bs'] or 'Bs' in (company.currency_id.symbol or ''))
        
        if is_ves_foreign and is_ves_company:
            usd_currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
            if usd_currency:
                foreign_currency = usd_currency

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

        foreign_currency = company.currency_foreign_id or getattr(company, 'currency_id_dif', False) or self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        
        is_ves_foreign = foreign_currency and (foreign_currency.name in ['VES', 'VEF', 'Bs.', 'Bs'] or 'Bs' in (foreign_currency.symbol or ''))
        is_ves_company = company.currency_id and (company.currency_id.name in ['VES', 'VEF', 'Bs.', 'Bs'] or 'Bs' in (company.currency_id.symbol or ''))
        
        if is_ves_foreign and is_ves_company:
            usd_currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
            if usd_currency:
                foreign_currency = usd_currency

        if not foreign_currency:
            return res

        # Obtener la factura
        move = False
        for base_line in base_lines:
            record = base_line.get("record")
            if record and hasattr(record, 'move_id') and record.move_id:
                move = record.move_id
                break

        rate = 1.0
        is_invoice_in_usd = currency.name == 'USD'
        if move:
            # Obtener las tasas posibles de la factura
            rates_to_check = [
                getattr(move, 'foreign_rate', 0.0) or 0.0,
                getattr(move, 'tax_today', 0.0) or 0.0,
                getattr(move, 'foreign_inverse_rate', 0.0) or 0.0,
            ]
            # Priorizar cualquier tasa que sea mayor que 1.0 (ej. 617.64 o 474.06)
            for r in rates_to_check:
                if r > 1.0:
                    rate = r
                    break
            else:
                # Si no hay ninguna tasa > 1.0, buscar la primera tasa válida > 0
                for r in rates_to_check:
                    if r > 0.0:
                        # Si es menor que 1.0 (ej. 0.0016), la invertimos para obtener la tasa real
                        rate = 1.0 / r if r < 1.0 else r
                        break

        # Obtener las monedas específicas para USD y VES
        usd_currency = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
        ves_currency = company.currency_foreign_id or getattr(company, 'currency_id_dif', False)
        is_ves_foreign = ves_currency and (ves_currency.name in ['VES', 'VEF', 'Bs.', 'Bs'] or 'Bs' in (ves_currency.symbol or ''))
        if not is_ves_foreign:
            ves_currency = self.env['res.currency'].search([('name', 'in', ['VES', 'VEF'])], limit=1)

        # Definir la moneda de referencia del segundo bloque y el operador de conversión
        if is_invoice_in_usd:
            # Factura en USD -> El segundo bloque de referencia se muestra en bolívares (VES/VEF)
            foreign_currency = ves_currency or company.currency_id
            convert = lambda val: val * rate
        else:
            # Factura en Bolívares -> El segundo bloque de referencia se muestra en USD
            foreign_currency = usd_currency or getattr(company, 'currency_id_dif', False)
            # Si por alguna razón la tasa es la inversa directa de Odoo (ej. 0.0016), y el rate guardado es el inverso:
            # En Odoo.sh, move.foreign_rate contiene la tasa en bolívares por dólar (ej. 617.64).
            # Por lo tanto, dividimos el valor en Bs por la tasa para obtener USD.
            convert = lambda val: val / rate

        try:
            # 1. Obtener y calcular montos nativos de la factura en la moneda de la factura
            subtotal_amount = sum(sub.get("base_amount_currency", 0.0) for sub in res.get("subtotals", []))
            tax_amount = sum(sub.get("tax_amount_currency", 0.0) for sub in res.get("subtotals", []))
            total_amount = subtotal_amount + tax_amount

            # 2. Convertir montos a moneda extranjera SOLO para display
            foreign_amount_untaxed = convert(subtotal_amount)
            foreign_amount_total = convert(total_amount)

            # IMPORTANTE: NO sobreescribir amount_total ni amount_untaxed.
            # Odoo 18 usa estos campos nativos para la validación del balance del asiento
            # en _check_balanced(). Sobreescribirlos con valores convertidos provoca
            # que tax_totals.tax_amount sea incorrecto (ej. 88.0/623 = 0.14 en lugar de 88.0)
            # y el asiento falle la validación.
            res["formatted_amount_untaxed"] = formatLang(self.env, subtotal_amount, currency_obj=currency)
            res["formatted_amount_total"] = formatLang(self.env, total_amount, currency_obj=currency)

            res["foreign_amount_untaxed"] = foreign_amount_untaxed
            res["foreign_amount_total"] = foreign_amount_total

            # 3. Convertir lista de subtotales
            res["foreign_subtotals"] = []
            for subtotal in res.get("subtotals", []):
                f_subtotal_amount = convert(subtotal.get("base_amount_currency", 0.0))
                res["foreign_subtotals"].append({
                    "name": subtotal.get("name"),
                    "amount": f_subtotal_amount,
                    "formatted_amount": formatLang(self.env, f_subtotal_amount, currency_obj=foreign_currency)
                })

            # 4. Convertir grupos de impuestos
            groups_by_foreign_subtotal = {}
            groups_by_subtotal = {}
            for subtotal in res.get("subtotals", []):
                s_name = subtotal.get("name")
                groups_by_foreign_subtotal[s_name] = []
                groups_by_subtotal[s_name] = []
                for tg in subtotal.get("tax_groups", []):
                    base_amount_cur = tg.get("base_amount_currency", 0.0)
                    tax_amount_cur = tg.get("tax_amount_currency", 0.0)
                    
                    f_base_amount = convert(base_amount_cur)
                    f_tax_amount = convert(tax_amount_cur)
                    
                    groups_by_foreign_subtotal[s_name].append({
                        "tax_group_id": tg.get("id"),
                        "tax_group_name": tg.get("group_name"),
                        "tax_group_base_amount": f_base_amount,
                        "tax_group_amount": f_tax_amount,
                        "base_amount": f_base_amount,
                        "tax_amount": f_tax_amount,
                        "formatted_tax_group_base_amount": formatLang(self.env, f_base_amount, currency_obj=foreign_currency),
                        "formatted_tax_group_amount": formatLang(self.env, f_tax_amount, currency_obj=foreign_currency),
                    })
                    
                    groups_by_subtotal[s_name].append({
                        "tax_group_id": tg.get("id"),
                        "tax_group_name": tg.get("group_name"),
                        "tax_group_base_amount": base_amount_cur,
                        "tax_group_amount": tax_amount_cur,
                        "formatted_tax_group_base_amount": formatLang(self.env, base_amount_cur, currency_obj=currency),
                        "formatted_tax_group_amount": formatLang(self.env, tax_amount_cur, currency_obj=currency),
                    })
                    
            res["groups_by_foreign_subtotal"] = groups_by_foreign_subtotal
            res["groups_by_subtotal"] = groups_by_subtotal
            res["foreign_formatted_amount_untaxed"] = formatLang(self.env, foreign_amount_untaxed, currency_obj=foreign_currency)
            res["foreign_formatted_amount_total"] = formatLang(self.env, foreign_amount_total, currency_obj=foreign_currency)

            # 5. Crear la estructura unificada (para el frontend de la localización)
            unified_rows = []
            for sub_index, subtotal in enumerate(res.get("subtotals", [])):
                name = subtotal.get("name")
                f_subtotals = res.get("foreign_subtotals", [])
                f_subtotal_formatted = f_subtotals[sub_index].get("formatted_amount") if len(f_subtotals) > sub_index else formatLang(self.env, 0.0, currency_obj=foreign_currency)
                
                unified_rows.append({
                    "label": name,
                    "usd": f_subtotal_formatted,
                    "bs": formatLang(self.env, subtotal.get("base_amount_currency", 0.0), currency_obj=currency),
                    "is_total": False,
                    "is_subtotal": True,
                })

                if name in groups_by_subtotal:
                    for g_index, group in enumerate(groups_by_subtotal[name]):
                        f_groups = groups_by_foreign_subtotal.get(name, [])
                        f_group_formatted = f_groups[g_index].get("formatted_tax_group_amount") if len(f_groups) > g_index else formatLang(self.env, 0.0, currency_obj=foreign_currency)
                        
                        unified_rows.append({
                            "label": group.get("tax_group_name"),
                            "usd": f_group_formatted,
                            "bs": group.get("formatted_tax_group_amount"),
                            "is_total": False,
                            "is_subtotal": False,
                        })

            # Fila de Total Final
            unified_rows.append({
                "label": _("TOTAL"),
                "usd": res["foreign_formatted_amount_total"],
                "bs": res["formatted_amount_total"],
                "is_total": True,
                "is_subtotal": False,
            })
            res["unified_rows"] = unified_rows

        except Exception as e:
            _logger.warning("Error calculating foreign tax totals (bimonetary): %s", e)

        return res


    def get_foreign_base_tax_lines(self, base_lines, tax_lines, currency):
        foreign_base_lines = [line.copy() for line in base_lines if line]
        foreign_tax_lines = None
        if tax_lines:
            foreign_tax_lines = [line.copy() for line in tax_lines if line]

        # Obtener la factura para determinar la conversión reactiva exacta
        move = False
        for base_line in base_lines:
            record = base_line.get("record")
            if record and hasattr(record, 'move_id') and record.move_id:
                move = record.move_id
                break

        rate = 1.0
        is_usd_invoice = False
        if move:
            rate = move.tax_today or move.foreign_rate or 1.0
            if rate <= 0.0:
                rate = 1.0
            is_usd_invoice = move.currency_id != self.env.company.currency_id

        if is_usd_invoice:
            convert = lambda val: val * rate
        else:
            convert = lambda val: val / rate

        taxes = []
        for base_line in foreign_base_lines:
            price_unit = base_line.get("price_unit", 0.0)
            price_subtotal = base_line.get("price_subtotal", 0.0)

            base_line["price_unit"] = convert(price_unit)
            base_line["price_subtotal"] = convert(price_subtotal)
            base_line["currency"] = currency

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
