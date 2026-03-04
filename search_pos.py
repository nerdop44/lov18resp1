import urllib.request
url = "https://raw.githubusercontent.com/odoo/odoo/18.0/addons/point_of_sale/static/src/app/screens/product_screen/control_buttons/orderline_note_button/orderline_note_button.js"
req = urllib.request.Request(url)
print(urllib.request.urlopen(req).read().decode('utf-8'))
