#!/usr/bin/env python3
"""
Sincronizador Quirúrgico de Submódulos Odoo.sh v2 (Genérico)
Basado en variables de contexto de .agent/project_context.md
"""
import subprocess
import os
import sys
import re

def run(cmd, cwd=None):
    print(f"Executing: {cmd} (in {cwd or '.'})")
    result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result.stdout.strip()

def get_context_variable(var_name):
    """Extrae una variable del archivo de contexto en formato Markdown."""
    context_path = os.path.join(os.getcwd(), ".agent/project_context.md")
    if not os.path.exists(context_path):
        print(f"Error: No se encontró el archivo de contexto en {context_path}")
        sys.exit(1)
    
    with open(context_path, 'r') as f:
        content = f.read()
        # Busca patrones tipo [VAR_NAME]: valor
        match = re.search(f"\[{var_name}\]:\s*(.*)", content)
        if match:
            return match.group(1).strip()
    return None

def main():
    if len(sys.argv) < 2:
        print("Uso: odoo_sync_v2.py <entorno> [mensaje_commit]")
        print("Ejemplo: odoo_sync_v2.py Prueba 'Mejoras en vistas'")
        sys.exit(1)

    entorno = sys.argv[1]
    custom_msg = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""

    # Carga de variables del contexto
    repo_submodule = get_context_variable("REPO_SUBMODULE_PATH")
    main_repo_url = get_context_variable("MAIN_REPO_SSH")
    submodule_github_path = get_context_variable("SUBMODULE_PATH_IN_MAIN")
    
    # Determinar rama de destino según entorno
    branch_target = entorno # Por defecto usa el nombre del entorno como rama
    
    if not all([repo_submodule, main_repo_url, submodule_github_path]):
        print("Error: Faltan variables obligatorias en .agent/project_context.md")
        print(f"REPO_SUBMODULE_PATH: {repo_submodule}")
        print(f"MAIN_REPO_SSH: {main_repo_url}")
        print(f"SUBMODULE_PATH_IN_MAIN: {submodule_github_path}")
        sys.exit(1)

    temp_dir = f"/tmp/odoo_sync_{entorno.lower()}"
    
    print(f"--- Fase 1: Sincronizando Submódulo ({entorno}) ---")
    current_branch = run("git branch --show-current", cwd=repo_submodule)
    run(f"git push origin {current_branch}", cwd=repo_submodule)
    # Empuja también a la rama sombra del entorno en el repo de localización
    run(f"git push origin {current_branch}:{branch_target}", cwd=repo_submodule)
    new_hash = run("git rev-parse HEAD", cwd=repo_submodule)
    print(f"Nuevo Hash del Submódulo: {new_hash}")

    print(f"--- Fase 2: Actualización Quirúrgica en {temp_dir} ---")
    run(f"rm -rf {temp_dir}")
    run(f"git clone -b {branch_target} {main_repo_url} {temp_dir}")
    
    run(f"git submodule update --init --remote {submodule_github_path}", cwd=temp_dir)
    run(f"git add {submodule_github_path}", cwd=temp_dir)

    commit_msg = f"chore({entorno.lower()}): {custom_msg} (submodule {new_hash[:7]})" if custom_msg else f"chore: surgical sync {entorno} {new_hash[:7]}"
    
    status = run("git status --porcelain", cwd=temp_dir)
    if status:
        run(f'git commit -m "{commit_msg}"', cwd=temp_dir)
        run(f"git push origin {branch_target}", cwd=temp_dir)
        print(f"--- ÉXITO: Despliegue completado a {branch_target} ---")
    else:
        print(f"--- AVISO: El submódulo ya estaba actualizado en {branch_target} ---")

    run(f"rm -rf {temp_dir}")

if __name__ == "__main__":
    main()
