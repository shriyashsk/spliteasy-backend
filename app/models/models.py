import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Boolean, Numeric, Text, Integer,
    ForeignKey, Date, UniqueConstraint, DateTime
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)
    auth_provider = Column(String(50), default="email")
    oauth_provider_id = Column(String(255), nullable=True)
    email_verified = Column(Boolean, default=False)
    preferred_currency = Column(String(10), default="USD")
    avatar_url = Column(Text, nullable=True)
    timezone = Column(String(100), nullable=True)
    status = Column(String(50), default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)


class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String(255), primary_key=True)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    user_agent = Column(Text, nullable=True)
    ip_address = Column(String(100), nullable=True)

    user = relationship("User")


class Group(Base):
    __tablename__ = "groups"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False)
    created_by_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    currency = Column(String(10), default="USD")
    description = Column(Text, nullable=True)
    cover_image_url = Column(Text, nullable=True)
    group_icon = Column(Text, nullable=True)
    category = Column(String(50), nullable=True)
    default_split_preference = Column(String(50), default="equal")
    status = Column(String(50), default="active")
    archived_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    members = relationship("GroupMember", back_populates="group")
    expenses = relationship("Expense", back_populates="group")


class GroupMember(Base):
    __tablename__ = "group_members"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    group_id = Column(UUID(as_uuid=False), ForeignKey("groups.id"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    invited_by_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    role = Column(String(50), default="member")
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    removed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (UniqueConstraint("group_id", "user_id"),)

    group = relationship("Group", back_populates="members")
    user = relationship("User", foreign_keys=[user_id])


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    group_id = Column(UUID(as_uuid=False), ForeignKey("groups.id"), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False)
    paid_by_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_by_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    split_type = Column(String(50), nullable=False)
    expense_date = Column(Date, default=date.today)
    status = Column(String(50), default="active")
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    group = relationship("Group", back_populates="expenses")
    splits = relationship("ExpenseSplit", back_populates="expense", cascade="all, delete-orphan")
    comments = relationship("ExpenseComment", back_populates="expense")
    paid_by = relationship("User", foreign_keys=[paid_by_user_id])


class ExpenseSplit(Base):
    __tablename__ = "expense_splits"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    expense_id = Column(UUID(as_uuid=False), ForeignKey("expenses.id"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    percentage = Column(Numeric(5, 2), nullable=True)
    share_count = Column(Integer, nullable=True)
    exchange_rate = Column(Numeric(18, 6), nullable=True)
    is_settled = Column(Boolean, default=False)
    settled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    expense = relationship("Expense", back_populates="splits")
    user = relationship("User")


class Balance(Base):
    __tablename__ = "balances"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    group_id = Column(UUID(as_uuid=False), ForeignKey("groups.id"), nullable=False)
    user_id_1 = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    user_id_2 = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    net_amount = Column(Numeric(12, 2), nullable=False, default=0)
    currency = Column(String(10), nullable=False, default="USD")
    last_updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("group_id", "user_id_1", "user_id_2"),)

    user1 = relationship("User", foreign_keys=[user_id_1])
    user2 = relationship("User", foreign_keys=[user_id_2])


class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    group_id = Column(UUID(as_uuid=False), ForeignKey("groups.id"), nullable=False)
    paid_by_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    paid_to_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(10), nullable=False)
    note = Column(Text, nullable=True)
    upi_transaction_ref = Column(String(255), nullable=True)
    status = Column(String(50), default="confirmed")
    settlement_date = Column(Date, default=date.today)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    paid_by = relationship("User", foreign_keys=[paid_by_user_id])
    paid_to = relationship("User", foreign_keys=[paid_to_user_id])


class EditLog(Base):
    __tablename__ = "edit_logs"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    entity_type = Column(String(100), nullable=False)
    entity_id = Column(UUID(as_uuid=False), nullable=False)
    changed_by_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    change_type = Column(String(50), nullable=False)
    before_json = Column(JSONB, nullable=True)
    after_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    changed_by = relationship("User")


class Invite(Base):
    __tablename__ = "invites"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    token = Column(String(255), unique=True, nullable=False)
    group_id = Column(UUID(as_uuid=False), ForeignKey("groups.id"), nullable=False)
    invited_email = Column(String(255), nullable=False)
    invited_by_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"))
    status = Column(String(50), default="pending")
    accepted_by_user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    group = relationship("Group")
    invited_by = relationship("User", foreign_keys=[invited_by_user_id])


class ExpenseComment(Base):
    __tablename__ = "expense_comments"

    id = Column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    expense_id = Column(UUID(as_uuid=False), ForeignKey("expenses.id"), nullable=False)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    expense = relationship("Expense", back_populates="comments")
    user = relationship("User")