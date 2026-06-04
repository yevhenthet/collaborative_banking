"""Run once to create the first admin user."""
import sys
from app.database import SessionLocal, engine
from app.models import Base, User, Role
from app.auth import hash_password

Base.metadata.create_all(bind=engine)

name = input("Name: ").strip()
email = input("Email: ").strip()
password = input("Password: ").strip()

db = SessionLocal()
if db.query(User).filter(User.email == email).first():
    print("User with this email already exists.")
    sys.exit(1)

user = User(name=name, email=email, password_hash=hash_password(password), role=Role.admin)
db.add(user)
db.commit()
print(f"Admin '{name}' created successfully.")
