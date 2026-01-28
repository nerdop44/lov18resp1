import os
import ast
import json

def get_manifest(module_path):
    manifest_file = os.path.join(module_path, "__manifest__.py")
    if not os.path.exists(manifest_file):
        return None
    with open(manifest_file, "r") as f:
        return ast.literal_eval(f.read())

repo_root = "/home/nerdop/laboratorio/LocVe18v2"
modules = [d for d in os.listdir(repo_root) if os.path.isdir(os.path.join(repo_root, d)) and os.path.exists(os.path.join(repo_root, d, "__manifest__.py"))]

dependency_map = {}
all_deps = set()

for module in modules:
    manifest = get_manifest(os.path.join(repo_root, module))
    if manifest:
        deps = manifest.get("depends", [])
        dependency_map[module] = deps
        all_deps.update(deps)

# Separate internal vs external dependencies
internal_modules = set(modules)
external_deps = all_deps - internal_modules

# Topological sort for installation order
def topological_sort(dep_map):
    sorted_modules = []
    visited = set()
    temp_visited = set()

    def visit(node):
        if node in temp_visited:
            raise Exception(f"Circular dependency detected involving {node}")
        if node not in visited:
            temp_visited.add(node)
            # Only recurse on internal dependencies
            for neighbor in dep_map.get(node, []):
                if neighbor in internal_modules:
                    visit(neighbor)
            temp_visited.remove(node)
            visited.add(node)
            sorted_modules.append(node)

    for node in dep_map:
        if node not in visited:
            visit(node)
    return sorted_modules

try:
    install_order = topological_sort(dependency_map)
except Exception as e:
    install_order = str(e)

audit_results = {
    "modules_found": len(modules),
    "dependency_map": dependency_map,
    "external_dependencies": list(external_deps),
    "suggested_install_order": install_order
}

print(json.dumps(audit_results, indent=4))
