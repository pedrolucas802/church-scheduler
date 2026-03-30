#!/usr/bin/env python3
"""
Sync users from database to Keycloak.
Creates Keycloak accounts for database users that don't have them.
"""

import sys
from pathlib import Path

# Ensure `import src...` works
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.db import list_users, update_user_profile
from src.auth.kc import create_user_in_keycloak

def sync_users_to_keycloak():
    """Sync database users to Keycloak."""
    db_users = list_users()
    
    for user in db_users:
        user_id = user[0]
        kc_sub = user[1]
        username = user[2]
        email = user[3]
        full_name = user[4]
        
        if not username or not email:
            print(f"Skipping user {user_id}: missing username or email")
            continue
        
        # Split name
        name_parts = (full_name or "").split()
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
        
        # Default password (users should change it)
        password = "TempPass123!"
        
        # Determine role based on username or assume volunteer
        roles = []
        if "admin" in username.lower():
            roles = ["ministry_admin"]
        elif "super" in username.lower():
            roles = ["super_admin"]
        else:
            roles = ["volunteer"]
        
        print(f"Syncing user to Keycloak: {username} ({email}) with roles {roles}")
        
        real_kc_sub = create_user_in_keycloak(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            roles=roles
        )
        
        if real_kc_sub:
            # Update the database with the real kc_sub
            update_user_profile(real_kc_sub, full_name, email)
            print(f"✅ Synced {username} with kc_sub {real_kc_sub}")
        else:
            print(f"❌ Failed to sync {username}")

if __name__ == "__main__":
    sync_users_to_keycloak()
