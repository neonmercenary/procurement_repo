from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from datetime import datetime
from .db import Base

class Merchant(Base):
    __tablename__ = "merchants"
    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String, unique=True, index=True) # Blockchain Key
    name = Column(String)
    kyb_status = Column(String, default="pending") # "verified", "flagged"
    is_active = Column(Boolean, default=True)
    goods = relationship("Good", back_populates="merchant")

class Good(Base):
    __tablename__ = "goods"
    id = Column(Integer, primary_key=True)
    title = Column(String)
    price_usdc = Column(Float)
    category = Column(String) # e.g., "SaaS", "Data", "Cloud"
    merchant_id = Column(Integer, ForeignKey("merchants.id"))
    merchant = relationship("Merchant", back_populates="goods")

class Policy(Base):
    """The SnowGate Spend Policy defined by the Human Admin"""
    __tablename__ = "policies"
    id = Column(Integer, primary_key=True)
    agent_wallet = Column(String, unique=True)
    daily_limit_usdc = Column(Float)
    restricted_categories = Column(String) # Comma-separated list

class Transaction(Base):
    """The Audit Trail for Tail Spend Analytics"""
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True)
    tx_hash = Column(String, unique=True) # On-chain reference
    buyer_wallet = Column(String)
    merchant_wallet = Column(String)
    amount_usdc = Column(Float)
    category = Column(String)
    timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String) # "completed", "failed", "disputed"



