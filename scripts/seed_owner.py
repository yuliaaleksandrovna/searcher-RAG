"""
Creates (or promotes) the first owner account so there's a way into /admin/*.
Usage:
    python scripts/seed_owner.py --username admin --password secret123
    python scripts/seed_owner.py            (prompts interactively)
"""

import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.models import Role, User, seed_roles, ROLE_OWNER  # noqa: E402
from app.auth import hash_password  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--username")
    parser.add_argument("--password")
    args = parser.parse_args()

    username = args.username or input("Owner username: ").strip()
    password = args.password or getpass.getpass("Owner password: ")

    if len(password) < 6:
        print("ERROR: password must be at least 6 characters")
        sys.exit(1)

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_roles(db)
        owner_role = db.query(Role).filter(Role.name == ROLE_OWNER).first()

        user = db.query(User).filter(User.username == username).first()
        if user:
            user.role_id = owner_role.id
            user.password_hash = hash_password(password)
            db.commit()
            print(f"Promoted existing user '{username}' to owner and reset password.")
        else:
            user = User(
                username=username,
                password_hash=hash_password(password),
                role_id=owner_role.id,
            )
            db.add(user)
            db.commit()
            print(f"Created owner user '{username}'.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
