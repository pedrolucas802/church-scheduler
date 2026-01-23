import getpass
import bcrypt

from src.db import init_db, upsert_admin_user

def main():
    init_db()

    pwd1 = getpass.getpass("New admin password: ")
    pwd2 = getpass.getpass("Confirm password: ")
    if pwd1 != pwd2:
        raise SystemExit("Passwords do not match.")

    if len(pwd1) < 12:
        raise SystemExit("Use at least 12 characters (recommend 16+).")

    hashed = bcrypt.hashpw(pwd1.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    upsert_admin_user("admin", hashed, active=True)
    print("✅ Admin password set/updated for user 'admin'.")

if __name__ == "__main__":
    main()