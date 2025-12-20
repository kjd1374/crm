from sqlalchemy.orm import Session
from sqlalchemy import func
from models_test import Customer, Order, Interaction, Quote, QuoteItem, Product
from datetime import datetime, date
import pandas as pd
import datetime as dt

# --- Customer Operations ---
def get_all_customers(db: Session):
    return db.query(Customer).all()

def get_customer_by_id(db: Session, customer_id: int):
    return db.query(Customer).filter(Customer.id == customer_id).first()

def create_customer(db: Session, customer_data: dict):
    existing = db.query(Customer).filter(Customer.company_name == customer_data['company_name']).first()
    if existing:
        return existing
    
    new_customer = Customer(**customer_data)
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)
    return new_customer

def update_interaction_status(db: Session, interaction_id: int, new_status: str):
    interaction = db.query(Interaction).filter(Interaction.id == interaction_id).first()
    if interaction:
        interaction.status = new_status
        interaction.next_action_date = None 
        db.commit()
        return True
    return False

def reset_database(db: Session):
    try:
        db.query(QuoteItem).delete()
        db.query(Quote).delete()
        db.query(Product).delete()
        db.query(Interaction).delete()
        db.query(Order).delete()
        db.query(Customer).delete()
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        print(f"Reset error: {e}")
        return False

# --- Interaction Operations ---
def add_interaction(db: Session, customer_id: int, content: str, next_action_date: date, status: str):
    new_interaction = Interaction(
        customer_id=customer_id,
        content=content,
        next_action_date=next_action_date,
        status=status,
        log_date=date.today()
    )
    db.add(new_interaction)
    db.commit()
    db.refresh(new_interaction)
    return new_interaction

def get_interactions_by_customer(db: Session, customer_id: int):
    return db.query(Interaction).filter(Interaction.customer_id == customer_id).order_by(Interaction.log_date.desc()).all()

# --- Order Operations ---
def get_orders_by_customer(db: Session, customer_id: int):
    return db.query(Order).filter(Order.customer_id == customer_id).order_by(Order.order_date.desc()).all()

def create_order(db: Session, customer_id: int, order_date, product_name, quantity, total_amount, deposit_amount, note):
    new_order = Order(
        customer_id=customer_id,
        order_date=order_date,
        product_name=product_name,
        quantity=quantity,
        total_amount=total_amount,
        deposit_amount=deposit_amount,
        is_ordered=True,
        note=note
    )
    db.add(new_order)
    db.commit()
    db.refresh(new_order)
    return new_order

# --- Dashboard Metrics ---
def get_todays_calls(db: Session):
    today = date.today()
    return db.query(Interaction).filter(Interaction.next_action_date == today).all()

def get_monthly_sales(db: Session):
    current_month = date.today().replace(day=1)
    orders = db.query(Order).filter(Order.order_date >= current_month).all()
    total_sales = sum(o.total_amount for o in orders)
    return total_sales

def get_total_receivables(db: Session):
    orders = db.query(Order).all()
    total_receivable = sum(o.outstanding_amount for o in orders)
    return total_receivable

def get_monthly_sales_trend(db: Session):
    orders = db.query(Order).filter(Order.is_ordered == True).all()
    data = {}
    for o in orders:
        if not o.order_date: continue
        month_key = o.order_date.strftime("%Y-%m")
        data[month_key] = data.get(month_key, 0) + o.total_amount
    sorted_data = sorted(data.items())
    return {"Date": [x[0] for x in sorted_data], "Sales": [x[1] for x in sorted_data]}

def get_top_receivables(db: Session, limit=5):
    customers = db.query(Customer).all()
    debt_list = []
    
    for c in customers:
        debt = sum(o.outstanding_amount for o in c.orders)
        if debt > 0:
            debt_list.append({"Company": c.company_name, "Receivable": debt, "Rep": c.sales_rep})
    debt_list.sort(key=lambda x: x["Receivable"], reverse=True)
    return debt_list[:limit]

def get_sales_by_industry(db: Session):
    results = db.query(Customer.industry, func.sum(Order.total_amount))\
                .join(Order)\
                .filter(Order.is_ordered == True)\
                .group_by(Customer.industry).all()
    data = {"Industry": [], "Sales": []}
    for industry, sales in results:
        industry_name = industry if industry else "Unknown"
        data["Industry"].append(industry_name)
        data["Sales"].append(sales)
    return data

def get_scheduled_interactions(db: Session, filter_type="all"):
    today = date.today()
    query = db.query(Interaction).filter(Interaction.next_action_date != None)
    
    if filter_type == 'today':
        return query.filter(Interaction.next_action_date == today).all()
    elif filter_type == 'upcoming':
        end_date = today + dt.timedelta(days=7)
        return query.filter(Interaction.next_action_date > today, Interaction.next_action_date <= end_date).order_by(Interaction.next_action_date).all()
    elif filter_type == 'overdue':
        return query.filter(Interaction.next_action_date < today).order_by(Interaction.next_action_date).all()
    return []

def process_csv_data(db: Session, df: pd.DataFrame):
    stats = {"new_customers": 0, "new_orders": 0, "errors": 0}
    cols = df.columns.tolist()
    manager_indices = [i for i, c in enumerate(cols) if '담당자' in c]
    
    for _, row in df.iterrows():
        try:
            company = str(row.get('상호명', '')).strip()
            if not company or company == 'nan': continue
                
            sales_rep = ""
            client_name = ""
            if len(manager_indices) >= 1: sales_rep = str(row.iloc[manager_indices[0]]).strip()
            if len(manager_indices) >= 2: client_name = str(row.iloc[manager_indices[1]]).strip()
            if sales_rep == 'nan': sales_rep = ""
            if client_name == 'nan': client_name = ""

            phone = str(row.get('연락처', '')).strip()
            if phone == 'nan': phone = ""
            industry = str(row.get('업종', '')).strip()
            if industry == 'nan': industry = ""
            
            customer = db.query(Customer).filter(Customer.company_name == company).first()
            if not customer:
                customer = Customer(company_name=company, client_name=client_name, phone=phone, industry=industry, sales_rep=sales_rep)
                db.add(customer)
                db.commit()
                db.refresh(customer)
                stats['new_customers'] += 1
            
            import re
            def clean_number(val):
                val_str = str(val)
                if not val_str or val_str.lower() == 'nan': return 0
                val_str = val_str.replace(',', '')
                matches = re.findall(r'-?\d+\.?\d*', val_str)
                if not matches: return 0
                return int(sum(float(m) for m in matches))
            
            total_amt = clean_number(row.get('총가격', 0))
            deposit_amt = clean_number(row.get('입금액', 0))
            qty = clean_number(row.get('수량', 0))
            prod_name = str(row.get('상품명', ''))
            if prod_name == 'nan': prod_name = None
            note = str(row.get('비고', ''))
            if note == 'nan': note = None
            
            try:
                order_date = pd.to_datetime(str(row.get('날짜', ''))).date()
            except:
                order_date = date.today()

            new_order = Order(customer_id=customer.id, order_date=order_date, product_name=prod_name, quantity=qty, total_amount=total_amt, deposit_amount=deposit_amt, is_ordered=True, note=note)
            db.add(new_order)
            stats['new_orders'] += 1
            
        except Exception:
            stats['errors'] += 1
    db.commit()
    return stats

# --- NEW: PRODUCT & QUOTE UTILS ---

def get_all_products(db: Session):
    return db.query(Product).all()

def create_product(db: Session, name, price, category, desc="", options=None):
    existing = db.query(Product).filter(Product.name == name).first()
    if existing: return None
    
    import json
    options_str = json.dumps(options) if options else "[]"
    
    new_prod = Product(name=name, unit_price=price, category=category, description=desc, options_json=options_str)
    db.add(new_prod)
    db.commit()
    return new_prod

def delete_product(db: Session, name):
    prod = db.query(Product).filter(Product.name == name).first()
    if prod:
        db.delete(prod)
        db.commit()
        return True
    return False

def delete_quote(db: Session, quote_id: int):
    q = db.query(Quote).filter(Quote.id == quote_id).first()
    if q:
        db.delete(q) # Cascade deletes items
        db.commit()
        return True
    return False

def create_quote(db: Session, customer_id, items, valid_date=None, note=""):
    """
    items: list of dicts {'product_name', 'qty', 'price', 'amount', 'options_summary'}
    """
    total = sum(item['amount'] for item in items)
    quote = Quote(
        customer_id=customer_id,
        quote_date=date.today(),
        valid_until=valid_date,
        status="Draft",
        total_amount=total,
        note=note
    )
    db.add(quote)
    db.commit()
    db.refresh(quote)
    
    for item in items:
        q_item = QuoteItem(
            quote_id=quote.id,
            product_name=item['product_name'],
            quantity=item['qty'],
            unit_price=item['price'],
            amount=item['amount'],
            selected_options=item.get('options_summary', "")
        )
        db.add(q_item)
    
    db.commit()
    return quote

def get_quotes_by_customer(db: Session, customer_id: int):
    return db.query(Quote).filter(Quote.customer_id == customer_id).order_by(Quote.quote_date.desc()).all()

def update_quote_status(db: Session, quote_id: int, status: str):
    q = db.query(Quote).filter(Quote.id == quote_id).first()
    if q:
        q.status = status
        db.commit()
        
        # If converted, create an order?
        if status == "Converted":
            # Simplified logic: 1 Quote = 1 Aggregated Order for now
            # To be more precise, we might want one order per item, or a multi-line order system.
            # But the current Order model is single-line basic.
            # We'll create one order "Quote #ID Items"
            create_order(
                db, 
                q.customer_id, 
                date.today(), 
                f"견적 #{q.id} 확정분", 
                1, 
                q.total_amount, 
                0, 
                "견적 변환됨"
            )
        return True
    return False
