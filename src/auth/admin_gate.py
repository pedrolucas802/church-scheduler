# src/auth/admin_gate.py
import os
from typing import List

from src.auth.kc import is_logged_in, get_roles

# Comma-separated roles that count as admin when signed in with Keycloak
# Example: KC_ADMIN_ROLES=admin,church_admin
KC_ADMIN_ROLES: List[str] = [
    r.strip()
    for r in os.getenv("KC_ADMIN_ROLES", "admin").split(",")
    if r.strip()
]


def is_admin() -> bool:
    """
    Admin enabled if user is logged in via Keycloak and has one of KC_ADMIN_ROLES.
    """
    if not is_logged_in():
        return False
    roles = set(get_roles())
    return any(r in roles for r in KC_ADMIN_ROLES)