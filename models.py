from sqlalchemy import Column, Integer, String, Date, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String, unique=True, index=True, nullable=False)
    client_name = Column(String)  # Customer contact person
    phone = Column(String)
    industry = Column(String)
    sales_rep = Column(String)    # Internal sales representative
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    orders = relationship("Order", back_populates="customer", cascade="all, delete-orphan")
    interactions = relationship("Interaction", back_populates="customer", cascade="all, delete-orphan")
    quotes = relationship("Quote", back_populates="customer", cascade="all, delete-orphan")

class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    order_date = Column(Date, default=datetime.now)
    product_name = Column(String)
    quantity = Column(Integer, default=0)
    total_amount = Column(Integer, default=0)
    deposit_amount = Column(Integer, default=0)
    is_ordered = Column(Boolean, default=False)
    note = Column(String)

    # Relationship
    customer = relationship("Customer", back_populates="orders")

    @property
    def outstanding_amount(self):
        return self.total_amount - self.deposit_amount

class Interaction(Base):
    __tablename__ = "interactions"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    log_date = Column(Date, default=datetime.now)
    content = Column(String)
    next_action_date = Column(Date)
    status = Column(String) # e.g., 'Contacting', 'Proposed', 'Contracted', 'On Hold'

    # Relationship
    customer = relationship("Customer", back_populates="interactions")

# --- NEW MODELS FOR QUOTES ---

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    category = Column(String)
    unit_price = Column(Integer, default=0)
    description = Column(String)
    options_json = Column(String, default="[]") # e.g. [{"name": "Size", "values": [{"label": "Big", "price": 5000}]}, ...]

class Quote(Base):
    __tablename__ = "quotes"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    quote_date = Column(Date, default=datetime.now)
    valid_until = Column(Date)
    status = Column(String, default="Draft") # Draft, Sent, Accepted, Rejected, Converted
    total_amount = Column(Integer, default=0)
    note = Column(String)
    
    # Relationships
    customer = relationship("Customer", back_populates="quotes")
    items = relationship("QuoteItem", back_populates="quote", cascade="all, delete-orphan")

    quote = relationship("Quote", back_populates="items")
    
class QuoteItem(Base):
    __tablename__ = "quote_items"
    
    id = Column(Integer, primary_key=True, index=True)
    quote_id = Column(Integer, ForeignKey("quotes.id"), nullable=False)
    product_name = Column(String)
    quantity = Column(Integer, default=1)
    unit_price = Column(Integer, default=0)
    amount = Column(Integer, default=0)
    
    # Detailed Specs from AI/User
    print_type = Column(String)  # 1도 단면, etc
    origin = Column(String)      # 국내, 중국
    color = Column(String)
    cutting = Column(Boolean, default=False)
    remote_control = Column(Boolean, default=False)
    due_date = Column(String)    # Kept as string for flexibility (e.g. "1월 5일")
    note = Column(String)
    
    # Additional options JSON if needed
    selected_options = Column(String, default="") 
    
    quote = relationship("Quote", back_populates="items")
