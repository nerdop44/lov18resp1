
from odoo import fields, models, api

def inspect_currencies(env):
    company = env.company
    print(f"\n=== INSPECTION START ===")
    print(f"Company: {company.name}")
    print(f"Main Currency: {company.currency_id.name} (ID: {company.currency_id.id})")
    print(f"Current Dual Currency: {company.currency_id_dif.name} (ID: {company.currency_id_dif.id})")
    
    if company.currency_id == company.currency_id_dif:
        print("WARNING: Main Currency and Dual Currency are the SAME.")
        print("Attempting to fix...")
        
        # Find potential other currencies
        usd = env['res.currency'].search([('name', '=', 'USD')], limit=1)
        # Search for VES or Bs.
        ves = env['res.currency'].search(['|', ('name', '=', 'VES'), ('name', '=', 'Bs.')], limit=1)
        if not ves:
             ves = env['res.currency'].search([('symbol', 'ilike', 'Bs')], limit=1)

        print(f"Found USD: {usd.name if usd else 'No'}")
        print(f"Found VES: {ves.name if ves else 'No'}")

        target_currency = None
        if company.currency_id == usd and ves:
            target_currency = ves
        elif company.currency_id == ves and usd:
            target_currency = usd
        
        if target_currency:
            print(f"Switching Dual Currency to: {target_currency.name}")
            company.sudo().write({'currency_id_dif': target_currency.id})
            env.cr.commit()
            print("SUCCESS: Configuration updated.")
        else:
            print("ERROR: Could not determine distinct target currency or currency not found.")
    else:
        print("OK: Currencies are already different. No changes made.")
    
    print("=== INSPECTION END ===\n")

# Run functionality
inspect_currencies(env)

