import os
import json
import datetime
import re
from sqlalchemy.orm import Session
from database import get_db
import utils
from models import Customer

# State file to track read positions
STATE_FILE = "batch_state.json"

# Log directories (User provided)
BASE_DIR = r"C:\Users\rusil\Documents\하이웍스 채팅저장"
CHINA_ROOM = r"(중국1) 영업팀- 주문제작 영업방"
KOREA_ROOM = r"(한국2) 영업팀-국내 주문제작 관해 남기는방"

def get_todays_filepaths():
    today_str = datetime.date.today().strftime("%Y-%m-%d") + ".txt"
    return {
        "CHINA": os.path.join(BASE_DIR, CHINA_ROOM, today_str),
        "KOREA": os.path.join(BASE_DIR, KOREA_ROOM, today_str)
    }

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def read_new_content(filepath, state_key, current_state):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return ""
    
    last_pos = current_state.get(state_key, {}).get("last_pos", 0)
    
    # If file is smaller than last_pos, it might have been reset/rotated
    current_size = os.path.getsize(filepath)
    if current_size < last_pos:
        last_pos = 0
        
    content = ""
    try:
        with open(filepath, "r", encoding="utf-8", errors='ignore') as f:
            f.seek(last_pos)
            content = f.read()
            new_pos = f.tell()
            
        # Update state immediately (or after processing)
        if state_key not in current_state:
            current_state[state_key] = {}
        current_state[state_key]["last_pos"] = new_pos
        current_state[state_key]["last_updated"] = str(datetime.datetime.now())
        
        return content
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
        return ""

def process_china_log(db: Session, text):
    """
    China Room Rules:
    - Keywords: 단가, 가격 -> [단가 변동] (Interaction)
    - Keywords: 제작기간, 일정 -> [납기 확인] (Interaction)
    """
    lines = text.splitlines()
    header_pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) (오전|오후) (\d{1,2}:\d{2})\] (.*)")
    
    current_sender = "Unknown"
    current_date = datetime.date.today()
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        match = header_pattern.match(line)
        if match:
            # Update contexts
            date_str, ampm, time_str, sender = match.groups()
            current_sender = sender
            # Simple date parse (or assume today)
            try:
                current_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except: pass
            continue
            
        # Analyze Content
        if any(k in line for k in ["단가", "가격"]):
            print(f"[CHINA] Price Logic: {line}")
            # Log as Interaction
            utils.add_interaction(
                db, 
                get_or_create_guest(db, current_sender).id, 
                f"[단가변동] {line}", 
                None, 
                "확인필요", 
                log_date=current_date
            )
            
        elif any(k in line for k in ["제작기간", "일정"]):
             print(f"[CHINA] Schedule Logic: {line}")
             utils.add_interaction(
                db, 
                get_or_create_guest(db, current_sender).id, 
                f"[납기확인] {line}", 
                None, 
                "진행중", 
                log_date=current_date
            )

def process_korea_log(db: Session, text):
    """
    Korea Room Rules:
    - Keywords: 입금, 카드 -> [입금 확인] (Interaction)
    - Keywords: 발주서, 기업, 업체 -> [발주처 확인] (Order)
    """
    lines = text.splitlines()
    header_pattern = re.compile(r"^\[(\d{4}-\d{2}-\d{2}) (오전|오후) (\d{1,2}:\d{2})\] (.*)")
    
    current_sender = "Unknown"
    current_date = datetime.date.today()
    
    for line in lines:
        line = line.strip()
        if not line: continue
        
        match = header_pattern.match(line)
        if match:
            date_str, ampm, time_str, sender = match.groups()
            current_sender = sender
            try:
                current_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
            except: pass
            continue

        # Logic
        if any(k in line for k in ["입금", "카드", "송금"]):
            print(f"[KOREA] Payment Logic: {line}")
            utils.add_interaction(
                db, 
                get_or_create_guest(db, current_sender).id, 
                f"[입금확인] {line}", 
                None, 
                "완료", 
                log_date=current_date
            )
            
        if "발주서" in line or "견적서" in line:
            # Enhanced Logic: Extract Company/Subject
            # Patterns to try
            company_name = "미상"
            cleaned_line = line.replace("  ", " ").strip()
            
            # Pattern 1: "대표님 [Company] 발주서..."
            match1 = re.search(r'대표님\s+(.*?)\s+(?:발주서|견적서)', cleaned_line)
            # Pattern 2: "[Company] 발주서입니다"
            match2 = re.search(r'(.*?)\s+(?:발주서|견적서)입니다', cleaned_line)
            
            if match1:
                company_name = match1.group(1).strip()
            elif match2:
                # Remove common prefixes if match is too long or contains "대표님"
                raw = match2.group(1).strip()
                if "대표님" in raw:
                    raw = raw.replace("대표님", "").strip()
                # Remove "," or punctuation at start
                company_name = raw.strip(",. ")
            else:
                # Fallback: Just use words before keywords
                match3 = re.search(r'(\S+)\s+(?:발주서|견적서)', cleaned_line)
                if match3:
                     company_name = match3.group(1)

            # Exclusion: If name is too trivial (e.g. "네", "이번") skip or mark generic
            if len(company_name) < 2 or company_name in ["네", "네,", "이번", "혹시", "미상"]:
                print(f"[KOREA] Order Form Logic IGNORED: {line} -> {company_name}")
                continue
            
            # Filter matches only if "발주서" is clearly the main topic
            # (Already checked "발주서" in line)
            
            # Determine Label
            doc_type = "발주서"
            if "견적서" in line:
                doc_type = "견적서"
            
            label = f"[{doc_type} 접수]" # e.g. [견적서 접수] or [발주서 접수]
            
            print(f"[KOREA] Doc Logic ({doc_type}): {line} -> {company_name}")
            
            utils.create_order(
                db, 
                get_or_create_guest(db, current_sender).id, 
                current_date, 
                f"{label} {company_name}", 
                1, 
                0, 0, 
                f"원본: {line}"
            )
            
        elif any(k in line for k in ["기업", "업체"]):
            # Generic Order Logic
            # Filter out confirmations/questions
            if any(n in line for n in ["확인", "네", "감사", "수고", "문의", "?"]):
                continue
                
            print(f"[KOREA] Order Logic: {line}")
            # Try to extract quantity or just save text
            qty = 1
            nums = re.findall(r'\d+', line)
            if nums: qty = int(nums[0])
            
            utils.create_order(
                db, 
                get_or_create_guest(db, current_sender).id, 
                current_date, 
                "국내발주(자동감지)", 
                qty, 
                0, 0, 
                f"원본: {line}"
            )

def get_or_create_guest(db: Session, name):
    # Find existing or create dummy customer
    cust = db.query(Customer).filter((Customer.client_name == name) | (Customer.company_name == name)).first()
    if not cust:
        # Check if we have a generic 'Messenger Guest'
        cust = db.query(Customer).filter(Customer.company_name == f"Unknown-{name}").first()
        if not cust:
             cust = Customer(
                 company_name=name,  # Use sender name as company for now
                 client_name=name,
                 sales_rep="Automated",
                 industry="메신저유입"
             )
             db.add(cust)
             db.commit()
             db.refresh(cust)
    return cust

def main():
    print(f"--- Batch Process Started: {datetime.datetime.now()} ---")
    state = load_state()
    files = get_todays_filepaths()
    db = next(get_db())
    
    # 1. Process China Room
    print(f"Checking China Room: {files['CHINA']}")
    china_text = read_new_content(files['CHINA'], "china_room", state)
    if china_text:
        process_china_log(db, china_text)
    
    # 2. Process Korea Room
    print(f"Checking Korea Room: {files['KOREA']}")
    korea_text = read_new_content(files['KOREA'], "korea_room", state)
    if korea_text:
        process_korea_log(db, korea_text)
        
    save_state(state)
    db.close()
    print("--- Batch Process Completed ---")

if __name__ == "__main__":
    main()
