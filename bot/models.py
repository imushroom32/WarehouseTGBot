# bot/models.py
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from bot.config import MANAGER_TELEGRAM_IDS
from bot.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(64), unique=True, nullable=False)
    full_name = Column(String(128))
    role = Column(String(16))  # "manager" | "employee"
    created_at = Column(DateTime, default=datetime.now)

    stocks = relationship("Stock", back_populates="user")

    @staticmethod
    def get_or_create(session, tg_user):
        uid = str(tg_user.id)

        user = session.query(User).filter_by(telegram_id=uid).one_or_none()
        desired_role = "manager" if uid in MANAGER_TELEGRAM_IDS else "employee"

        if user:
            # ▶ если роль изменилась — обновим
            if user.role != desired_role:
                user.role = desired_role
                session.commit()
            return user

        # ▶ создать нового
        user = User(
            telegram_id=uid,
            full_name=tg_user.full_name,
            role=desired_role,
        )
        session.add(user)
        session.commit()
        return user


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.now)

    stocks = relationship("Stock", back_populates="product")


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"))  # ← nullable: складской «ничей»
    quantity = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    product = relationship("Product", back_populates="stocks")
    user = relationship("User", back_populates="stocks")

class Log(Base):
    __tablename__ = "logs"

    id        = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.now)
    action    = Column(String(64))     # "add", "writeoff", "transfer", ...
    user_id   = Column(String(64))     # Telegram ID
    info      = Column(Text)           # что произошло