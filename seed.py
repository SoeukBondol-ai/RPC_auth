import sys

sys.path.insert(0, ".")

import config
from auth_service import db


def main():
    db.init_db()
    print("Database initialized.")

    for username, password in config.get_seed_users():
        if db.user_exists(username):
            print(f"  {username:8s} — already exists")
        else:
            db.create_user(username, password)
            print(f"  {username:8s} — created")


if __name__ == "__main__":
    main()
