"""Explicit local administration; passwords entered via hidden prompt."""

import argparse
from getpass import getpass

from sqlalchemy import select

from .db import SessionLocal
from .models import AuditEvent, User
from .security import passwords


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["create-admin"])
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    password = getpass("New admin password (12+ characters): ")
    if len(password) < 12 or len(password) > 128 or getpass("Confirm password: ") != password:
        raise SystemExit("Password requirements or confirmation failed.")
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == args.email.lower())):
            raise SystemExit("Account already exists. No role or password changed.")
        admin = User(
            email=args.email.lower(),
            name="Administrator",
            password_hash=passwords.hash(password),
            verified=True,
            role="admin",
        )
        db.add(admin)
        db.flush()
        db.add(AuditEvent(user_id=admin.id, action="Administrator created through local CLI"))
        db.commit()
    print("Administrator created. Password was not logged.")


if __name__ == "__main__":
    main()
