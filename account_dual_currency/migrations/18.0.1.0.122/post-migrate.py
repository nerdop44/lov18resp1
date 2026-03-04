
import logging

def migrate(cr, version):
    if not version:
        return

    # Move list_price to list_price_usd if list_price_usd is 0
    # This assumes that existing values in list_price are actually the USD amounts
    # intended by the user, as per context.
    cr.execute(\"\"\"
        UPDATE product_template 
        SET list_price_usd = list_price 
        WHERE (list_price_usd IS NULL OR list_price_usd = 0) 
        AND list_price > 0
    \"\"\")
    
    cr.execute(\"\"\"
        UPDATE product_product 
        SET list_price_usd = lst_price 
        WHERE (list_price_usd IS NULL OR list_price_usd = 0) 
        AND lst_price > 0
    \"\"\")
