import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Healer's Balance Pro", layout="wide", page_icon="🏥")

def clean_val(x):
    """숫자 데이터 정제"""
    if pd.isna(x) or x == '-': return 0.0
    if isinstance(x, (int, float)): return float(x)
    val = str(x).replace(',', '').replace('"', '').replace('원', '').strip()
    try: return float(val)
    except: return 0.0

def load_data(file_obj, header_idx):
    """인코딩 무적 파일 로더"""
    if file_obj.name.lower().endswith(('.xls', '.xlsx')):
        return pd.read_excel(file_obj, header=header_idx)
    
    encodings = ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']
    for enc in encodings:
        try:
            file_obj.seek(0)
            df = pd.read_csv(file_obj, header=header_idx, encoding=enc)
            if len(df.columns) > 1: return df
        except: continue
            
    file_obj.seek(0)
    return pd.read_excel(file_obj, header=header_idx)

def is_duplicate_or_transfer(desc):
    """[핵심 1] 이중 지출 및 계좌 간 이체 필터링 (원장님 데이터 기반)"""
    desc = str(desc).replace(' ', '')
    # 신한은행, 타행이체, 카드대금, 페이충전 등 내 통장 안에서 돈이 도는 것들
    exclude_keywords = ['타행이체', '신한은행', '하나988', '현126', '카드', '네이버페이충전', '7064299']
    return any(k in desc for k in exclude_keywords)

def auto_categorize(desc):
    """[핵심 2] 원장님 맞춤형 자동 분류 엔진"""
    desc = str(desc).replace(' ', '')
    
    # 1. 한의원 고정/운영 경비 (원장님 실제 데이터 반영)
    if any(k in desc for k in ['이윤세무', '삼성화재', '보험약', '바른한약', '경옥고', '소모품', '통신']): 
        return '한의원 경비'
    
    # 2. 생활/장보기
    if any(k in desc for k in ['이마트', '다이소', '씨유', 'CU', '정육점', '영양제']): 
        return '생활비/마트'
    
    # 3. 외식/배달
    if any(k in desc for k in ['숙성도', '커피', '에그타르트', '고등어회', '닭갈비', '각재기국']): 
        return '외식/식비'
    
    # 4. 차량/교통
    if any(k in desc for k in ['천하자동차', '천마에너지', '에너지']): 
        return '차량/교통'
    
    # 5. 쇼핑/온라인
    if any(k in desc for k in ['쿠팡', '네이버페이', '롯데물산']): 
        return '온라인쇼핑'
    
    # 6. 용돈 및 기타
    if any(k in desc for k in ['아내', '부모님']): 
        return '가족 용돈'
    
    return '개인/기타'

with st.sidebar:
    st.header("📂 월간 데이터 업로드")
    
    st.subheader("1. 병원 수입")
    inc_file = st.file_uploader("한의맥 년월결산", type=['csv', 'xls', 'xlsx'])
    
    st.subheader("2. 지출 원본 (은행/카드사)")
    sh_card = st.file_uploader("신한카드 내역", type=['csv', 'xls', 'xlsx'])
    wr_card = st.file_uploader("우리카드 내역", type=['csv', 'xls', 'xlsx'])
    sh_bank = st.file_uploader("신한은행 내역", type=['csv', 'xls', 'xlsx'])
    ibk_bank = st.file_uploader("기업은행 내역", type=['csv', 'xls', 'xlsx'])
    
    st.subheader("3. 수기 입력")
    cash_input = st.number_input("이번 달 현금 지출 (단위: 원)", min_value=0, value=0, step=10000)

st.title("🏥 원장님 맞춤형 통합 자산관리 대시보드")

if inc_file or sh_card or wr_card or sh_bank or ibk_bank or cash_input > 0:
    with st.spinner("이중 결제 제외 및 맞춤형 카테고리 분류 중..."):
        try:
            total_income = 0
            
            # --- 수입 (한의맥) ---
            if inc_file:
                inc_df = load_data(inc_file, header_idx=2)
                inc_df = inc_df.dropna(subset=['진료일자'])
                mask = inc_df['보험'].astype(str).str.contains('합계|총계|총합|소계', na=False)
                inc_clean = inc_df[~mask].copy()
                total_income = inc_clean['총수납액'].apply(clean_val).sum() + inc_clean['청구액'].apply(clean_val).sum()

            # --- 지출 통합 ---
            all_expenses = []

            if sh_card:
                df = load_data(sh_card, header_idx=0)
                df_p = pd.DataFrame({
                    '날짜': df.get('거래일', df.iloc[:,0]),
                    '금액': df.get('금액', df.iloc[:,5]).apply(clean_val),
                    '설명': df.get('가맹점명', df.iloc[:,3]),
                    '출처': '신한카드'
                })
                all_expenses.append(df_p)

            if wr_card:
                df = load_data(wr_card, header_idx=1)
                df_p = pd.DataFrame({
                    '날짜': df.get('이용일', df.iloc[:,0]),
                    '금액': df.get('이용금액(원)', df.iloc[:,7]).apply(clean_val),
                    '설명': df.get('이용가맹점(은행)명', df.iloc[:,3]),
                    '출처': '우리카드'
                })
                all_expenses.append(df_p)

            if sh_bank:
                df = load_data(sh_bank, header_idx=6)
                df = df[df.get('출금(원)', df.iloc[:,3]).apply(clean_val) > 0]
                df_p = pd.DataFrame({
                    '날짜': df.get('거래일자', df.iloc[:,0]),
                    '금액': df.get('출금(원)', df.iloc[:,3]).apply(clean_val),
                    '설명': df.get('내용', df.iloc[:,5]),
                    '출처': '신한은행'
                })
                all_expenses.append(df_p)

            if ibk_bank:
                df = load_data(ibk_bank, header_idx=None)
                df = df[df.iloc[:,1].apply(clean_val) > 0]
                df_p = pd.DataFrame({
                    '날짜': df.iloc[:,0],
                    '금액': df.iloc[:,1].apply(clean_val),
                    '설명': df.iloc[:,4],
                    '출처': '기업은행'
                })
                all_expenses.append(df_p)

            # --- 병합 및 필터링 ---
            if all_expenses or cash_input > 0:
                if all_expenses:
                    exp_final = pd.concat(all_expenses, ignore_index=True)
                    exp_final['날짜'] = exp_final['날짜'].astype(str).str[:10]
                    
                    # [적용] 이중 지출(계좌이체 등) 걸러내기
                    exp_final = exp_final[~exp_final['설명'].apply(is_duplicate_or_transfer)]
                else:
                    exp_final = pd.DataFrame(columns=['날짜', '금액', '설명', '출처'])

                if cash_input > 0:
                    exp_final.loc[len(exp_final)] = ['수기입력', cash_input, '현금 지출 (자동합산)', '현금']

                # [적용] 맞춤형 카테고리 자동 분류
                exp_final['카테고리'] = exp_final['설명'].apply(auto_categorize)
                
                total_exp = exp_final['금액'].sum()
                biz_exp = exp_final[exp_final['카테고리'] == '한의원 경비']['금액'].sum()
                personal_exp = total_exp - biz_exp
                net_income = total_income - biz_exp

                # 대시보드 출력
                st.subheader("💰 월간 통합 성적표")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("총 수입 (한의맥)", f"{total_income:,.0f}원")
                col2.metric("한의원 경비", f"-{biz_exp:,.0f}원")
                col3.metric("원장님 순소득", f"{net_income:,.0f}원")
                col4.metric("이번 달 잉여 자산", f"{net_income - personal_exp:,.0f}원", delta_color="normal")
                
                st.divider()
                
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### 🛒 소비 카테고리별 비중 (경비 제외)")
                    fig1 = px.pie(exp_final[exp_final['카테고리'] != '한의원 경비'], values='금액', names='카테고리', hole=0.4)
                    st.plotly_chart(fig1, use_container_width=True)
                with c2:
                    st.markdown("#### 💳 결제 수단별 지출 비중")
                    fig2 = px.pie(exp_final, values='금액', names='출처', hole=0.4)
                    st.plotly_chart(fig2, use_container_width=True)
                
                st.divider()
                
                st.subheader("📋 전체 결제 내역 (중복 제거 및 분류 완료)")
                st.dataframe(
                    exp_final.sort_values('금액', ascending=False).reset_index(drop=True),
                    use_container_width=True,
                    height=500
                )
            else:
                st.info("유효한 지출 내역이 없습니다.")
                
        except Exception as e:
            st.error(f"오류 발생: {str(e)}")
else:
    st.info("👈 왼쪽 사이드바에 파일들을 업로드하면 자동으로 이중 결제를 제외하고 분류합니다.")
