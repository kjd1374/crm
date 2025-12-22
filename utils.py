from sqlalchemy.orm import Session
from sqlalchemy import func
from models import Customer, Order, Interaction, Product, Quote, QuoteItem
from datetime import datetime, date
import pandas as pd

# --- Customer Operations ---
def get_all_customers(db: Session):
    return db.query(Customer).all()

def get_customer_by_id(db: Session, customer_id: int):
    return db.query(Customer).filter(Customer.id == customer_id).first()

def create_customer(db: Session, customer_data: dict):
    # Check if exists
    existing = db.query(Customer).filter(Customer.company_name == customer_data['company_name']).first()
    if existing:
        return existing
    
    new_customer = Customer(**customer_data)
    db.add(new_customer)
    db.commit()
    db.refresh(new_customer)
    return new_customer

def update_interaction_status(db: Session, interaction_id: int, new_status: str):
    """Update status and clear next_action_date (mark as done)"""
    interaction = db.query(Interaction).filter(Interaction.id == interaction_id).first()
    if interaction:
        interaction.status = new_status
        interaction.next_action_date = None # Remove from schedule
        db.commit()
        return True
    return False


# --- MESSENGER RULES ---
MESSENGER_RULES = [
    # 1. 🚨 발주 (Order) - Strict
    {"type": "ORDER", "keywords": ["발주서", "발주서입니다", "주문서"], "label": "🚨 발주"},
    # 2. 💰 입금 (Payment) - Strict
    {"type": "PAYMENT", "keywords": ["입금액", "입금액입니다", "카드결제", "송금", "이체"], "label": "💰 입금"},
]

def parse_messenger_logs(text):
    """
    Parses raw messenger text into structure data for tracking.
    Returns: List of dicts 
    """
    import re
    lines = text.splitlines()
    header_pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) (오전|오후) (\d{1,2}:\d{2})\] (.*)")
    
    parsed_msgs = []
    current_msg = None
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        match = header_pattern.match(line)
        if match:
            # Save previous
            if current_msg:
                parsed_msgs.append(current_msg)
            
            # Start new
            date_str, ampm, time_str, sender = match.groups()
            hour, minute = map(int, time_str.split(':'))
            if ampm == "오후" and hour != 12: hour += 12
            elif ampm == "오전" and hour == 12: hour = 0
            
            try:
                dt = datetime.strptime(f"{date_str} {hour:02d}:{minute:02d}:00", "%Y-%m-%d %H:%M:%S")
            except:
                dt = datetime.now()
                
            current_msg = {"date": dt, "sender": sender.strip(), "text": "", "type": "ETC", "value": 0, "extra": ""}
        else:
            if current_msg:
                current_msg["text"] += "\n" + line
    
    if current_msg:
        parsed_msgs.append(current_msg)
        
    # Analyze Types & Values
    results = []
    for msg in parsed_msgs:
        txt = msg["text"].strip()
        msg["text"] = txt
        
        # Categorize (Strict)
        msg_type = None
        for rule in MESSENGER_RULES:
            if any(k in txt for k in rule["keywords"]):
                msg_type = rule["type"]
                break
        
        # ⚠️ Strict Filter for Manual Mode: Skip if no rule matched
        if not msg_type:
            continue
        
        msg["type"] = msg_type
        # Add label
        msg["type_label"] = next((r["label"] for r in MESSENGER_RULES if r["type"] == msg_type), "기타")
        
        # Logic for Values (Quantity or Amount)
        import re
        
        # 1. 🚨 Order
        if msg_type == "ORDER":
            msg["value"] = 1 # Default qty 1 if not specified
            # Try to find quantity if explicitly mentioned like "100개"
            qty_match = re.search(r'(\d+)\s*(?:개|박스|box|ea)', txt, re.IGNORECASE)
            if qty_match:
                msg["value"] = int(qty_match.group(1))

        # 2. 💰 Payment
        elif msg_type == "PAYMENT":
            msg["value"] = 0
            # Remove date-like strings to avoid confusion (2024-...)
            clean_txt = re.sub(r'\d{4}-\d{2}-\d{2}', '', txt)
            clean_txt = clean_txt.replace(',', '')
            
            # Simple approach: Find largest number in the message
            all_nums = re.findall(r'\d+', clean_txt)
            candidates = []
            for n in all_nums:
                try:
                    val = int(n)
                    if val > 1000: # Ignore small numbers like time or small qtys
                        candidates.append(val)
                except: pass
            
            if candidates:
                msg["value"] = max(candidates)
        
        results.append(msg)
        
    return results

def get_recent_messenger_activity(db: Session, days=7):
    """
    Fetch recent auto-processed messenger logs from DB.
    Returns dict with keys: 'orders', 'payments', 'prices', 'others'
    """
    import datetime
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    
    # 1. Orders (Manual or Batch)
    # Filter by checking if note contains "원본:" or just all recent orders?
    # Let's show all recent orders for safety
    orders = db.query(Order).filter(Order.order_date >= cutoff).order_by(Order.id.desc()).all()
    
    # 2. Interactions (Payment, Price, Schedule)
    # Filter by specific tags we added in batch_processor
    interactions = db.query(Interaction).filter(Interaction.log_date >= cutoff).order_by(Interaction.id.desc()).all()
    
    activity = {
        "orders": [],
        "payments": [],
        "prices": [],
        "others": []
    }
    
    # Process Orders
    for o in orders:
        activity['orders'].append({
            "sender": o.customer.company_name,
            "sales_rep": o.customer.sales_rep, # Added Sales Rep
            "date": o.order_date,
            "product": o.product_name or '상품미지정', # Explicit product name
            "text": f"{o.product_name or '상품미지정'} {o.quantity}개",
            "value": o.quantity,
            "raw": o.note
        })
        
    # Process Interactions
    for i in interactions:
        txt = i.content
        item = {
            "sender": i.customer.company_name,
            "date": i.log_date,
            "text": txt,
            "value": 0,
            "id": i.id  # Added ID for context lookup
        }
        
        if "[입금확인]" in txt:
            activity['payments'].append(item)
        elif "[단가변동]" in txt:
            activity['prices'].append(item)
        elif "[납기확인]" in txt:
            activity['prices'].append(item) # Group schedule with price/notices
        elif "[문의]" in txt:
             activity['others'].append(item)
             
    return activity

def get_interaction_context(db: Session, interaction_id: int, window=5, limit_to_sender=None):
    """
    Finds surrounding messages. Increased window size for better detection.
    Prioritizes backward search for amounts.
    If limit_to_sender is provided, only includes messages from that sender (company_name).
    """
    # Search window [id-window, id+1]
    min_id = max(1, interaction_id - window)
    max_id = interaction_id + 1 
    
    query = db.query(Interaction).filter(
        Interaction.id >= min_id, 
        Interaction.id <= max_id
    )
    
    if limit_to_sender:
        query = query.join(Interaction.customer).filter(Customer.company_name == limit_to_sender)
        
    neighbors = query.order_by(Interaction.id).all()
    
    # Format: [content] || ...
    context_text = " || ".join([f"[{n.id}] {n.content}" for n in neighbors])
    return context_text
    
    # Format: [Date Time] Content
    context_text = " || ".join([f"[{n.id}] {n.content}" for n in neighbors])
    return context_text


def reset_database(db: Session):
    """Delete all data from all tables"""
    try:
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
def add_interaction(db: Session, customer_id: int, content: str, next_action_date: date, status: str, log_date: date = None):
    if log_date is None:
        log_date = date.today()
        
    new_interaction = Interaction(
        customer_id=customer_id,
        content=content,
        next_action_date=next_action_date,
        status=status,
        log_date=log_date
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
        is_ordered=True, # Manual entry implies it's an order
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
    # This is a simplified version. For exact "This Month", we need date filtering.
    # Assuming user wants total sales for now or simple "current month" logic.
    current_month = date.today().replace(day=1)
    # Filter orders >= current_month
    orders = db.query(Order).filter(Order.order_date >= current_month).all()
    total_sales = sum(o.total_amount for o in orders)
    return total_sales

def get_total_receivables(db: Session):
    # Total Amount - Total Deposit
    orders = db.query(Order).all()
    total_receivable = sum(o.outstanding_amount for o in orders)
    return total_receivable

def get_monthly_sales_trend(db: Session):
    """
    Returns a dataframe-like list for sales trend.
    Group by Month.
    """
    # SQLite has limited date functions, so fetching all orders and processing in python is safer for small scale.
    # For large scale, use SQL group by.
    orders = db.query(Order).filter(Order.is_ordered == True).all()
    
    data = {}
    for o in orders:
        if not o.order_date: continue
        month_key = o.order_date.strftime("%Y-%m")
        data[month_key] = data.get(month_key, 0) + o.total_amount
        
    # Sort by date
    sorted_data = sorted(data.items())
    return {"Date": [x[0] for x in sorted_data], "Sales": [x[1] for x in sorted_data]}

def get_top_receivables(db: Session, limit=5):
    """
    Returns top N customers with highest outstanding debt.
    """
    customers = db.query(Customer).all()
    debt_list = []
    
    for c in customers:
        debt = sum(o.outstanding_amount for o in c.orders)
        if debt > 0:
            debt_list.append({"Company": c.company_name, "Receivable": debt, "Rep": c.sales_rep})
            
    # Sort desc
    debt_list.sort(key=lambda x: x["Receivable"], reverse=True)
    return debt_list[:limit]

def get_sales_by_industry(db: Session):
    """
    Returns sales grouped by customer industry.
    """
    # Join Order and Customer, group by Industry
    results = db.query(Customer.industry, func.sum(Order.total_amount))\
                .join(Order)\
                .filter(Order.is_ordered == True)\
                .group_by(Customer.industry).all()
    
    # Clean up results (None industry -> "Unknown")
    data = {"Industry": [], "Sales": []}
    for industry, sales in results:
        industry_name = industry if industry else "Unknown"
        data["Industry"].append(industry_name)
        data["Sales"].append(sales)
        
    return data

def get_scheduled_interactions(db: Session, filter_type="all"):
    """
    Fetch interactions based on filter:
    - 'today': Next action date is today
    - 'upcoming': Next action date is within next 7 days (inclusive)
    - 'overdue': Next action date is before today
    """
    today = date.today()
    query = db.query(Interaction).filter(Interaction.next_action_date != None)
    
    if filter_type == 'today':
        return query.filter(Interaction.next_action_date == today).all()
    elif filter_type == 'upcoming':
        # Need datetime for range comparison if not using between with dates directly
        # simplistic approach:
        import datetime
        end_date = today + datetime.timedelta(days=7)
        return query.filter(Interaction.next_action_date > today, Interaction.next_action_date <= end_date).order_by(Interaction.next_action_date).all()
    elif filter_type == 'overdue':
        return query.filter(Interaction.next_action_date < today).order_by(Interaction.next_action_date).all()
    
    return []

def process_csv_data(db: Session, df: pd.DataFrame):
    """
    Process uploaded CSV dataframe and import to DB.
    Handles duplicate '담당자' columns: 1st=sales_rep, 2nd=client_name
    """
    # 1. Handle duplicate column names
    # Pandas usually renames duplicates to 'Col', 'Col.1' etc.
    # We expect '담당자', '담당자.1' if they are exact duplicates in header.
    
    # Map for renaming to internal model fields
    # Adjust based on exact CSV headers user might have. 
    # Try generic matching just in case.
    
    # We will iterate row by row for safety and complex logic
    
    stats = {"new_customers": 0, "new_orders": 0, "errors": 0}
    
    # Identify columns
    cols = df.columns.tolist()
    
    # Find indices of '담당자'
    manager_indices = [i for i, c in enumerate(cols) if '담당자' in c]
    
    for _, row in df.iterrows():
        try:
            # Extract Customer Data
            company = str(row.get('상호명', '')).strip()
            if not company or company == 'nan':
                continue
                
            # '담당자' Logic
            sales_rep = ""
            client_name = ""
            
            if len(manager_indices) >= 1:
                sales_rep = str(row.iloc[manager_indices[0]]).strip()
            if len(manager_indices) >= 2:
                client_name = str(row.iloc[manager_indices[1]]).strip()
            if sales_rep == 'nan': sales_rep = ""
            if client_name == 'nan': client_name = ""

            phone = str(row.get('연락처', '')).strip()
            if phone == 'nan': phone = ""
            
            industry = str(row.get('업종', '')).strip()
            if industry == 'nan': industry = ""
            
            # Check/Create Customer
            customer = db.query(Customer).filter(Customer.company_name == company).first()
            if not customer:
                customer = Customer(
                    company_name=company,
                    client_name=client_name,
                    phone=phone,
                    industry=industry,
                    sales_rep=sales_rep
                )
                db.add(customer)
                db.commit()
                db.refresh(customer)
                stats['new_customers'] += 1
            
            # Extract Order Data
            import re
            def clean_number(val):
                # Extract all numbers from string (handling integers and floats)
                val_str = str(val)
                if not val_str or val_str.lower() == 'nan': return 0
                
                # Find all numbers (e.g. "1,000" -> "1000", "500/600" -> ["500", "600"])
                # Remove commas first
                val_str = val_str.replace(',', '')
                # Find digits (allowing for decimals)
                matches = re.findall(r'-?\d+\.?\d*', val_str)
                
                if not matches: return 0
                
                # Strategy: Sum all found numbers (assuming "500/500" means two items worth 500 each)
                # This is a heuristic for messy data.
                total = sum(float(m) for m in matches)
                return int(total)
            
            total_amt = clean_number(row.get('총가격', 0))
            deposit_amt = clean_number(row.get('입금액', 0))
            qty = clean_number(row.get('수량', 0))
            
            prod_name = str(row.get('상품명', ''))
            if prod_name == 'nan': prod_name = None
            
            note = str(row.get('비고', ''))
            if note == 'nan': note = None
            
            order_date_str = str(row.get('날짜', ''))
            try:
                # Try parsing date 
                # Pandas to_datetime is smart but might fail on really weird stuff
                order_date = pd.to_datetime(order_date_str).date()
            except:
                order_date = date.today()

            # Create Order
            new_order = Order(
                customer_id=customer.id,
                order_date=order_date,
                product_name=prod_name,
                quantity=qty,
                total_amount=total_amt,
                deposit_amount=deposit_amt,
                is_ordered=True,
                note=note
            )
            db.add(new_order)
            stats['new_orders'] += 1
            
        except Exception as e:
            # print(f"Error processing row: {e}") # Reduce noise
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

def delete_product(db: Session, product_id: int):
    prod = db.query(Product).filter(Product.id == product_id).first()
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
