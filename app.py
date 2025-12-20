import streamlit as st
import pandas as pd
from datetime import date, timedelta
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
page = st.sidebar.radio("메뉴 이동", ["대시보드", "고객 관리", "견적 관리", "데이터 입력"], index=0)

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

# --- PAGE 1: Dashboard ---
if page == "대시보드":
    st.title("📊 대시보드")
    
    db = get_session()
    
    # Metrics
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
    
    with chart_col1:
        st.write("**월별 매출 추이**")
        trend_data = utils.get_monthly_sales_trend(db)
        if trend_data["Date"]:
            df_trend = pd.DataFrame(trend_data)
            st.bar_chart(df_trend, x="Date", y="Sales", color="#4CAF50")
        else:
            st.info("데이터가 부족합니다.")

    with chart_col2:
        st.write("**업종별 매출 비중**")
        industry_data = utils.get_sales_by_industry(db)
        if industry_data["Industry"]:
            df_ind = pd.DataFrame(industry_data)
            st.bar_chart(df_ind, x="Industry", y="Sales", color="#FF9800")
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
                            st.markdown(f"{log.content}")
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
                if quotes:
                    for q in quotes:
                        with st.expander(f"📄 견적 #{q.id} ({q.status}) - ₩{q.total_amount:,}"):
                            st.write(f"**유효기간:** {q.valid_until}")
                            st.write(f"**메모:** {q.note}")
                            # Items
                            st.table(pd.DataFrame([{"상품": i.product_name, "수량": i.quantity, "단가": i.unit_price, "금액": i.amount} for i in q.items]))
                            
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
                        
                        with col_q:
                            i_qty = st.number_input("수량", min_value=1, value=1)
                        
                        sel_prod = next((p for p in products if p.name == i_name_sel), None)
                        
                        # Options Logic
                        import json
                        options_list = []
                        if sel_prod and sel_prod.options_json:
                            try:
                                options_list = json.loads(sel_prod.options_json)
                            except:
                                options_list = []
                        
                        base_price = sel_prod.unit_price if sel_prod else 0
                        calc_unit_price = base_price
                        fixed_add_cost = 0 # Cost added to TOTAL, not unit
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
                                        # Show threshold info in label if exists
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
                        st.table(pd.DataFrame([{"상품": i.product_name, "옵션": i.selected_options, "수량": i.quantity, "금액": i.amount} for i in q.items]))
                        
                        c1, c2, c3 = st.columns([1, 1, 3])
                        if c1.button("🗑 삭제", key=f"del_q_{q.id}"):
                            if utils.delete_quote(db, q.id):
                                st.success("삭제되었습니다.")
                                st.rerun()
                        
                        if c2.button("✏️ 불러오기(수정)", key=f"edit_q_{q.id}"):
                            # Load items into session state and switch tab
                            st.session_state.quote_items = []
                            for i in q.items:
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
                    # Domestic
                    p_price = st.number_input("기본 단가 (KRW)", min_value=0, step=100)
                    final_p_price = p_price
                    p_desc_auto = "국내 소싱 제품"
                    
                else:
                    # China: Calculation Logic
                    st.markdown("**🇨🇳 중국 소싱 단가 계산**")
                    c1, c2 = st.columns(2)
                    c_base = c1.number_input("현지 단가 (RMB/USD)", min_value=0.0, step=0.1, format="%.2f")
                    c_rate = c2.number_input("환율 (Exchange Rate)", min_value=0.0, step=1.0, value=195.0)
                    
                    c3, c4 = st.columns(2)
                    c_logistics = c3.number_input("물류비 배율 (예: 1.1)", min_value=1.0, step=0.05, value=1.0)
                    c_prod = c4.number_input("제작비 (단가 합산)", min_value=0.0, step=0.1, value=0.0, format="%.2f")
                    
                    # Formula: (Base + Production) * Rate * Logistics
                    final_p_price = int((c_base + c_prod) * c_rate * c_logistics)
                    
                    st.info(f"🧮 계산된 단가: **₩{final_p_price:,}**")
                    p_desc_auto = f"[중국소싱] (현지:{c_base} + 제작:{c_prod}) * 환율:{c_rate} * 물류:{c_logistics}"

                st.markdown("---")
                st.markdown("**옵션 구성**")
                
                with st.expander("옵션 그룹 추가/관리", expanded=True):
                    with st.form("add_opt_form", clear_on_submit=True):
                        st.caption("고급설정: 특정 수량 이하일 때 고정비 부과")
                        c1, c2 = st.columns(2)
                        o_grp = c1.text_input("그룹명", value="사이즈")
                        o_lbl = c2.text_input("선택값", value="기본")
                        
                        c3, c4 = st.columns(2)
                        o_price = c3.number_input("추가 단가 (개당)", step=100, value=0)
                        
                        # Threshold Logic
                        use_th = st.checkbox("수량 조건 사용 (예: 499개 이하시 고정비)")
                        th_qty = 0
                        th_fixed = 0
                        
                        def_th = 499 if sourcing_type == "국내" else 500
                        
                        if use_th:
                             c5, c6 = st.columns(2)
                             th_qty = c5.number_input("기준 수량 (이하)", value=def_th, step=1)
                             th_fixed = c6.number_input("고정비용 (Total)", value=250000, step=10000)
                        
                        if st.form_submit_button("옵션 규칙 추가"):
                            if o_grp and o_lbl:
                                found = False
                                new_val = {
                                    "label": o_lbl, 
                                    "price": o_price,
                                    "threshold_qty": th_qty if use_th else 0,
                                    "threshold_fixed_price": th_fixed if use_th else 0
                                }
                                
                                for grp in st.session_state.new_prod_opts:
                                    if grp['name'] == o_grp:
                                        grp['values'].append(new_val)
                                        found = True
                                        break
                                if not found:
                                    st.session_state.new_prod_opts.append({
                                        "name": o_grp,
                                        "values": [new_val]
                                    })
                                st.rerun()
                            else:
                                st.warning("그룹명과 선택값을 입력하세요.")

                    if st.session_state.new_prod_opts:
                        st.caption("설정된 옵션:")
                        for grp_idx, grp in enumerate(st.session_state.new_prod_opts):
                            st.write(f"**📂 {grp['name']}**")
                            for val_idx, val in enumerate(grp['values']):
                                c_show, c_del = st.columns([4, 1])
                                info = f"- {val['label']} (+{val['price']:,})"
                                if val.get('threshold_qty', 0) > 0:
                                    info += f" [조건: {val['threshold_qty']}개↓ 고정 {val['threshold_fixed_price']:,}]"
                                c_show.text(info)
                                if c_del.button("❌", key=f"del_opt_{grp_idx}_{val_idx}"):
                                    grp['values'].pop(val_idx)
                                    if not grp['values']:
                                        st.session_state.new_prod_opts.pop(grp_idx)
                                    st.rerun()
                
                st.markdown("---")
                
                if st.button("제품 등록 완료", type="primary", use_container_width=True):
                    if p_name and final_p_price >= 0:
                        res = utils.create_product(db, p_name, final_p_price, p_cat, p_desc_auto, options=st.session_state.new_prod_opts)
                        if res:
                            st.success(f"'{p_name}' 등록 완료")
                            st.session_state.new_prod_opts = [] # Init
                            st.rerun()
                        else:
                            st.error("이미 존재하는 제품명입니다.")
                    else:
                        st.error("제품명과 가격을 확인해주세요.")
        
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
                                o_list = json.loads(p.options_json)
                                st.write("**옵션 상세:**")
                                for grp in o_list:
                                    st.write(f"_{grp['name']}_")
                                    for v in grp['values']:
                                        details = f"+{v['price']:,}"
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
