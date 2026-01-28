import argparse
import getpass
import re

import bcrypt

from src.db import init_db, upsert_admin_user

USERNAME_RE = re.compile(r"^[a-zA-Z0-9._-]{3,32}$")


def main():
    parser = argparse.ArgumentParser(description="Create/update an admin user password.")
    parser.add_argument("--username", default="admin", help="Admin username (default: admin)")
    args = parser.parse_args()

    init_db()

    username = (args.username or "admin").strip()
    if not USERNAME_RE.match(username):
        raise SystemExit("Invalid username. Use 3-32 chars: letters, numbers, . _ -")

    pwd1 = getpass.getpass(f"New password for '{username}': ")
    pwd2 = getpass.getpass("Confirm password: ")
    if pwd1 != pwd2:
        raise SystemExit("Passwords do not match.")
    if len(pwd1) < 4:
        raise SystemExit("Use at least 4 characters (recommend 16+).")

    hashed = bcrypt.hashpw(pwd1.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    upsert_admin_user(username, hashed, active=True)

    print(f"✅ Admin password set/updated for user '{username}'.")


if __name__ == "__main__":
    main()