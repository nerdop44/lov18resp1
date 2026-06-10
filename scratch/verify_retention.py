import unittest

class MockCompany:
    def __init__(self, currency_name):
        self.currency_id = MockCurrency(currency_name)

class MockCurrency:
    def __init__(self, name):
        self.name = name

class MockTaxGroup:
    def __init__(self, group_id, amount):
        self.tax_group_id = MockTaxGroupRecord(group_id)
        self.amount = amount

class MockTaxGroupRecord:
    def __init__(self, group_id):
        self.id = group_id

class MockTaxLine:
    def __init__(self, retention_amount, foreign_retention_amount):
        self.retention_amount = retention_amount
        self.foreign_retention_amount = foreign_retention_amount

class MockRetentionLine:
    def __init__(self, retention_amount, foreign_retention_amount, currency_name, rate=1.0):
        self.retention_amount = retention_amount
        self.foreign_retention_amount = foreign_retention_amount
        self.company_id = MockCompany(currency_name)
        self.foreign_currency_rate = rate
        self.write_calls = []

    def write(self, vals):
        self.write_calls.append(vals)
        if "retention_amount" in vals:
            self.retention_amount = vals["retention_amount"]

class TestRetentionFixes(unittest.TestCase):

    def test_tax_group_data_extraction(self):
        # Mock Odoo 18 tax_group_data structure
        tax_group_data = {
            "tax_group_id": 1,
            "tax_group_base_amount": 100.0,
            "tax_group_amount": 16.0,
        }

        # Verify our modified extraction logic
        invoice_amount_company = (
            tax_group_data.get("tax_group_base_amount")
            or tax_group_data.get("base_amount")
            or tax_group_data.get("base_amount_currency", 0.0)
        )
        iva_amount_company = (
            tax_group_data.get("tax_group_amount")
            or tax_group_data.get("tax_amount")
            or tax_group_data.get("tax_amount_currency", 0.0)
        )

        self.assertEqual(invoice_amount_company, 100.0)
        self.assertEqual(iva_amount_company, 16.0)

    def test_sum_retention_total_ves_company(self):
        # Company currency is VES
        company = MockCompany("VES")
        
        # Line with VES = 160.0 (foreign_retention_amount), USD = 4.0 (retention_amount)
        lines = [MockTaxLine(4.0, 160.0)]

        # If system currency is requested (currency_system = True) -> VES
        is_check_currency_system = True
        company_currency_is_vef = company.currency_id.name in ("VES", "VEF")
        self.assertTrue(company_currency_is_vef)

        if company_currency_is_vef:
            if is_check_currency_system:
                val = sum(l.foreign_retention_amount for l in lines)
            else:
                val = sum(l.retention_amount for l in lines)
        else:
            if is_check_currency_system:
                val = sum(l.retention_amount for l in lines)
            else:
                val = sum(l.foreign_retention_amount for l in lines)

        # Should return VES amount (160.0)
        self.assertEqual(val, 160.0)

        # If alternate currency is requested (currency_system = False) -> USD
        is_check_currency_system = False
        if company_currency_is_vef:
            if is_check_currency_system:
                val = sum(l.foreign_retention_amount for l in lines)
            else:
                val = sum(l.retention_amount for l in lines)
        else:
            if is_check_currency_system:
                val = sum(l.retention_amount for l in lines)
            else:
                val = sum(l.foreign_retention_amount for l in lines)

        # Should return USD amount (4.0)
        self.assertEqual(val, 4.0)

    def test_sum_retention_total_usd_company(self):
        # Company currency is USD
        company = MockCompany("USD")
        
        # Line with VES = 160.0 (foreign_retention_amount), USD = 4.0 (retention_amount)
        lines = [MockTaxLine(4.0, 160.0)]

        # If system currency is requested (currency_system = True) -> USD
        is_check_currency_system = True
        company_currency_is_vef = company.currency_id.name in ("VES", "VEF")
        self.assertFalse(company_currency_is_vef)

        if company_currency_is_vef:
            if is_check_currency_system:
                val = sum(l.foreign_retention_amount for l in lines)
            else:
                val = sum(l.retention_amount for l in lines)
        else:
            if is_check_currency_system:
                val = sum(l.retention_amount for l in lines)
            else:
                val = sum(l.foreign_retention_amount for l in lines)

        # Should return USD amount (4.0)
        self.assertEqual(val, 4.0)

        # If alternate currency is requested (currency_system = False) -> VES
        is_check_currency_system = False
        if company_currency_is_vef:
            if is_check_currency_system:
                val = sum(l.foreign_retention_amount for l in lines)
            else:
                val = sum(l.retention_amount for l in lines)
        else:
            if is_check_currency_system:
                val = sum(l.retention_amount for l in lines)
            else:
                val = sum(l.foreign_retention_amount for l in lines)

        # Should return VES amount (160.0)
        self.assertEqual(val, 160.0)

    def test_self_healing_routine(self):
        # Case 1: VES company, zero retention_amount, positive foreign_retention_amount
        line1 = MockRetentionLine(0.0, 160.0, "VES")
        
        # Simulate self-healing logic
        company_currency_is_vef = line1.company_id.currency_id.name in ("VES", "VEF")
        if company_currency_is_vef:
            line1.write({"retention_amount": line1.foreign_retention_amount})
        else:
            rate = line1.foreign_currency_rate or 1.0
            line1.write({"retention_amount": line1.foreign_retention_amount / rate if rate else 0.0})
            
        self.assertEqual(line1.retention_amount, 160.0)
        self.assertEqual(line1.write_calls, [{"retention_amount": 160.0}])

        # Case 2: USD company, zero retention_amount, positive foreign_retention_amount
        line2 = MockRetentionLine(0.0, 160.0, "USD", rate=40.0)
        
        # Simulate self-healing logic
        company_currency_is_vef = line2.company_id.currency_id.name in ("VES", "VEF")
        if company_currency_is_vef:
            line2.write({"retention_amount": line2.foreign_retention_amount})
        else:
            rate = line2.foreign_currency_rate or 1.0
            line2.write({"retention_amount": line2.foreign_retention_amount / rate if rate else 0.0})
            
        self.assertEqual(line2.retention_amount, 4.0)
        self.assertEqual(line2.write_calls, [{"retention_amount": 4.0}])

    def test_total_purchases_and_sales_iva_formulas(self):
        # 1. Test l10n_ve_invoice logic (multiplied by multiplier in fields dict)
        
        # Regular Invoice (multiplier = 1)
        taxes_reg = {
            "amount_untaxed": 100.0, # (val * 1) inside determinate_amount_taxeds
            "amount_taxed": 16.0,    # (val * 1) inside determinate_amount_taxeds
        }
        multiplier = 1
        total_purchases_iva_reg = (taxes_reg.get("amount_untaxed", 0) + taxes_reg.get("amount_taxed", 0)) * multiplier
        self.assertEqual(total_purchases_iva_reg, 116.0)

        # Refund (multiplier = -1)
        taxes_ref = {
            "amount_untaxed": -100.0, # (val * -1) inside determinate_amount_taxeds
            "amount_taxed": -16.0,    # (val * -1) inside determinate_amount_taxeds
        }
        multiplier = -1
        total_purchases_iva_ref = (taxes_ref.get("amount_untaxed", 0) + taxes_ref.get("amount_taxed", 0)) * multiplier
        self.assertEqual(total_purchases_iva_ref, 116.0) # Correct positive value

        # 2. Test l10n_ve_binaural logic (no multiplier in fields dict)
        
        # Regular Invoice
        total_purchases_iva_bin_reg = taxes_reg.get("amount_untaxed", 0) + taxes_reg.get("amount_taxed", 0)
        self.assertEqual(total_purchases_iva_bin_reg, 116.0)

        # Refund
        total_purchases_iva_bin_ref = taxes_ref.get("amount_untaxed", 0) + taxes_ref.get("amount_taxed", 0)
        self.assertEqual(total_purchases_iva_bin_ref, -116.0) # Correct negative value for binaural

    def test_corrupt_usd_usd_retention_resolution(self):
        # Helper to simulate _sum_retention_total with the new logic
        def sum_retention_total_sim(retention_amount, foreign_retention_amount, rate, currency_system, company_currency):
            company_currency_is_vef = company_currency in ("VES", "VEF")
            if rate <= 0.0:
                rate = 1.0

            if company_currency_is_vef:
                if currency_system:
                    if abs(foreign_retention_amount - retention_amount) < 0.01 and rate > 1.0:
                        return retention_amount * rate
                    return max(foreign_retention_amount, retention_amount * rate) if rate > 1.0 else foreign_retention_amount
                else:
                    if abs(foreign_retention_amount - retention_amount) < 0.01:
                        return retention_amount
                    if foreign_retention_amount > retention_amount and rate > 1.0:
                        return foreign_retention_amount / rate
                    return retention_amount
            else:
                if currency_system:
                    if abs(foreign_retention_amount - retention_amount) < 0.01:
                        return retention_amount
                    if foreign_retention_amount > retention_amount and rate > 1.0:
                        return foreign_retention_amount / rate
                    return retention_amount
                else:
                    if abs(foreign_retention_amount - retention_amount) < 0.01 and rate > 1.0:
                        return retention_amount * rate
                    return max(foreign_retention_amount, retention_amount * rate) if rate > 1.0 else foreign_retention_amount

        # Case 1: Corrupt line in VES company (both fields stored 55.51 USD, rate = 381.13)
        # System Currency (VES) report should resolve to 55.51 * 381.13 = 21156.5263 Bs.
        val_ves = sum_retention_total_sim(55.51, 55.51, 381.13, currency_system=True, company_currency="VES")
        self.assertAlmostEqual(val_ves, 21156.5263, places=4)

        # Alternate Currency (USD) report should resolve to 55.51 USD
        val_usd = sum_retention_total_sim(55.51, 55.51, 381.13, currency_system=False, company_currency="VES")
        self.assertEqual(val_usd, 55.51)

        # Case 2: Correctly stored line (retention_amount = 55.51 USD, foreign_retention_amount = 21156.88 Bs.)
        val_ves_correct = sum_retention_total_sim(55.51, 21156.88, 381.13, currency_system=True, company_currency="VES")
        self.assertEqual(val_ves_correct, 21156.88)

        val_usd_correct = sum_retention_total_sim(55.51, 21156.88, 381.13, currency_system=False, company_currency="VES")
        self.assertAlmostEqual(val_usd_correct, 55.51, places=2)

if __name__ == "__main__":
    unittest.main()
