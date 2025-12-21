from database import get_db
from models import Order
import datetime

db = next(get_db())

print("--- LAST 20 ORDERS ---")
orders = db.query(Order).order_by(Order.id.desc()).limit(20).all()
for o in orders:
    # Print ID, Date str, Sender, Product
    print(f"[{o.id}] {o.order_date} | {o.customer.company_name} | {o.product_name}")

print("\n--- FILTER TEST ---")
cutoff = datetime.date.today() - datetime.timedelta(days=7)
print(f"Cutoff Date: {cutoff}")
filtered = db.query(Order).filter(Order.order_date >= cutoff).order_by(Order.id.desc()).all()
print(f"Filtered Count: {len(filtered)}")
for o in filtered[:10]:
    print(f" -> {o.order_date}: {o.product_name}")

db.close()
