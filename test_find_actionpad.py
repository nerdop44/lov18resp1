import os
for root, dirs, files in os.walk('/home/odoo/src/odoo/addons/point_of_sale/static/src'):
    for file in files:
        if file.endswith('.xml'):
            path = os.path.join(root, file)
            with open(path, 'r') as f:
                content = f.read()
                if 'ActionpadWidget' in content or 'pos_control_buttons' in content:
                    print(f"File: {path}")
