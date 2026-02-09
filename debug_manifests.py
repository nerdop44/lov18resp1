
import odoo
from odoo.modules import load_information_from_description_file
import sys
import os

modules = ['pos_fiscal_printer', 'pos_igtf_tax', 'pos_show_dual_currency']
addons_paths = odoo.tools.config['addons_path'].split(',')

print(f"Checking modules: {modules}")

for mod in modules:
    print(f"\n--- {mod} ---")
    found = False
    for path in addons_paths:
        mod_path = os.path.join(path, mod)
        if os.path.exists(mod_path):
            found = True
            print(f"Found in {mod_path}")
            try:
                info = load_information_from_description_file(mod, mod_path)
                print(f"Installable: {info.get('installable')}")
                print(f"Depends: {info.get('depends')}")
                if not info.get('installable'):
                    print("WARNING: installable is False or None (Defaults to False if not specified?)")
            except Exception as e:
                print(f"Error loading manifest: {e}")
            break
    if not found:
         print("NOT FOUND in addons_path")
