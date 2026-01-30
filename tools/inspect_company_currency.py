
from odoo import fields, models, api

def inspect_currencies(env):
    company = env.company
    print(f"Company: {company.name}")
    print(f"Main Currency: {company.currency_id.name} (ID: {company.currency_id.id})")
    print(f"Dual Currency: {company.currency_id_dif.name} (ID: {company.currency_id_dif.id}) if company.currency_id_dif else 'None'")
    
    if company.currency_id == company.currency_id_dif:
        print("WARNING: Main Currency and Dual Currency are the SAME.")
    else:
        print("Currencies are different.")

    # List available currencies
    usd = env['res.currency'].search([('name', '=', 'USD')], limit=1)
    ves = env['res.currency'].search([('name', 'in', ['VES', 'Bs.', 'Bs'])], limit=1) # Adjust search if needed
    
    print(f"USD ID: {usd.id if usd else 'Not Found'}")
    print(f"VES ID: {ves.id if ves else 'Not Found'}")

