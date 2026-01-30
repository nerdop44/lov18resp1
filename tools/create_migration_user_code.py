
from odoo import api, SUPERUSER_ID

def create_migration_user(env):
    try:
        User = env['res.users']
        login = 'migration_api'
        password = 'migration_password_123'
        
        # Search for existing user
        user = User.search([('login', '=', login)], limit=1)
        
        vals = {
            'name': 'Migration API',
            'login': login,
            'password': password,
            'active': True,
        }
        
        if not user:
            print(f"Creating user {login}...")
            user = User.create(vals)
        else:
            print(f"Updating user {login}...")
            user.write(vals)

        # Grant Admin rights
        group_system = env.ref('base.group_system')
        if group_system not in user.groups_id:
            user.write({'groups_id': [(4, group_system.id)]})
            
        env.cr.commit()
        print(f"SUCCESS: User {login} prepared.")
        
    except Exception as e:
        env.cr.rollback()
        print(f"ERROR: {e}")

create_migration_user(env)
