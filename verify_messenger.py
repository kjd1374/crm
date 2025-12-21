from database import get_db
from models import Customer, Order, Interaction
import utils
import time
import os

def setup_test_data():
    db = next(get_db())
    # 1. Ensure Customer exists
    cust = db.query(Customer).filter(Customer.client_name == "홍길동").first()
    if not cust:
        print("Creating test customer '홍길동'...")
        utils.create_customer(db, {
            "company_name": "테스트상사",
            "client_name": "홍길동",
            "phone": "010-1234-5678",
            "industry": "IT",
            "sales_rep": "Test"
        })
        db.commit()
    else:
        print("Test customer '홍길동' already exists.")
    
    # 2. Clear old test orders/interactions for clean check
    # (Optional, skipping to avoid side effects on real data, just checking count)
    db.close()

def append_log_message():
    log_file = "messenger_log.txt"
    
    # Append a "Order" message
    msg = "\n[2025-12-21 오후 3:05] 홍길동\n사과 500개 발주 부탁드립니다.\n"
    
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(msg)
    print(f"Appended to {log_file}")

def verify_result():
    print("Waiting for listener to process...")
    time.sleep(3) # Wait for polling
    
    db = next(get_db())
    # Check for recent order
    cust = db.query(Customer).filter(Customer.client_name == "홍길동").first()
    if cust:
        # Get latest order
        last_order = db.query(Order).filter(Order.customer_id == cust.id).order_by(Order.id.desc()).first()
        if last_order and "메신저" in (last_order.note or ""):
            print(f"SUCCESS: Found Order #{last_order.id} - Qty: {last_order.quantity}")
        else:
            print("FAILURE: No order found from messenger.")
    else:
        print("FAILURE: Customer not found.")
    db.close()

if __name__ == "__main__":
    setup_test_data()
    append_log_message()
    verify_result()
