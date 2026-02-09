
printers = env['x.pos.fiscal.printer'].sudo().search([])
print("--- FISCAL PRINTERS START ---")
for p in printers:
    print(f"ID: {p.id} | Name: {p.name} | Serial: {p.serial} | Company: {p.company_id.name} (ID: {p.company_id.id}, Active: {p.company_id.active})")
print("--- FISCAL PRINTERS END ---")
