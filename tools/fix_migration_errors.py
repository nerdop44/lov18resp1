import re
import os

def fix_odoo_xml(content):
    # Fix attrs={'invisible': ...}
    def replace_attrs(match):
        attr_dict_str = match.group(1)
        # Simplify common attrs
        # attrs="{'invisible': [('state', '=', 'draft')]}" -> invisible="state == 'draft'"
        # Note: Odoo 17+ invisible/readonly/required take a domain string
        
        fixes = []
        # Extract individual keys from the dict-like string
        def extract_domain(key):
            # Matches key: [ ... ] handling nested [ ] one level deep
            pattern = fr"'{key}':\s*(\[[^\[\]]*(?:\[[^\[\]]*\][^\[\]]*)*\])"
            match = re.search(pattern, attr_dict_str)
            return match.group(1) if match else None

        fixes = []
        inv_domain = extract_domain('invisible')
        if inv_domain: fixes.append(f'invisible="{inv_domain}"')
        
        ro_domain = extract_domain('readonly')
        if ro_domain: fixes.append(f'readonly="{ro_domain}"')
        
        req_domain = extract_domain('required')
        if req_domain: fixes.append(f'required="{req_domain}"')
        
        return " ".join(fixes)

    content = re.sub(r'attrs="\{([^\}]+)\}"', replace_attrs, content)
    
    # Fix states="..." for buttons
    # states="draft" -> invisible="state != 'draft'"
    def replace_states_button(match):
        pre = match.group(1)
        states = match.group(2)
        post = match.group(3)
        state_list = [s.strip() for s in states.split(',')]
        if len(state_list) == 1:
            return f'{pre}invisible="state != \'{state_list[0]}\'"{post}'
        else:
            return f'{pre}invisible="state not in {state_list}"{post}'

    content = re.sub(r'(<button[^>]+)states="([^"]+)"([^>]*>)', replace_states_button, content)
    
    # Fix states="..." for fields (usually implies readonly, but Odoo 17+ handles this differently)
    # For fields, states="..." is often equivalent to readonly in certain states
    # This is more complex, but for now let's convert to invisible if that's the intent
    # OR just remove it if it's causing generic ParseErrors
    content = re.sub(r'(<field[^>]+)states="([^"]+)"([^>]*>)', replace_states_button, content)

    return content

repo_root = "/home/nerdop/laboratorio/LocVe18v2"
for root, dirs, files in os.walk(repo_root):
    for file in files:
        if file.endswith(".xml"):
            path = os.path.join(root, file)
            with open(path, "r") as f:
                content = f.read()
            
            new_content = fix_odoo_xml(content)
            
            if new_content != content:
                with open(path, "w") as f:
                    f.write(new_content)
                print(f"Fixed XML: {path}")

# Fix Python files
for root, dirs, files in os.walk(repo_root):
    if "temp_verify" in root: continue
    for file in files:
        if file.endswith(".py"):
            path = os.path.join(root, file)
            with open(path, "r") as f:
                lines = f.readlines()
            
            new_lines = []
            skip_next = False
            for i, line in enumerate(lines):
                if skip_next:
                    if line.strip().endswith("}") or line.strip().endswith("},"):
                        skip_next = False
                    continue
                
                # Remove _valid_field_parameter hack
                    # Skip the next few lines of this method
                    skip_next_block = True
                    continue
                
                # Remove states= from field definitions
                if "states=" in line:
                    # Handle multi-line states
                    if "{" in line and "}" not in line:
                        skip_next = True
                    # Just remove the parameter and the comma if exists
                    line = re.sub(r',\s*states=\{[^\}]+\}', '', line)
                    line = re.sub(r'states=\{[^\}]+\},?', '', line)
                
                if "email_re" in line and "from odoo.tools" not in line: # Avoid removing import
                    continue
                
                new_lines.append(line)
            
            # Additional cleanup for the _valid_field_parameter block if we skipped it
            final_lines = []
            skip_method = False
            for line in new_lines:
                    skip_method = True
                    continue
                if skip_method:
                    if line.strip() == "" or line.startswith("    def ") or line.startswith("class "):
                        skip_method = False
                    else:
                        continue
                final_lines.append(line)
            
            # Post-fix broken brackets like invisible="[('state','not in',['done','paid']])"
            def balance_brackets(match):
                attr_name = match.group(1)
                value = match.group(2)
                open_b = value.count('[')
                close_b = value.count(']')
                open_p = value.count('(')
                close_p = value.count(')')
                if open_b > close_b:
                    value += ']' * (open_b - close_b)
                if open_p > close_p:
                    value += ')' * (open_p - close_p)
                return f'{attr_name}="{value}"'
            
            processed_content = "".join(final_lines)
            processed_content = re.sub(r'(invisible|readonly|required)="([^"]+)"', balance_brackets, processed_content)

            if processed_content != "".join(lines):
                with open(path, "w") as f:
                    f.write(processed_content)
                print(f"Fixed Python: {path}")

# Same for XML
for root, dirs, files in os.walk(repo_root):
    if "temp_verify" in root: continue
    for file in files:
        if file.endswith(".xml"):
            path = os.path.join(root, file)
            with open(path, "r") as f:
                content = f.read()
            
            def balance_brackets(match):
                attr_name = match.group(1)
                value = match.group(2)
                open_b = value.count('[')
                close_b = value.count(']')
                open_p = value.count('(')
                close_p = value.count(')')
                if open_b > close_b:
                    value += ']' * (open_b - close_b)
                if open_p > close_p:
                    value += ')' * (open_p - close_p)
                return f'{attr_name}="{value}"'
            
            new_content = fix_odoo_xml(content)
            new_content = re.sub(r'(invisible|readonly|required)="([^"]+)"', balance_brackets, new_content)
            
            if new_content != content:
                with open(path, "w") as f:
                    f.write(new_content)
                print(f"Fixed XML: {path}")
