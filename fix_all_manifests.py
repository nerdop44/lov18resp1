import os
import ast

def fix_manifests(root_dir):
    print(f"Scanning {root_dir}...")
    for item in os.listdir(root_dir):
        path = os.path.join(root_dir, item)
        if os.path.isdir(path):
            manifest_path = os.path.join(path, '__manifest__.py')
            if os.path.exists(manifest_path):
                print(f"Processing {manifest_path}...")
                try:
                    with open(manifest_path, 'r') as f:
                        content = f.read()
                    
                    try:
                        manifest = ast.literal_eval(content)
                    except Exception as e:
                        print(f"Error parsing {manifest_path}: {e}")
                        continue
                        
                    if not manifest.get('installable', False):
                        print(f"  -> Fixing installable: True in {item}")
                        # We use simple string replacement to preserve formatting/comments
                        # if 'installable' is present but False
                        if "'installable': False" in content:
                            new_content = content.replace("'installable': False", "'installable': True")
                        elif '"installable": False' in content:
                            new_content = content.replace('"installable": False', '"installable": True')
                        else:
                            # It might be missing. We need to add it.
                            # Look for the last closing brace and insert before it
                            last_brace = content.rfind('}')
                            if last_brace != -1:
                                new_content = content[:last_brace] + "    'installable': True,\n}"
                            else:
                                print("  -> Could not find closing brace to insert installable key.")
                                continue
                                
                        with open(manifest_path, 'w') as f:
                            f.write(new_content)
                    else:
                        print(f"  -> Already installable.")
                        
                except Exception as e:
                    print(f"Error processing {manifest_path}: {e}")

if __name__ == "__main__":
    fix_manifests('/home/nerdop/laboratorio/LocVe18v2')
