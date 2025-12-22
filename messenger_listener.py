import time
import re
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from datetime import datetime
from database import get_db
from models import Customer, Order, Interaction
import utils

# Configuration
WATCH_FILE = "messenger_log.txt"
POLL_INTERVAL = 1

class MessengerHandler(FileSystemEventHandler):
    def __init__(self, filename):
        self.filename = filename
        self.last_pos = 0
        # Try to start at the end of file to avoid re-processing old logs on restart
        if os.path.exists(filename):
            self.last_pos = os.path.getsize(filename)
        
        # Regex for Korean KakaoTalk/Messenger style: [YYYY-MM-DD 오후 2:44] 이름
        self.header_pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) (오전|오후) (\d{1,2}:\d{2})\] (.*)")

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(self.filename):
            self.process_new_lines()

    def process_new_lines(self):
        if not os.path.exists(self.filename):
            return

        try:
            # Try UTF-8 first, then CP949 (common on Windows)
            encodings = ['utf-8', 'cp949']
            content = ""
            current_encoding = 'utf-8'
            
            for enc in encodings:
                try:
                    with open(self.filename, 'r', encoding=enc) as f:
                        f.seek(self.last_pos)
                        content = f.read()
                        self.last_pos = f.tell() # Update pos only if read succeeds
                        current_encoding = enc
                        break
                except UnicodeDecodeError:
                    continue
            
            if content:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Detected change ({len(content)} chars, {current_encoding}). Parsing...")
                self.parse_and_act(content)
                
        except Exception as e:
            print(f"Error reading file: {e}")

    def parse_and_act(self, content):
        lines = content.splitlines()
        print(f"DEBUG: Processing {len(lines)} new lines...") # Debug print
        
        current_msg = {"date": None, "sender": None, "text": ""}
        
        for line in lines:
            line = line.strip()
            if not line: continue
            
            match = self.header_pattern.match(line)
            if match:
                print(f"DEBUG: Header matched -> {line[:30]}...") # Debug print
                # Process previous message
                if current_msg["sender"]:
                    self.trigger_crm_action(current_msg)
                
                # Start new message
                date_str, ampm, time_str, sender = match.groups()
                
                # ... (Time parsing logic) ...
                hour, minute = map(int, time_str.split(':'))
                if ampm == "오후" and hour != 12: hour += 12
                elif ampm == "오전" and hour == 12: hour = 0
                
                try:
                    dt = datetime.strptime(f"{date_str} {hour:02d}:{minute:02d}:00", "%Y-%m-%d %H:%M:%S")
                except:
                    dt = datetime.now()

                current_msg = {"date": dt, "sender": sender.strip(), "text": ""}
            else:
                # Continuation
                if current_msg["sender"]:
                    current_msg["text"] += "\n" + line
                else:
                     print(f"DEBUG: Line ignored (No header yet): {line[:20]}...")
        
        # Process last message
        if current_msg["sender"]:
            self.trigger_crm_action(current_msg)

    def trigger_crm_action(self, msg):
        sender = msg['sender']
        text = msg['text'].strip()
        timestamp = msg['date']
        
        print(f"New Message from {sender}: {text[:30]}...")
        
        db = next(get_db())
        try:
            # 1. Identify Customer
            customer = db.query(Customer).filter(
                (Customer.client_name == sender) | (Customer.company_name == sender)
            ).first()
            
            if not customer:
                print(f" -> Unknown customer: {sender} (Skip)")
                return

            # 2. Analyze & Execute Action
            action_type = analyze_text(text)
            
            if action_type == "ORDER":
                # Extract Quantity (Context: numbers in text)
                import re
                numbers = re.findall(r'\d+', text)
                qty = int(numbers[0]) if numbers else 1
                
                # Create Order
                utils.create_order(
                    db, 
                    customer.id, 
                    timestamp.date(), 
                    "메신저 발주품", # Product Name (Generic)
                    qty, 
                    0, 
                    0, 
                    f"원본: {text}"
                )
                print(f" -> [ACTION] Created Order (Qty: {qty})")

            elif action_type == "INQUIRY":
                status = "접촉중"
                utils.add_interaction(
                    db,
                    customer.id,
                    f"[메신저 문의] {text}",
                    None,
                    status,
                    log_date=timestamp.date()
                )
                print(f" -> [ACTION] Logged Inquiry")

            elif action_type == "COMPLETE":
                # Update latest interaction
                last_interaction = db.query(Interaction).filter(Interaction.customer_id == customer.id).order_by(Interaction.id.desc()).first()
                if last_interaction:
                    last_interaction.status = "완료"
                    db.commit()
                    print(f" -> [ACTION] Updated Status to Complete")
            else:
                print(" -> No actionable keywords found.")
            
        except Exception as e:
            print(f"Error acting on message: {e}")
        finally:
            db.close()

# --- CONFIGURATION & RULES ---
# 여기에 규칙을 정의합니다. (규칙 추가/수정이 쉽도록 분리함)
RULES = [
    {
        "type": "ORDER",
        "keywords": ["발주", "주문"],
        "description": "상품 주문으로 분류"
    },
    {
        "type": "INQUIRY",
        "keywords": ["문의", "?", "가능할까요", "언제"],
        "description": "일반 문의로 분류"
    },
    {
        "type": "COMPLETE",
        "keywords": ["완료", "감사합니다", "확정"],
        "description": "상담 완료 처리"
    }
]

def analyze_text(text):
    """
    텍스트를 분석하여 가장 적합한 규칙을 찾습니다.
    (앞뒤 문맥을 고려한 로직 확장이 가능한 곳)
    """
    text_lower = text.lower() # Case insensitive
    
    # 1. Check for Order (Priority 1)
    if any(k in text for k in RULES[0]['keywords']):
        return "ORDER"
        
    # 2. Check for Complete (Priority 2)
    if any(k in text for k in RULES[2]['keywords']):
        return "COMPLETE"
        
    # 3. Check for Inquiry (Priority 3)
    if any(k in text for k in RULES[1]['keywords']):
        return "INQUIRY"
        
    return None



if __name__ == "__main__":
    # Ensure file exists
    if not os.path.exists(WATCH_FILE):
        with open(WATCH_FILE, 'w', encoding='utf-8') as f:
            f.write("")
            
    event_handler = MessengerHandler(WATCH_FILE)
    observer = Observer()
    observer.schedule(event_handler, path=".", recursive=False)
    observer.start()

    abs_path = os.path.abspath(WATCH_FILE)
    print(f"Monitoring Target: {abs_path}")
    print(f"Waiting for new messages... (Ctrl+C to stop)")
    try:
        while True:
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
