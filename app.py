import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
from database import get_db, init_db
from models import Customer, Order, Interaction, Quote
import utils

# Page Config
st.set_page_config(page_title="간편 CRM", layout="wide", page_icon="💼")

# Initialize DB
init_db()

# Function to get DB session
def get_session():
    return next(get_db())

# --- Sidebar Navigation ---
st.sidebar.title("💼 CRM 시스템")
page = st.sidebar.radio("메뉴 이동", ["대시보드", "고객 관리", "견적 관리", "데이터 입력", "메신저 입력", "AI CRM"], index=0)

st.sidebar.divider()
# Reset Data Feature
with st.sidebar.expander("⚠️ 데이터 초기화"):
    st.warning("모든 데이터가 삭제됩니다!")
    if st.button("전체 초기화 실행", type="primary"):
        db = get_session()
        if utils.reset_database(db):
            st.success("초기화 완료!")
            st.rerun()
        else:
            st.error("초기화 실패")
        db.close()

# Admin Tools (Hidden/Advanced)
with st.sidebar.expander("🛠️ 관리자 도구"):
    st.caption("DB 스키마 변경 등")
    if st.button("DB 마이그레이션 실행"):
        db = get_session()
        logs = utils.run_db_migration(db)
        db.close()
        for log in logs:
            st.text(log)
        if not logs:
            st.info("변경사항 없음 (이미 최신)")
        else:
            st.success("마이그레이션 완료")

# --- PAGE 1: Dashboard ---
if page == "대시보드":
    st.title("📊 대시보드")
    
    db = get_session()

    # --- 🗓️ DASHBOARD CALENDAR (Split View) ---
    import calendar
    from datetime import date, datetime

    # Initialize Session State for Selected Date
    if 'selected_date' not in st.session_state:
        st.session_state['selected_date'] = date.today()

    # Custom CSS
    st.markdown("""
    <style>
    .day-btn-normal {
        font-size: 14px;
        padding: 5px;
    }
    .status-dot {
        font-size: 8px;
        color: #ff4b4b;
    }
    .calendar-container {
        border-right: 1px solid #333;
        padding-right: 20px;
    }
    div[data-testid="stColumn"] button {
        width: 100%;
        height: 55px !important; /* Fixed height for stacked content */
        padding: 2px !important;
        white-space: pre-wrap !important; /* Enable newline stacking */
        line-height: 1.1 !important;
        font-size: 11px !important;
        overflow: hidden !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # Fetch Data
    activity = utils.get_recent_messenger_activity(db, days=60)
    
    # --- GLOBAL FILTER (User Request) ---
    # We rely on save-time filtering now. 
    # Showing all saved Orders and Payments.
    pass

    # Layout: Split View (Narrow Calendar, Wide Details)
    cal_col, detail_col = st.columns([1, 2], gap="large")

    # --- LEFT: CALENDAR ---
    with cal_col:
        now = date.today()
        # Ensure session state defaults
        if 'cal_sel_y' not in st.session_state: st.session_state['cal_sel_y'] = now.year
        if 'cal_sel_m' not in st.session_state: st.session_state['cal_sel_m'] = now.month
        
        # Get values for Header
        current_y = st.session_state['cal_sel_y']
        current_m = st.session_state['cal_sel_m']
        
        # Header Row: Title and Selectors INLINE
        # [Title (Year.Month)] [Selector Year] [Selector Month]
        h_c1, h_c2, h_c3 = st.columns([2, 1.2, 1], gap="small")
        with h_c1:
            st.markdown(f"<h3 style='margin:0; padding-top:5px;'>{current_y}.{current_m}</h3>", unsafe_allow_html=True)
        with h_c2:
            # User Request: Year cut off -> Use 'YY format (e.g. '25)
            sel_year = st.selectbox("", range(now.year-1, now.year+3), index=1, key="cal_sel_y", format_func=lambda x: f"'{str(x)[2:]}", label_visibility="collapsed")
        with h_c3:
            sel_month = st.selectbox("", range(1, 13), index=now.month-1, format_func=lambda x: f"{x}월", key="cal_sel_m", label_visibility="collapsed")

        st.write("") # Spacer

        # Calendar Grid
        calendar.setfirstweekday(calendar.SUNDAY)
        cal = calendar.monthcalendar(sel_year, sel_month)
        
        # Week Header
        week_cols = st.columns(7)
        weekdays = ["일", "월", "화", "수", "목", "금", "토"]
        for i, day_name in enumerate(weekdays):
            color = "#ff6b6b" if i == 0 else "#4dabf7" if i == 6 else "#ffffff"
            week_cols[i].markdown(f"<div style='text-align: center; color: {color}; font-weight: bold; font-size: 10px;'>{day_name}</div>", unsafe_allow_html=True)

        for week in cal:
            cols = st.columns(7)
            for i, day in enumerate(week):
                with cols[i]:
                    if day == 0:
                        st.write("")
                    else:
                        current_d = date(sel_year, sel_month, day)
                        
                        # Check events (Global filtered)
                        has_orders = any(o['date'] == current_d for o in activity['orders'])
                        has_payments = any(p['date'] == current_d for p in activity['payments'])
                        
                        # Label Logic: Date Top, Icon Bottom
                        # Use narrower layout logic
                        label = f"{day}"
                        if has_orders or has_payments:
                            label += "\n"
                            if has_orders: label += "📦"
                            if has_payments: label += "💰"
                        
                        # Highlighting
                        is_selected = (st.session_state['selected_date'] == current_d)
                        btn_type = "primary" if is_selected else "secondary"
                        
                        if st.button(label, key=f"d_{day}", type=btn_type, use_container_width=True):
                            st.session_state['selected_date'] = current_d
                            st.rerun()

    # --- RIGHT: DETAILS ---
    with detail_col:
        sel_d = st.session_state['selected_date']
        st.markdown(f"### 🗓️ {sel_d.strftime('%Y-%m-%d')} 상세 내역")
        
        # Filter (Using Global Lists)
        d_orders = [o for o in activity['orders'] if o['date'] == sel_d]
        d_payments = [p for p in activity['payments'] if p['date'] == sel_d]
        
        if not d_orders and not d_payments:
            st.info("기록된 내역이 없습니다.")
        else:
            # User Request: Scrollable Container (Limit visible length)
            with st.container(height=500, border=False):
                # Orders

                if d_orders:
                    st.caption(f"🚨 발주 ({len(d_orders)})")
                    for o in d_orders:
                        # o['sales_rep'] added in utils
                        sales_rep = o.get('sales_rep', '')
                        if sales_rep == "Automated":
                            sales_rep = ""
                        
                        customer = o['sender']
                        product = o.get('product', '제품미상')
                        
                        # Format: if sales_rep exists, "Rep - Customer". Else just "Customer"
                        if sales_rep:
                            summary_txt = f"📦 {sales_rep} - {customer} - {product}"
                        else:
                            summary_txt = f"📦 {customer} - {product}"
                        
                        # Expander: Show ONLY Raw Text
                        with st.expander(summary_txt):
                            st.text(o['raw'])

                if d_orders and d_payments:
                    st.divider()
                    
                # Payments
                if d_payments:
                    # 1. Pre-process to extract amounts and Deduplicate
                    unique_payments = []
                    last_processed = None # {amount: int, time: datetime, sender: str}
                    
                    import re
                    from datetime import datetime, timedelta

                    d_payments_sorted = sorted(d_payments, key=lambda x: x.get('date', datetime.min))

                    for p in d_payments_sorted:
                         # Extract Amount Logic (Same as before)
                        final_amt = "금액 미상"
                        final_amt_val = 0
                        context_snippet = ""
                        
                        # 1. Direct Regex
                        direct_match = re.search(r'([\d,]+)(원|만원)', p['text'])
                        amount_found = False
                        
                        if direct_match:
                            val_str = direct_match.group(1).replace(",", "")
                            try:
                                val_int = int(val_str)
                                if val_int > 0:
                                    final_amt = direct_match.group(0)
                                    final_amt_val = val_int
                                    amount_found = True
                            except: pass
                        
                        if not amount_found and 'id' in p:
                            # 2. Context Search
                            context_text = utils.get_interaction_context(db, p['id'], window=5, limit_to_sender=p['sender'])
                            all_matches = re.findall(r'([\d,]+)(원|만원)', context_text)
                            
                            valid_candidates = []
                            for m in all_matches:
                                try:
                                    val = int(m[0].replace(",", ""))
                                    if val > 0:
                                        valid_candidates.append((val, f"{m[0]}{m[1]}"))
                                except: pass
                            
                            if valid_candidates:
                                # Pick last one
                                final_amt_val, final_amt = valid_candidates[-1]
                                context_snippet = f"문맥 감지: {final_amt}"
                        
                        # DEDUPLICATION LOGIC
                        # If same Amount AND Same Sender AND Time Diff < 60s
                        is_duplicate = False
                        p_time = p.get('date') # Assuming 'date' is a datetime object from utils
                        # Wait, utils.py sets 'date': i.log_date. database.py says log_date allows null? 
                        # Assuming it's valid datetime.
                        
                        if last_processed and final_amt_val > 0:
                            prev_amt = last_processed['amount']
                            prev_time = last_processed['time']
                            prev_sender = last_processed['sender']
                            
                            if (prev_amt == final_amt_val and 
                                prev_sender == p['sender'] and 
                                p_time and prev_time):
                                delta = p_time - prev_time
                                if abs(delta.total_seconds()) < 60: # Within 60 seconds
                                    is_duplicate = True
                        
                        if not is_duplicate:
                            # Add to unique list
                            p_data = {
                                'data': p,
                                'amt_str': final_amt,
                                'amt_val': final_amt_val,
                                'snippet': context_snippet
                            }
                            unique_payments.append(p_data)
                            # Update last processed only if valid amount (to chain duplicates)
                            if final_amt_val > 0:
                                last_processed = {
                                    'amount': final_amt_val,
                                    'time': p_time,
                                    'sender': p['sender']
                                }
                    
                    # RENDER
                    st.caption(f"💰 입금 확인 ({len(unique_payments)})")
                    for item in unique_payments:
                        p = item['data']
                        final_amt = item['amt_str']
                        
                        summary_txt = f"💰 {p['sender']}: {final_amt}"
                        
                        with st.expander(summary_txt):
                            st.text(p['text'])
    
    st.divider()
    
    # Metrics
    # col1, col2, col3 ... (Original Code continues)
    col1, col2, col3 = st.columns(3)
    
    monthly_sales = utils.get_monthly_sales(db)
    receivables = utils.get_total_receivables(db)
    todays_calls = utils.get_todays_calls(db)
    
    with col1:
        st.metric("이번 달 매출", f"₩{monthly_sales:,}")
    with col2:
        st.metric("총 미수금", f"₩{receivables:,}", delta_color="inverse")
    with col3:
        st.metric("오늘 연락할 곳", f"{len(todays_calls)} 곳")
        
    st.divider()

    # --- Analysis Section ---
    st.subheader("📈 매출 분석")
    chart_col1, chart_col2 = st.columns(2)
    
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm

    # Font setup for Korean (Cross-platform)
    import platform
    system_name = platform.system()
    
    if system_name == 'Windows':
        plt.rcParams['font.family'] = 'Malgun Gothic'
    elif system_name == 'Darwin': # Mac
        plt.rcParams['font.family'] = 'AppleGothic'
    else: # Linux / Streamlit Cloud
        # Try to find a Korean font, fallback to sans-serif
        # Streamlit Cloud needs 'fonts-nanum' installed via packages.txt
        plt.rcParams['font.family'] = 'NanumGothic'

    # Minus sign support
    plt.rcParams['axes.unicode_minus'] = False
    
    with chart_col1:
        st.write("**월별 매출 추이**")
        trend_data = utils.get_monthly_sales_trend(db)
        if trend_data["Date"]:
            df_trend = pd.DataFrame(trend_data)
            # Matplotlib Chart
            fig, ax = plt.subplots(figsize=(5, 3))
            ax.bar(df_trend["Date"], df_trend["Sales"], color="#4CAF50")
            ax.set_title("Monthly Trend")
            st.pyplot(fig)
        else:
            st.info("데이터가 부족합니다.")

    with chart_col2:
        st.write("**업종별 매출 비중**")
        industry_data = utils.get_sales_by_industry(db)
        if industry_data["Industry"]:
            df_ind = pd.DataFrame(industry_data)
            # Matplotlib Chart
            fig, ax = plt.subplots(figsize=(5, 3))
            ax.bar(df_ind["Industry"], df_ind["Sales"], color="#FF9800")
            ax.set_title("By Industry")
            st.pyplot(fig)
        else:
            st.info("데이터가 부족합니다.")

    st.divider()

    # --- Schedule & Tasks ---
    st.subheader("📅 일정 & 업무")
    
    tab_today, tab_upcoming, tab_overdue, tab_debt = st.tabs(["🔥 오늘 일정", "📆 예정 (7일)", "⚠️ 지연됨", "💰 미수금 Top"])
    
    with tab_today:
        if todays_calls:
            for interaction in todays_calls:
                cust = interaction.customer
                with st.expander(f"📞 {cust.company_name} - {cust.client_name}", expanded=True):
                    st.write(f"**계획:** {interaction.content}")
                    st.caption(f"상태: {interaction.status}")
                    if st.button("✅ 완료 처리", key=f"done_{interaction.id}"):
                        utils.update_interaction_status(db, interaction.id, "완료")
                        st.success("완료 처리되었습니다!")
                        st.rerun()
        else:
            st.success("오늘 예정된 업무가 없습니다! 🎉")

    with tab_upcoming:
        upcoming = utils.get_scheduled_interactions(db, 'upcoming')
        if upcoming:
            for interaction in upcoming:
                 cust = interaction.customer
                 st.info(f"**{interaction.next_action_date}**: {cust.company_name} ({cust.client_name}) - {interaction.content}")
        else:
            st.write("향후 7일간 예정된 업무가 없습니다.")

    with tab_overdue:
        overdue = utils.get_scheduled_interactions(db, 'overdue')
        if overdue:
            for interaction in overdue:
                 cust = interaction.customer
                 st.error(f"**{interaction.next_action_date}**: {cust.company_name} - {interaction.content}")
        else:
            st.write("지연된 업무가 없습니다. 👍")

    with tab_debt:
        top_debtors = utils.get_top_receivables(db)
        if top_debtors:
            for d in top_debtors:
                st.write(f"**{d['Company']}**")
                st.caption(f"₩{d['Receivable']:,} (담당: {d['Rep']})")
                st.progress(min(1.0, d['Receivable']/10000000))
        else:
            st.success("미수금 이슈가 없습니다! 🎉")
    
    db.close()

# --- PAGE 2: Customer Management ---
elif page == "고객 관리":
    st.title("👥 고객 관리")
    
    db = get_session()
    customers = utils.get_all_customers(db)
    
    # Customer Selector
    if customers:
        customer_names = [f"{c.company_name} ({c.client_name})" for c in customers]
        selected_customer_name = st.selectbox("🔍 고객 검색", customer_names)
        
        # Find selected customer
        selected_index = customer_names.index(selected_customer_name)
        customer = customers[selected_index]
        
        st.divider()
        
        # Layout
        col_info, col_main = st.columns([1, 2])
        
        with col_info:
            st.subheader("ℹ️ 기본 정보")
            with st.form("customer_info_form"):
                c_company = st.text_input("상호명", customer.company_name)
                c_client = st.text_input("담당자명", customer.client_name)
                c_phone = st.text_input("연락처", customer.phone)
                c_industry = st.text_input("업종", customer.industry)
                c_rep = st.text_input("영업 담당", customer.sales_rep)
                
                if st.form_submit_button("정보 수정"):
                    customer.company_name = c_company
                    customer.client_name = c_client
                    customer.phone = c_phone
                    customer.industry = c_industry
                    customer.sales_rep = c_rep
                    db.commit()
                    st.success("수정되었습니다!")
                    st.rerun()
            
            st.info(f"등록일: {customer.created_at.strftime('%Y-%m-%d')}")

        with col_main:
             # Tabs for Orders and Interactions
            sub_tab1, sub_tab2, sub_tab3 = st.tabs(["💬 상담 일지", "🛒 주문 내역", "📄 견적 내역"])
            
            with sub_tab1:
                # Add New Log
                st.write("##### ✍️ 상담 기록 추가")
                with st.form("new_log_form"):
                    col_c, col_s = st.columns([3, 1])
                    with col_c:
                         new_log_date = st.date_input("상담 일시", value=date.today())
                         new_content = st.text_area("내용", placeholder="상담 내용을 입력하세요...", height=100)
                    
                    with col_s:
                        st.write("") # Spacer to align with date input if needed, or just let it stack
                        st.write("") 
                        new_next_date = st.date_input("다음 연락일", value=None)
                        new_status = st.selectbox("상태", ["접촉중", "제안단계", "협상중", "계약완료", "보류", "완료"])
                    
                    if st.form_submit_button("기록 저장", use_container_width=True):
                        utils.add_interaction(db, customer.id, new_content, new_next_date, new_status, log_date=new_log_date)
                        st.success("저장되었습니다!")
                        st.rerun()

                st.divider()
                st.write("##### 📜 상담 이력")
                
                logs = utils.get_interactions_by_customer(db, customer.id)
                if logs:
                    for log in logs:
                        with st.chat_message("user", avatar="👤"):
                            st.write(f"**{log.log_date}** | {log.status}")
                            # Show content in expander to save space
                            with st.expander("상담 내용 보기", expanded=False):
                                st.markdown(log.content)
                            
                            if log.next_action_date:
                                st.caption(f"🔜 예정일: {log.next_action_date}")
                else:
                    st.caption("기록된 이력이 없습니다.")

            with sub_tab2:
                orders = utils.get_orders_by_customer(db, customer.id)
                if orders:
                    # Creating a cleaner dataframe for display
                    order_data = [{
                        "날짜": o.order_date,
                        "상품명": o.product_name,
                        "수량": o.quantity,
                        "총금액": o.total_amount,
                        "입금액": o.deposit_amount,
                        "미수금": o.outstanding_amount,
                        "비고": o.note
                    } for o in orders]
                    
                    df_orders = pd.DataFrame(order_data)
                    # Format columns
                    st.dataframe(
                        df_orders,
                        column_config={
                            "날짜": "날짜",
                            "총금액": st.column_config.NumberColumn("총금액", format="₩%d"),
                            "입금액": st.column_config.NumberColumn("입금액", format="₩%d"),
                            "미수금": st.column_config.NumberColumn("미수금", format="₩%d"),
                        },
                        width='stretch',
                        hide_index=True
                    )
                else:
                    st.info("주문 내역이 없습니다.")
        
            with sub_tab3: # Quotes
                quotes = utils.get_quotes_by_customer(db, customer.id)
                # Filter out 'Draft' quotes (User Request: Show only confirmed/sent quotes)
                visible_quotes = [q for q in quotes if q.status != "Draft"]
                
                if visible_quotes:
                    for q in visible_quotes:
                        with st.expander(f"📄 견적 #{q.id} ({q.status}) - ₩{q.total_amount:,}"):
                            st.write(f"**유효기간:** {q.valid_until}")
                            st.write(f"**메모:** {q.note}")
                            # Items
                            st.table(pd.DataFrame([{"상품": i.product_name, "수량": i.quantity, "단가": i.unit_price, "금액": i.amount} for i in q.quote_items]))
                            
                            c1, c2 = st.columns(2)
                            if q.status == "Draft":
                                if c1.button("📩 발송 처리", key=f"send_{q.id}"):
                                    utils.update_quote_status(db, q.id, "Sent")
                                    st.rerun()
                            if q.status == "Sent":
                                if c2.button("✅ 수주 확정 (주문생성)", key=f"win_{q.id}"):
                                    utils.update_quote_status(db, q.id, "Converted")
                                    st.success("주문으로 변환되었습니다!")
                                    st.rerun()
                else:
                    st.info("견적 내역이 없습니다.")

    else:
        st.warning("등록된 고객이 없습니다. '데이터 입력' 메뉴에서 데이터를 추가해주세요.")
    
    db.close()

# --- PAGE 3: Quote Management ---
elif page == "견적 관리":
    st.title("📑 견적 관리")
    
    db = get_session()
    
    tab_new, tab_list, tab_prod = st.tabs(["✨ 견적 작성", "🗂 견적 목록", "🛍 제품 관리"])
    
    # 1. New Quote
    with tab_new:
        st.subheader("새 견적서 작성")
        customers = utils.get_all_customers(db)
        if not customers:
            st.error("고객을 먼저 등록해주세요.")
        else:
            # Step 1: Select Customer
            c_options = {f"{c.company_name} ({c.client_name})": c.id for c in customers}
            sel_c = st.selectbox("고객 선택", list(c_options.keys()))
            sel_c_id = c_options[sel_c]
            
            st.divider()
            
            # Step 2: Add Items
            if 'quote_items' not in st.session_state:
                st.session_state.quote_items = []
                
            # Item Input Form
            with st.container():
                st.markdown("#### 🛒 품목 추가")
                
                products = utils.get_all_products(db)
                prod_names = [p.name for p in products]
                
                is_manual = st.checkbox("직접 입력하기", value=False)
                
                col_p, col_opt, col_q, col_add = st.columns([2.5, 3.5, 0.8, 0.7])
                
                selected_options_summary = ""
                final_amount = 0
                display_unit_price = 0
                
                i_qty = 1
                
                # Manual Input Logic
                if is_manual:
                    with col_p:
                        i_name = st.text_input("품목명")
                    with col_q:
                        i_qty = st.number_input("수량", min_value=1, value=1)
                    with col_opt:
                        i_price = st.number_input("단가", min_value=0, step=1000, value=0)
                        display_unit_price = i_price
                        final_amount = i_price * i_qty

                # DB Product Logic
                else:
                    if prod_names:
                        with col_p:
                            i_name_sel = st.selectbox("품목 선택", prod_names)
                            i_name = i_name_sel
                        
                        sel_prod = next((p for p in products if p.name == i_name_sel), None)
                        
                        # Options Logic
                        import json
                        options_data = None 
                        is_china_mode = False
                        
                        if sel_prod and sel_prod.options_json:
                            try:
                                options_data = json.loads(sel_prod.options_json)
                                if isinstance(options_data, dict) and options_data.get('type') == 'china':
                                    is_china_mode = True
                                elif isinstance(options_data, list):
                                    is_china_mode = False # Domestic List
                            except:
                                options_data = [] # Fallback
                        
                        # --- CHINA MODE CALCULATION ---
                        if is_china_mode:
                            # Load Base Params
                            c_base = options_data.get('c_base', 0)
                            c_prod = options_data.get('c_prod', 0)
                            
                            st.markdown(f"**🇨🇳 [중국소싱] {i_name} 견적**")
                            # 1. Quantity First
                            with col_q:
                                i_qty = st.number_input("수량", min_value=1, value=500)
                            
                            with col_opt:
                                # China Specific Inputs
                                st.caption(f"기본정보: 현지 {c_base} / 제작 {c_prod}")
                                
                                # Packaging
                                st.markdown("###### 📦 포장 & 옵션 (현지화폐)")
                                c_pkg = st.columns(4)
                                opt_d = c_pkg[0].number_input("대지", min_value=0.0, step=0.1)
                                opt_b = c_pkg[1].number_input("박스", min_value=0.0, step=0.1)
                                opt_p = c_pkg[2].number_input("인쇄", min_value=0.0, step=0.1)
                                opt_h = c_pkg[3].number_input("손잡이", min_value=0.0, step=0.1)
                                
                                # Config
                                st.markdown("###### ⚙️ 환경설정")
                                c_conf = st.columns(2)
                                rate = c_conf[0].number_input("환율", value=210.0, step=1.0)
                                logistics = c_conf[1].number_input("물류배율", value=1.7, step=0.1)
                                
                                c_chk = st.columns(2)
                                is_remote = c_chk[0].checkbox("원격조종", value=False)
                                is_sky = c_chk[1].checkbox("스카이 (+1,000)", value=False)
                                
                                # CALCULATION
                                # 1. Base Unit Price (KRW)
                                opt_sum_cny = opt_d + opt_b + opt_p + opt_h
                                base_unit_krw = (c_base + c_prod + opt_sum_cny) * rate * logistics
                                
                                # 2. Sky Adder
                                if is_sky:
                                    base_unit_krw += 1000
                                
                                # 3. Remote Adder (Total Fixed)
                                remote_fixed = 0
                                if is_remote:
                                    remote_fixed = 550000 if i_qty <= 499 else 1000000
                                
                                # 4. Total & Final Unit
                                total_est = (base_unit_krw * i_qty) + remote_fixed
                                unit_est = total_est / i_qty if i_qty > 0 else 0
                                
                                display_unit_price = int(unit_est)
                                final_amount = int(total_est)
                                
                                # Summary String
                                opt_strs = []
                                if opt_d: opt_strs.append(f"대지:{opt_d}")
                                if opt_b: opt_strs.append(f"박스:{opt_b}")
                                if opt_p: opt_strs.append(f"인쇄:{opt_p}")
                                if opt_h: opt_strs.append(f"손잡이:{opt_h}")
                                if is_sky: opt_strs.append("SKY")
                                if is_remote: opt_strs.append("원격")
                                
                                selected_options_summary = f"[China] {', '.join(opt_strs)} / 환율{rate}"
                                
                                st.success(f"개당: ₩{display_unit_price:,} / 총액: ₩{final_amount:,}")

                        # --- DOMESTIC MODE (Legacy) ---
                        else:
                            # Domestic Logic
                            options_list = options_data if isinstance(options_data, list) else []
                            
                            with col_q:
                                i_qty = st.number_input("수량", min_value=1, value=1)
                            
                            base_price = sel_prod.unit_price if sel_prod else 0
                            calc_unit_price = base_price
                            fixed_add_cost = 0 
                            chosen_opts = []
                            
                            with col_opt:
                                if options_list:
                                    st.write(f"기본가: ₩{base_price:,}")
                                    if len(options_list) > 1:
                                        opt_cols_gen = st.columns(len(options_list))
                                    else:
                                        opt_cols_gen = [st.container()]
                                        
                                    for idx, opt_group in enumerate(options_list):
                                        g_name = opt_group.get('name', '옵션')
                                        g_vals = opt_group.get('values', [])
                                        
                                        # Create labels map
                                        val_map = {}
                                        for v in g_vals:
                                            label = v['label']
                                            price = v['price']
                                            th = v.get('threshold_qty', 0)
                                            th_fixed = v.get('threshold_fixed_price', 0)
                                            
                                            if th > 0:
                                               label += f" ({th}개↓ 고정+{th_fixed:,} / ↑ 개당+{price:,})"
                                            else:
                                               if price > 0: label += f" (+{price:,})"
                                            
                                            val_map[label] = v
                                        
                                        with opt_cols_gen[idx]:
                                            sel_val_str = st.selectbox(f"{g_name}", list(val_map.keys()), key=f"opt_{idx}", label_visibility="visible")
                                            sel_val = val_map[sel_val_str]
                                            
                                            # Price Calculation Strategy
                                            th = sel_val.get('threshold_qty', 0)
                                            th_fixed = sel_val.get('threshold_fixed_price', 0)
                                            v_price = sel_val.get('price', 0)
                                            
                                            if th > 0 and i_qty <= th:
                                                # Below threshold: Add Fixed Cost to Total
                                                fixed_add_cost += th_fixed
                                            else:
                                                # Above threshold or no threshold
                                                calc_unit_price += v_price
                                                
                                            chosen_opts.append(f"{g_name}:{sel_val['label']}")
                                    
                                    display_unit_price = calc_unit_price
                                    # Total = (Unit * Qty) + Fixed
                                    final_amount = (calc_unit_price * i_qty) + fixed_add_cost
                                    
                                    st.write(f"**적용 단가: :blue[₩{display_unit_price:,}]**")
                                    if fixed_add_cost > 0:
                                        st.caption(f"➕ 고정비 추가: ₩{fixed_add_cost:,}")
                                    
                                    selected_options_summary = ", ".join(chosen_opts)
                                    
                                else:
                                    st.write(f"단가: ₩{base_price:,}")
                                    display_unit_price = base_price
                                    final_amount = base_price * i_qty
                                    selected_options_summary = ""
                    else:
                        st.info("등록된 제품이 없습니다.")
                        i_name = None
                        i_qty = 1

                with col_add:
                    st.write("") 
                    st.write("") 
                    if st.button("➕ 담기", use_container_width=True):
                        if i_name:
                            st.session_state.quote_items.append({
                                "product_name": i_name,
                                "qty": i_qty,
                                "price": display_unit_price,
                                "amount": final_amount,
                                "options_summary": selected_options_summary
                            })
                        else:
                            st.toast("품목을 선택하세요.")
            
            # Show Items Table
            if st.session_state.quote_items:
                st.write("---")
                
                disp_items = []
                for idx, item in enumerate(st.session_state.quote_items):
                    disp_items.append({
                        "No": idx + 1,
                        "품목명": item['product_name'],
                        "옵션": item['options_summary'],
                        "단가": f"₩{item['price']:,}",
                        "수량": item['qty'],
                        "합계": f"₩{item['amount']:,}"
                    })
                
                st.dataframe(pd.DataFrame(disp_items), use_container_width=True, hide_index=True)
                
                total_est = sum(item['amount'] for item in st.session_state.quote_items)
                st.markdown(f"### 총 합계: :blue[₩{total_est:,}]")
                
                rem_col, save_col = st.columns([1,4])
                if rem_col.button("🗑 목록 비우기"):
                    st.session_state.quote_items = []
                    st.rerun()
                    
                if save_col.button("💾 견적서 저장 (Draft)", type="primary", use_container_width=True):
                    utils.create_quote(db, sel_c_id, st.session_state.quote_items, valid_date=date.today() + timedelta(days=14))
                    st.success("견적서가 저장되었습니다!")
                    st.session_state.quote_items = []
                    st.rerun()

    # 2. Quote List
    with tab_list:
        st.subheader("🗂 전체 견적 목록")
        
        customers = utils.get_all_customers(db)
        if customers:
            for c in customers:
                qs = utils.get_quotes_by_customer(db, c.id)
                for q in qs:
                    with st.expander(f"[{q.quote_date}] {c.company_name} - ₩{q.total_amount:,} ({q.status})"):
                        # Show Items
                        st.table(pd.DataFrame([{"상품": i.product_name, "옵션": i.selected_options, "수량": i.quantity, "금액": i.amount} for i in q.quote_items]))
                        
                        c1, c2, c3 = st.columns([1, 1, 3])
                        if c1.button("🗑 삭제", key=f"del_q_{q.id}"):
                            if utils.delete_quote(db, q.id):
                                st.success("삭제되었습니다.")
                                st.rerun()
                        
                        if c2.button("✏️ 불러오기(수정)", key=f"edit_q_{q.id}"):
                            # Load items into session state and switch tab
                            st.session_state.quote_items = []
                            for i in q.quote_items:
                                st.session_state.quote_items.append({
                                    "product_name": i.product_name,
                                    "qty": i.quantity,
                                    "price": i.unit_price,
                                    "amount": i.amount,
                                    "options_summary": i.selected_options
                                })
                            st.toast("견적 내용을 '견적 작성' 탭으로 불러왔습니다. 수정 후 저장하세요.")
        else:
            st.info("등록된 고객이 없습니다.")

    # 3. Product Management
    with tab_prod:
        st.subheader("🛍 제품 및 옵션 등록")
        
        col_form, col_view = st.columns([1, 1], gap="medium")
        
        with col_form:
            with st.container(border=True):
                st.markdown("#### 신규 제품 등록")
                
                # Sourcing Type Selection
                sourcing_type = st.radio("소싱 구분", ["국내", "중국"], horizontal=True)

                if 'new_prod_opts' not in st.session_state:
                    st.session_state.new_prod_opts = []

                p_name = st.text_input("제품명")
                p_cat = st.text_input("카테고리")
                
                final_p_price = 0
                p_desc_auto = ""
                if sourcing_type == "국내":
                    # Domestic Logic: Standard Price + Option Groups
                    p_price = st.number_input("기본 단가 (KRW)", min_value=0, step=100)
                    final_p_price = p_price
                    p_desc_auto = "국내 소싱 제품"
                    
                    # Option Groups UI (Domestic Only)
                    st.divider()
                    st.markdown("#### 🔧 옵션 구성 (국내 전용)")
                    st.caption("필요한 경우 옵션 그룹을 추가하세요. (예: 사이즈, 색상)")
                    
                    with st.expander("∨ 옵션 그룹 추가/관리", expanded=True):
                         # Existing Option Builder Logic
                        if 'new_prod_opts' not in st.session_state:
                            st.session_state.new_prod_opts = []
                            
                        # Simple Form to add Option Group
                        with st.form("add_opt_group"):
                            st.write("고급설정: 특정 수량 이하일 때 고정비 부과")
                            col_n, col_v = st.columns(2)
                            og_name = col_n.text_input("그룹명 (예: 사이즈)")
                            og_val = col_v.text_input("선택값 (예: XL)")
                            
                            og_price = st.number_input("추가 단가 (개당)", step=100)
                            
                            # Threshold Logic
                            use_threshold = st.checkbox("수량 조건 사용 (예: 499개 이하시 고정비)")
                            th_qty = 0
                            th_fix = 0
                            if use_threshold:
                                c_th1, c_th2 = st.columns(2)
                                th_qty = c_th1.number_input("기준 수량 (이하)", min_value=1, value=499)
                                th_fix = c_th2.number_input("고정비용 추가 (₩)", step=1000, value=100000)
                            
                            if st.form_submit_button("옵션 규칙 추가"):
                                # Check if group exists, append value
                                found = False
                                for grp in st.session_state.new_prod_opts:
                                    if grp['name'] == og_name:
                                        grp['values'].append({
                                            "label": og_val,
                                            "price": og_price,
                                            "threshold_qty": th_qty if use_threshold else 0,
                                            "threshold_fixed_price": th_fix if use_threshold else 0
                                        })
                                        found = True
                                        break
                                if not found:
                                    st.session_state.new_prod_opts.append({
                                        "name": og_name,
                                        "values": [{
                                            "label": og_val,
                                            "price": og_price,
                                            "threshold_qty": th_qty if use_threshold else 0,
                                            "threshold_fixed_price": th_fix if use_threshold else 0
                                        }]
                                    })
                                st.rerun()

                        # Display Added Options
                        if st.session_state.new_prod_opts:
                            st.write("---")
                            st.write("현재 등록된 옵션 목록:")
                            for g_idx, grp in enumerate(st.session_state.new_prod_opts):
                                st.write(f"**[{grp['name']}]**")
                                for v in grp['values']:
                                    cond = ""
                                    if v.get('threshold_qty') > 0:
                                        cond = f" (조건: {v['threshold_qty']}개 ↓ +{v['threshold_fixed_price']:,})"
                                    st.caption(f"- {v['label']} : +{v['price']:,}{cond}")
                                if st.button(f"그룹 삭제 ({grp['name']})", key=f"del_g_{g_idx}"):
                                    st.session_state.new_prod_opts.pop(g_idx)
                                    st.rerun()
                                    
                else:
                    # China Logic: Save Base Stats Only
                    st.info("중국 제품은 '견적 작성' 탭에서 세부 옵션(환율, 물류비, 포장 등)을 설정합니다.")
                    st.markdown("**🇨🇳 중국 소싱 기본 정보**")
                    
                    c1, c2 = st.columns(2)
                    c_base = c1.number_input("현지 단가 (RMB/USD)", min_value=0.0, step=0.1, format="%.2f")
                    c_prod = c2.number_input("제작비 (현지화폐)", min_value=0.0, step=0.1, value=0.0, format="%.2f")
                    
                    final_p_price = 0 # Will be calculated at Quote time
                    p_desc_auto = f"[중국소싱] 현지단가:{c_base} + 제작비:{c_prod}"
                    
                    # For China, we don't use the Option Group Builder
                    # We will save the parameters into 'options_json' as a Dict
                    st.session_state.new_prod_opts = {
                        "type": "china",
                        "c_base": c_base,
                        "c_prod": c_prod
                    }

                st.write("---")
                if st.button("제품 등록 완료", type="primary", use_container_width=True):
                    if p_name:
                        utils.create_product(db, p_name, final_p_price, p_cat, p_desc_auto, options=st.session_state.new_prod_opts)
                        st.success(f"{p_name} 등록 완료!")
                        st.session_state.new_prod_opts = [] # Reset
                        st.rerun()
                    else:
                        st.error("제품명을 입력하세요.")
        
        with col_view:
            st.markdown("#### 📋 제품 목록")
            prods = utils.get_all_products(db)
            if prods:
                for p in prods:
                    with st.expander(f"{p.name} (₩{p.unit_price:,})"):
                        st.write(f"**카테고리:** {p.category}")
                        opts = "없음"
                        if p.options_json and p.options_json != "[]":
                            import json
                            try:
                                        if v.get('threshold_qty'):
                                            details += f" (≤{v['threshold_qty']}개: 고정 {v['threshold_fixed_price']:,})"
                                        st.write(f"- {v['label']}: {details}")
                            except:
                                pass
                        
                        if st.button("🗑 제품 삭제", key=f"del_prod_{p.id}"):
                            if utils.delete_product(db, p.name):
                                st.success("삭제되었습니다.")
                                st.rerun()
            else:
                st.info("등록된 제품이 없습니다.")
    
    db.close()

# --- PAGE 4: Data Entry ---
elif page == "데이터 입력":
    st.title("📝 데이터 입력")
    
    tab_manual, tab_csv = st.tabs(["✍️ 직접 입력", "📂 CSV 업로드"])
    
    # --- Tab 1: Manual Input ---
    with tab_manual:
        st.subheader("신규 고객 등록")
        
        with st.form("manual_customer_form"):
            col1, col2 = st.columns(2)
            m_company = col1.text_input("상호명 (필수)")
            m_client_name = col2.text_input("담당자명")
            m_phone = col1.text_input("연락처")
            m_industry = col2.text_input("업종")
            m_sales_rep = st.text_input("영업 담당자", value="관리자")
            
            st.divider()
            st.caption("선택사항: 첫 주문 정보")
            col_o1, col_o2, col_o3 = st.columns(3)
            m_product = col_o1.text_input("상품명")
            m_qty = col_o2.number_input("수량", min_value=0, step=1)
            m_total = col_o3.number_input("총금액", min_value=0, step=1000)
            
            submitted = st.form_submit_button("고객 등록")
            
            if submitted:
                if not m_company:
                    st.error("상호명은 필수입니다.")
                else:
                    db = get_session()
                    try:
                        # Create Customer
                        customer_data = {
                            "company_name": m_company,
                            "client_name": m_client_name,
                            "phone": m_phone,
                            "industry": m_industry,
                            "sales_rep": m_sales_rep
                        }
                        # Check exist
                        existing = db.query(Customer).filter(Customer.company_name == m_company).first()
                        if existing:
                            st.warning(f"이미 등록된 상호명입니다: '{m_company}'")
                        else:
                            new_customer = utils.create_customer(db, customer_data)
                            st.success(f"고객 '{m_company}' 등록 완료!")
                            
                            # Add Order if data present
                            if m_product or m_total > 0:
                                utils.create_order(
                                    db, 
                                    new_customer.id, 
                                    date.today(), 
                                    m_product, 
                                    m_qty, 
                                    m_total, 
                                    0, # deposit default 0
                                    "첫 수동 등록"
                                )
                                st.success("초기 주문 내역이 추가되었습니다.")
                    except Exception as e:
                        st.error(f"에러 발생: {e}")
                    finally:
                        db.close()

    # --- Tab 2: CSV Upload ---
    with tab_csv:
        st.subheader("CSV 대량 업로드")
        st.markdown("""
        엑셀/CSV 파일을 업로드하세요. 시스템이 자동으로 처리합니다:
        1. **신규 고객 생성** (상호명 기준으로 중복 제거)
        2. **주문 이력 추가**
        """)
        
        uploaded_file = st.file_uploader("CSV 파일 선택", type=["csv"])
        
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                st.subheader("미리보기")
                st.dataframe(df.head(), width='stretch')
                
                if st.button("업로드 시작", type="primary"):
                    db = get_session()
                    with st.spinner("데이터 처리 중입니다..."):
                        stats = utils.process_csv_data(db, df)
                    
                    st.success("완료!")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("신규 고객", stats['new_customers'])
                    col2.metric("신규 주문", stats['new_orders'])
                    col3.metric("에러 건수", stats['errors'])
                    
                    db.close()
                    
            except Exception as e:
                st.error(f"파일 읽기 오류: {e}")

# --- PAGE 5: Internal Tracking Dashboard ---
# --- PAGE 5: Internal Tracking Dashboard ---
# --- PAGE 5: Internal Tracking Dashboard ---
elif page == "메신저 입력":
    st.title("🕵️ 사내 통합 모니터링 (관리자)")
    st.info("이곳은 관리자가 메신저 내용을 수동으로 입력하거나, 전체 로그를 검토하는 페이지입니다.")
    st.info("💡 **월별 발주 캘린더**는 이제 **[대시보드]** 메뉴에서 바로 확인하실 수 있습니다.")

    # 1. Manual Input Area (Optional)
    # 1. Manual Input Area (Optional)
    with st.expander("📂 대화 내용 파일 업로드 (TXT)", expanded=True):
        uploaded_file = st.file_uploader("채팅 로그 파일(.txt)을 업로드하세요", type=["txt"])
        col_act1, col_act2 = st.columns([1, 4])
        analyze_btn = col_act1.button("1. 파일 분석 및 미리보기")
        
        if analyze_btn and uploaded_file is not None:
             # Read file
             import io
             stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
             raw_text = stringio.read()
             
             parsed = utils.parse_messenger_logs(raw_text)
             if parsed:
                 st.session_state['manual_parsed_data'] = parsed
                 st.session_state['manual_parsed_step'] = 1
                 st.rerun()
             else:
                 st.warning("분석된 내용이 없습니다. 형식을 확인해주세요.")
        elif analyze_btn and uploaded_file is None:
            st.warning("파일을 먼저 업로드해주세요.")

        # --- Interactive Parsing & Saving Flow ---
        if st.session_state.get('manual_parsed_step') == 1 and st.session_state.get('manual_parsed_data'):
            parsed_data = st.session_state['manual_parsed_data']
            st.divider()
            st.markdown("#### 🔍 분석 결과 미리보기 및 고객 매칭")
            
            # 1. Identify Unique Senders
            unique_senders = list(set(m['sender'] for m in parsed_data))
            sender_mapping = {} # {'SenderName': CustomerID or None}
            
            db = get_session()
            all_customers = utils.get_all_customers(db)
            
            # Prepare options for selectbox
            cust_options = {f"{c.company_name} ({c.client_name})": c.id for c in all_customers}
            inv_cust_options = {v: k for k, v in cust_options.items()} # ID -> Label
            
            st.info("⚠️ '보낸사람'이 등록된 고객명과 다를 경우, 아래에서 직접 연결해주세요. (연결하지 않으면 저장되지 않습니다.)")
            
            cols_map = st.columns(3)
            for idx, sender in enumerate(unique_senders):
                with cols_map[idx % 3]:
                    # Try Auto Match
                    match = next((c for c in all_customers if c.client_name == sender or c.company_name == sender), None)
                    default_idx = 0
                    if match:
                        default_label = f"{match.company_name} ({match.client_name})"
                        if default_label in cust_options:
                           # Find index in keys list (prepend 'Skip' logic)
                           pass # handled below
                    
                    # UI Select
                    options_list = ["(건너뛰기/저장안함)"] + list(cust_options.keys())
                    
                    # Determine default index
                    sel_idx = 0
                    if match:
                         target = f"{match.company_name} ({match.client_name})"
                         if target in options_list:
                             sel_idx = options_list.index(target)
                    
                    selection = st.selectbox(f"보낸사람: **{sender}**", options_list, index=sel_idx, key=f"map_{sender}_{idx}")
                    
                    if selection != "(건너뛰기/저장안함)":
                        sender_mapping[sender] = cust_options[selection]
            
            # 2. Preview Data to be Saved
            st.write("▼ 저장될 데이터 미리보기")
            preview_rows = []
            for msg in parsed_data:
                cid = sender_mapping.get(msg['sender'])
                c_name = inv_cust_options.get(cid, "❌ 매칭안됨(저장X)") if cid else "❌ 매칭안됨(저장X)"
                preview_rows.append({
                    "날짜": msg['date'].strftime("%Y-%m-%d %H:%M"),
                    "보낸사람(원본)": msg['sender'],
                    "매칭된 고객": c_name,
                    "유형": msg['type_label'],
                    "내용": msg['text'],
                    "값(금액/수량)": msg['value']
                })
            st.dataframe(pd.DataFrame(preview_rows))
            
            if st.button("2. 확정 및 저장하기", type="primary"):
                saved_count = 0
                for msg in parsed_data:
                    cid = sender_mapping.get(msg['sender'])
                    if not cid:
                        continue
                        
                    # Save logic
                    try:
                        if msg['type'] == "ORDER":
                            utils.create_order(
                                db,
                                cid,
                                msg['date'].date(),
                                "수동입력 발주",
                                msg['value'],
                                0, 0,
                                f"수동입력: {msg['text']}"
                            )
                            saved_count += 1
                        else:
                            # Payment, Price, Etc -> Interaction
                            status = "완료"
                            # Fix: Use tags that get_recent_messenger_activity expects
                            tag = f"[{msg['type_label']}]"
                            content_prefix = ""
                            
                            if msg['type'] == 'PAYMENT':
                                tag = "[입금확인]"
                                # ⚠️ CRITICAL: Embed detected value into text because Interaction table has no amount field
                                # and strict filtering discards the context message containing the number.
                                if msg.get('value', 0) > 0:
                                    content_prefix = f"({msg['value']:,}원) "
                                    
                            elif msg['type'] == 'PRICE':
                                tag = "[단가변동]"
                                
                            utils.add_interaction(
                                db,
                                cid,
                                f"{tag} {content_prefix}{msg['text']}",
                                None,
                                status,
                                log_date=msg['date'].date()
                            )
                            saved_count += 1
                    except Exception as e:
                        st.error(f"저장 중 에러: {e}")
                
                db.commit()
                db.close()
                st.success(f"총 {saved_count}건이 저장되었습니다!")
                
                # Reset state
                st.session_state['manual_parsed_data'] = None
                st.session_state['manual_parsed_step'] = 0
                st.rerun()

            db.close()
    
    st.divider()
    
    # Simple List View for debugging/detailed check
    db = get_session()
    activity = utils.get_recent_messenger_activity(db, days=7)
    
    col_order, col_pay, col_price = st.columns(3)
    
    with col_order:
        st.subheader("🚨 최근 발주")
        if activity['orders']:
            for item in activity['orders']:
                 st.info(f"{item['date'].strftime('%m/%d')} {item['sender']}: {item['text']}")
    
    with col_pay:
        st.subheader("💰 최근 입금")
        if activity['payments']:
             for item in activity['payments']:
                 st.success(f"{item['date'].strftime('%m/%d')} {item['sender']}: {item['text']}")
                 
    with col_price:
        st.subheader("📈 최근 알림")
        if activity['prices']:
             for item in activity['prices']:
                 st.warning(f"{item['date'].strftime('%m/%d')} {item['sender']}: {item['text']}")

    db.close()

# --- PAGE 6: AI CRM ---
elif page == "AI CRM":
    st.title("🤖 AI 상담/견적 비서 (Beta)")
    
    st.markdown("""
    ### 🧠 자연어 처리 테스트
    고객과의 상담 내용, 견적 요청, 발주 내용 등을 자유롭게 입력해보세요.  
    AI가 내용을 분석하여 자동으로 구조화된 데이터로 변환해줍니다.
    
    *(현재는 UI 테스트 단계이며, 실제 처리를 위해서는 Gemini API 키가 필요합니다)*
    """)
    
    # Secure API Key Input
    if 'gemini_api_key' not in st.session_state:
        st.session_state['gemini_api_key'] = ""

    # Check for secrets (st.secrets or manual file read as fallback)
    has_secret_key = False
    secret_api_key = None
    
    # 1. Try st.secrets
    try:
        if "GEMINI_API_KEY" in st.secrets:
            secret_api_key = st.secrets["GEMINI_API_KEY"]
            has_secret_key = True
    except:
        pass

    # 2. Fallback: Manual read of .streamlit/secrets.toml (if Cloud ignores repo file)
    if not has_secret_key:
        try:
            import toml
            import os
            # Try connecting path
            secret_path = os.path.join(os.path.dirname(__file__), ".streamlit/secrets.toml")
            if os.path.exists(secret_path):
                with open(secret_path, "r", encoding="utf-8") as f:
                    secrets_dict = toml.load(f)
                    if "GEMINI_API_KEY" in secrets_dict:
                        secret_api_key = secrets_dict["GEMINI_API_KEY"]
                        has_secret_key = True
        except Exception as e:
            # st.error(f"Debug: File Read Error - {e}")
            pass
            
    # 3. Last Resort: Import from api_config.py (Explicit Python File)
    if not has_secret_key:
        try:
            import api_config
            if hasattr(api_config, 'GEMINI_API_KEY'):
                secret_api_key = api_config.GEMINI_API_KEY
                has_secret_key = True
        except ImportError:
            pass

    if has_secret_key:
        st.success("✅ API Key가 설정파일에서 로드되었습니다!")
        # Inject into session state for valid use in rest of app
        st.session_state['gemini_api_key'] = secret_api_key
    else:
        with st.expander("🔑 설정 (API Key)", expanded=True):
            api_key_input = st.text_input("Google Gemini API Key", type="password", key="gemini_api_key_input")
            if api_key_input:
                st.session_state['gemini_api_key'] = api_key_input
            st.caption("API Key는 저장되지 않으며, 세션 동안만 유지됩니다.")

    # --- Top Section: Input & Customer Info ---
    with st.container():
        col_input, col_result = st.columns([1, 1], gap="medium")
        
        with col_input:
            st.subheader("📝 입력")
            user_text = st.text_area("내용을 입력하세요", height=300, 
                placeholder="예시:\n오늘 김철수 부장님이랑 통화함.\n아이폰15 프로 5개, 케이스 10개 견적 요청하심.\n단가는 아이폰 150만원, 케이스 2만원으로 맞춰드리기로 했고\n다음주 수요일까지 견적서 보내드리기로 함.")
            
            if st.button("🚀 AI 분석 실행", type="primary", use_container_width=True):
                if not user_text:
                    st.warning("내용을 입력해주세요.")
                else:
                    st.session_state['ai_processing'] = True
                    
        with col_result:
            st.subheader("📊 분석 결과")
            if st.session_state.get('ai_processing'):
                # Real AI Processing
                with st.spinner("Gemini 3-Flash Preview Model이 내용을 분석 중입니다... (Table Ver.)"):
                    try:
                        # Get Key: Prioritize Secrets
                        api_key = None
                        try:
                            api_key = st.secrets["GEMINI_API_KEY"]
                        except:
                            api_key = st.session_state.get('gemini_api_key')
                        
                        if not api_key:
                            st.error("API Key가 설정되지 않았습니다. (.streamlit/secrets.toml 확인 필요)")
                            st.session_state['ai_processing'] = False
                        else:
                            result = utils.analyze_text_with_gemini_v3(api_key, user_text)
                            
                            if "error" in result:
                                st.error(f"AI 분석 실패: {result['error']}")
                            else:
                                st.success("✅ 분석 완료!")
                                st.session_state['ai_result'] = result  # Store result in session state
                                
                    except Exception as e:
                        st.error(f"시스템 오류: {e}")
                    
                    # Processing done
                    st.session_state['ai_processing'] = False

            # Display Results (Persistent) - Top Right: Customer Info
            if 'ai_result' in st.session_state and st.session_state['ai_result']:
                result = st.session_state['ai_result']
                
                if "results" in result and result["results"]:
                    import pandas as pd
                    # We need to recreate df here or just use result dict
                    first_row = result["results"][0] if result["results"] else {}

                    # 1. Common Information (Customer)
                    st.markdown("##### 🏢 고객 정보 (공통)")
                    st.caption("고객 정보는 상단에서 한 번만 확인하세요.")
                    
                    c0_1, c0_2 = st.columns([1, 2])
                    with c0_1:
                        # Auto-fill current date/time
                        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
                        st.text_input("📅 문의일시 (자동생성)", value=current_time_str)
                    with c0_2:
                        st.text_input("고객사", value=first_row.get("company_name", ""), key="ai_cust_company")
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.text_input("업종", value=first_row.get("industry", ""), key="ai_cust_industry")
                    with c2:
                        st.text_input("담당자", value=first_row.get("manager", ""), key="ai_cust_manager")
                    with c3:
                        st.text_input("연락처", value=first_row.get("phone", ""), key="ai_cust_phone")
                        
                    c4, c5 = st.columns(2)
                    with c4:
                        st.text_input("이메일", value=first_row.get("email", ""), key="ai_cust_email")
                    with c5:
                         pass # Spacer

    # --- Bottom Section: Product List (Full Width) ---
    with st.container():
        if 'ai_result' in st.session_state and st.session_state['ai_result']:
            result = st.session_state['ai_result']
            if "results" in result and result["results"]:
                st.divider() # Visual separation
                st.markdown("##### 📦 제품 목록 (상세)")
                st.caption("아래 표에서 제품 정보를 자세히 확인하고 수정할 수 있습니다. (DB schema updated)")

                import pandas as pd
                df = pd.DataFrame(result["results"])
                
                # Filter product-related columns
                # user requested: product / quantity / print_type / origin / color / due_date / cutting / remote / note
                product_cols_map = {
                    "product": "제품",
                    "quantity": "수량",
                    "print_type": "인쇄방식",
                    "origin": "제작",
                    "color": "색상",
                    "due_date": "납기일",
                    "cutting": "컷팅",
                    "remote_control": "원격조종",
                    "note": "비고"
                }
                
                # Ensure columns exist in df before renaming
                # Force ensure columns exist even if AI missed them, to show the structure
                for k in product_cols_map.keys():
                    if k not in df.columns:
                        if k in ["cutting", "remote_control"]:
                            df[k] = False
                        elif k == "quantity":
                            df[k] = 0
                        else:
                            df[k] = ""
                            
                existing_product_keys = [k for k in product_cols_map.keys()]
                df_products = df[existing_product_keys].copy()
                df_products = df_products.rename(columns=product_cols_map)
                
                # Define column configuration for better UX
                column_config = {
                    "수량": st.column_config.NumberColumn("수량", min_value=1, step=1),
                    "제품": st.column_config.TextColumn("제품", width="medium"),
                    "인쇄방식": st.column_config.SelectboxColumn("인쇄방식", options=["1도 단면", "1도 양면", "UV인쇄", "각인"], width="medium"),
                    "제작": st.column_config.SelectboxColumn("제작", options=["국내", "중국"], width="small"),
                    "색상": st.column_config.TextColumn("색상", width="small"),
                    "납기일": st.column_config.TextColumn("납기일", width="medium"),
                    "컷팅": st.column_config.CheckboxColumn("컷팅", width="small"),
                    "원격조종": st.column_config.CheckboxColumn("원격조종", width="small"),
                    "비고": st.column_config.TextColumn("비고", width="large"),
                }
                
                edited_df = st.data_editor(
                    df_products, 
                    use_container_width=True, 
                    num_rows="dynamic",
                    column_config=column_config
                )
            else:
                st.warning("분석된 데이터가 없습니다.")

            # Action Buttons (Restored & Updated)
            if "results" in result and result["results"]:
                st.divider()
                st.markdown("##### 📥 데이터 처리")
                
                if st.button("💾 고객 및 견적 등록", key="btn_upsert_all", type="primary", use_container_width=True):
                    # 1. Gather Customer Data from Inputs (using keys)
                    c_data = {
                        "company_name": st.session_state.get("ai_cust_company"),
                        "industry": st.session_state.get("ai_cust_industry"),
                        "manager": st.session_state.get("ai_cust_manager"),
                        "phone": st.session_state.get("ai_cust_phone"),
                        "email": st.session_state.get("ai_cust_email")
                    }
                    
                    if not c_data["company_name"]:
                        st.error("고객사명은 필수입니다.")
                    else:
                        with next(utils.get_db()) as db:
                            # 2. Upsert Customer
                            status, msg, customer = utils.upsert_customer_from_ai(db, c_data)
                            
                            if status == "error":
                                st.error(f"고객 저장 실패: {msg}")
                            else:
                                st.toast(f"고객: {msg}", icon="✅")
                                
                                # 3. Create Quote with Items
                                # Map back from Korean to English keys for the utility function
                                reverse_map = {v: k for k, v in product_cols_map.items()} # product_cols_map is defined above
                                
                                products_data = []
                                for index, row in edited_df.iterrows():
                                    item = {}
                                    for col_name, val in row.items():
                                        # Dataframe columns are Korean (e.g., '제품'), map to 'product'
                                        if col_name in reverse_map:
                                            key = reverse_map[col_name]
                                            item[key] = val
                                    products_data.append(item)
                                
                                if products_data:
                                    q_status, q_msg = utils.create_quote_from_ai(db, customer.id, products_data)
                                    if q_status == "success":
                                        st.success(f"완료! {msg}\n{q_msg}")
                                    else:
                                        st.error(f"견적 생성 실패: {q_msg}")
                                else:
                                    st.warning("저장할 제품 목록이 없습니다.")
