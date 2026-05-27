from datetime import datetime, timezone

from argon2 import PasswordHasher
from sqlalchemy import Column, DateTime, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

import config

ph = PasswordHasher()

engine = create_engine(f"sqlite:///{config.DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    """Create tables and seed default users if empty."""
    Base.metadata.create_all(engine)
    with SessionLocal() as session:
        if session.query(User).first() is None:
            for name, pwd in config.get_seed_users():
                session.add(User(username=name, password_hash=ph.hash(pwd)))
            session.commit()


def get_user(username: str) -> User | None:
    with SessionLocal() as session:
        return session.query(User).filter_by(username=username).first()


def create_user(username: str, password: str) -> User:
    with SessionLocal() as session:
        user = User(username=username, password_hash=ph.hash(password))
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def verify_password(username: str, password: str) -> bool:
    with SessionLocal() as session:
        user = session.query(User).filter_by(username=username).first()
        if user is None:
            return False
        try:
            ph.verify(user.password_hash, password)
            if ph.check_needs_rehash(user.password_hash):
                user.password_hash = ph.hash(password)
                session.commit()
            return True
        except Exception:
            return False


def reset_password(username: str, new_password: str) -> bool:
    with SessionLocal() as session:
        user = session.query(User).filter_by(username=username).first()
        if user is None:
            return False
        user.password_hash = ph.hash(new_password)
        session.commit()
        return True


def user_exists(username: str) -> bool:
    with SessionLocal() as session:
        return session.query(User).filter_by(username=username).first() is not None
