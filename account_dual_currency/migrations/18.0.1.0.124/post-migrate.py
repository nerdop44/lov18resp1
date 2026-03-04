
import logging

def migrate(cr, version):
    if not version:
        return

    # Move list_price to list_price_usd only in product_template
    # In Odoo, list_price is physically stored in product_template.
    # product_product uses a computed 'lst_price'.
    cr.execute("""
        UPDATE product_template 
        SET list_price_usd = list_price 
        WHERE (list_price_usd IS NULL OR list_price_usd = 0) 
        AND list_price > 0
    """)
    
    # We skip product_product as it doesn't have a physical list_price column.
    # The ORM will handle the related list_price_usd for variants if needed.
