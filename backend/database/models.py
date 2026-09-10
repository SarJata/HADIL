from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from .session import Base
import datetime

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    status = Column(String(50), default="active")
    
    orders = relationship("Order", back_populates="user")

class Order(Base):
    __tablename__ = "orders"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    user = relationship("User", back_populates="orders")

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    stock = Column(Integer, default=0)

class HadilQueryHistory(Base):
    __tablename__ = "hadil_query_history"
    
    id = Column(Integer, primary_key=True, index=True)
    natural_query = Column(String(1000), nullable=False)
    sql_query = Column(String(2000), nullable=False)
    usage_count = Column(Integer, default=1)
    last_used = Column(DateTime, default=datetime.datetime.utcnow)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_valid = Column(Integer, default=1)

class HadilDatabaseInsight(Base):
    __tablename__ = "hadil_database_insights"
    
    id = Column(Integer, primary_key=True, index=True)
    database_name = Column(String(255), unique=True, index=True, nullable=False)
    generated_summary = Column(String(4000), nullable=False)
    suggested_queries = Column(String(4000), nullable=False) # JSON string
    generated_at = Column(DateTime, default=datetime.datetime.utcnow)

