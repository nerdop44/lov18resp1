
import os
import ast
import sys

# Define modules to check
MODULES = ['pos_fiscal_printer', 'pos_igtf_tax', 'pos_show_dual_currency']

# Define addons paths (adjust if needed, assuming standard Odoo structure or current dir)
# We will check current directory recursively for these folders
ROOT_DIR = '/home/nerdop/laboratorio/LocVe18v2'

def load_manifest(path):
    try:
        with open(path, 'r') as f:
            return ast.literal_eval(f.read())
    except Exception as e:
        return {'error': str(e)}

print(f"Searching for modules in {ROOT_DIR}...")

for mod in MODULES:
    mod_path = os.path.join(ROOT_DIR, mod)
    manifest_path = os.path.join(mod_path, '__manifest__.py')
    
    print(f"\n--- {mod} ---")
    if os.path.exists(manifest_path):
        print(f"Found manifest at: {manifest_path}")
        info = load_manifest(manifest_path)
        
        if 'error' in info:
            print(f"ERROR parsing manifest: {info['error']}")
        else:
            installable = info.get('installable', True) # Default is True in Odoo generally, but let's see.
            # Actually, if not specified, it is True.
            
            print(f"Installable (Raw): {info.get('installable')}")
            print(f"Depends: {info.get('depends')}")
            
            # Check dependencies
            missing_deps = []
            for dep in info.get('depends', []):
                # Simple check if dep folder exists in root or if it is a standard module (we can't easily check standard modules here without full odoo env)
                # But we can check if it is one of OUR modules
                if dep in MODULES and not os.path.exists(os.path.join(ROOT_DIR, dep)):
                     missing_deps.append(dep)
            
            if missing_deps:
                 print(f"WARNING: Missing local dependencies: {missing_deps}")

    else:
        print(f"NOT FOUND: {manifest_path}")
