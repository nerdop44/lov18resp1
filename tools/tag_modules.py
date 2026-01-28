import os
import re

PREFIX = "[LocVe]"
CATEGORY = "LocVe [Localization]"

def update_manifest(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Update Name
    # Matches 'name': "..." or "name": """..."""
    name_match = re.search(r'([\'"]name[\'"]\s*:\s*([\'"]{1,3}))([^"\'\]]+)(\2)', content)
    if name_match:
        prefix_full = name_match.group(1)
        quote_type = name_match.group(2)
        current_name = name_match.group(3)
        suffix = name_match.group(4)
        
        if PREFIX not in current_name:
            new_name = f"{PREFIX} {current_name}"
            content = content.replace(f"{prefix_full}{current_name}{suffix}", f"{prefix_full}{new_name}{suffix}")

    # Update Category
    category_match = re.search(r'([\'"]category[\'"]\s*:\s*[\'"])([^"\'\]]+)([\'"])', content)
    if category_match:
        prefix_full = category_match.group(1)
        current_cat = category_match.group(2)
        suffix = category_match.group(3)
        
        content = content.replace(f"{prefix_full}{current_cat}{suffix}", f"{prefix_full}{CATEGORY}{suffix}")
    else:
        # If category doesn't exist, insert it after name
        if name_match:
            content = content.replace(name_match.group(0), f"{name_match.group(0)},\n    'category': '{CATEGORY}'")

    with open(filepath, 'w') as f:
        f.write(content)

if __name__ == "__main__":
    repo_root = os.getcwd()
    for root, dirs, files in os.walk(repo_root):
        if "__manifest__.py" in files:
            manifest_path = os.path.join(root, "__manifest__.py")
            print(f"Tagging: {manifest_path}")
            update_manifest(manifest_path)
