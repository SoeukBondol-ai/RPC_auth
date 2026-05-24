import sys

sys.path.insert(0, ".")

from auth_service import db


def main():
    db.init_db()
    print("Database initialized.")

    defaults = [("alice", "secret123"), ("bob", "pass456"), ("admin", "admin789")]
    for username, password in defaults:
        if db.user_exists(username):
            print(f"  {username:8s} — already exists")
        else:
            db.create_user(username, password)
            print(f"  {username:8s} — created")


if __name__ == "__main__":
    main()
