import os
import sys
from pathlib import Path
from getpass import getpass
from bcrypt import hashpw, gensalt
from dotenv import load_dotenv

# -----------------------------
# Ensure project root on path
# -----------------------------
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

# -----------------------------
# Load .env explicitly
# -----------------------------
ENV_PATH = ROOT / ".env"
load_dotenv(ENV_PATH)

# -----------------------------
# Now imports are safe
# -----------------------------
from src.db import init_db, upsert_admin_user


def main():
    init_db()

    username = input("Admin username: ").strip()
    password = getpass("Admin password: ").strip()

    if not username or not password:
        raise SystemExit("Username and password are required")

    password_hash = hashpw(password.encode(), gensalt()).decode()

    admin_id = upsert_admin_user(
        username=username,
        password_hash=password_hash,
        active=True
    )

    print(f"✅ Admin '{username}' ready (id={admin_id})")


if __name__ == "__main__":
    main()