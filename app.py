import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Healer's Balance Pro", layout="wide", page_icon="🏥")

def clean_val(x):
    if pd.isna(x) or x == '-': return 0.0
    if isinstance(x, (int, float)): return float(x)
    val = str(x).replace(',', '').replace('"', '').replace('원', '').strip()
    try: return float(val)
    except: return 0.0

def load_data(file_obj, header_idx):
    if file_obj.name.lower().endswith(('.xls', '.xlsx')):
        return pd.read_excel(file_obj, header=header_idx)
    
    for enc in ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']:
        try:
            file_obj.seek(0)
            df = pd.read_csv(file_obj, header=header_idx, encoding=enc)
            if len(df.columns) > 1: return df
        except: continue
    file_obj.seek(0)
    return pd.read_excel(file_obj, header=header_idx)

def is_duplicate(desc):
    desc = str(desc).replace(' ', '')
    return any(k in desc for k in ['타행이체', '신한은행', '하나988', '현126', '카드', '네이버페이충전', '7064299'])

# [핵심] 사용자가 입력한 키워드를 받아 분류하는 스마트 엔진
def auto_categorize(desc, kw_salary, kw_rent, kw_tax):
    desc = str(desc).replace(' ', '')
    
    # 1. 앱에서 입력받은 동적 키워드 (가장 최우선)
    if kw_salary and any(k.strip() in desc for k in kw_salary.split(',') if k.strip()): return '한의원 경비'
    if kw_rent and any(k.strip() in desc for k in kw_rent.split(',') if k.strip()): return '한의원 경비'
    if kw_tax and any(k.strip() in desc for k in kw_tax.split(',') if k.strip()): return '한의원 경비'
    
    # 2. 고정 키워드
    if any(k in desc for k in ['이윤세무', '삼성화재', '보험약', '바른한약', '경옥고', '소모품', '통신']): return '한의원 경비'
    if any(k in desc for k in ['이마트', '다이소', '씨유', 'CU', '정육점', '영양제']): return '생활비/마트'
    if any(k in desc for k in ['숙성도', '커피', '에그타르트', '고등어회', '닭갈비', '각재기국', '식당']): return '외식/식비'
    if any(k in desc for k in ['천하자동차', '천마에너지', '에너지']): return '차량/교통'
    if any(k in desc for k in ['쿠팡', '네이버페이', '롯데물산']): return '온라인쇼핑'
    if any(k in desc for k in ['아내', '부모님']): return '가족 용돈'
    
    return '개인/기타 (미분류)'

with st.sidebar:
    st.header("📂 1. 데이터 업로드")
    inc_file = st.file_uploader("한의맥 년월결산", type=['csv', 'xls', 'xlsx'])
    sh_card = st.file_uploader("신한카드 내역", type=['csv', 'xls', 'xlsx'])
    wr_card = st.file_uploader("우리카드 내역", type=['csv', 'xls', 'xlsx'])
    sh_bank = st.file_uploader("신한은행 내역", type=['csv', 'xls', 'xlsx'])
    ibk_bank = st.file_uploader("기업은행 내역", type=['csv', 'xls', 'xlsx'])
    cash_input = st.number_input("이번 달 현금 지출 (단위: 원)", min_value=0, value=0, step=10000)

    st.divider()
    
    st.header("⚙️ 2. 한의원 고정비 키워드 설정")
    st.caption("은행 내역에 찍히는 이름들을 쉼표(,)로 구분해 적어주세요. 바로 경비로 처리됩니다.")
    kw_salary = st.text_input("직원 이름 (급여)", placeholder="예: 김간호, 이실장")
    kw_rent = st.text_input("건물주/상호명 (월세)", placeholder="예: 홍길동, 메디컬타워")
    kw_tax = st.text_input("세금/4대보험", value="국민건강, 건강보험, 국민연금, 고용보험, 산재보험")

st.title("🏥 원장님 맞춤형 통합 자산관리 대시보드")

if inc_file or sh_card or wr_card or sh_bank or ibk_bank:
    with st.spinner("데이터 분석 중..."):
        try:
            total_income = 0
            if inc_file:
                inc_df = load_data(inc_file, header_idx=2)
                inc_df = inc_df.dropna(subset=['진료일자'])
                inc_clean = inc_df[~inc_df['보험'].astype(str).str.contains('합계|총계|총합|소계', na=False)].copy()
                total_income = inc_clean['총수납액'].apply(clean_val).sum() + inc_clean['청구액'].apply(clean_val).sum()

            all_expenses = []
            if sh_card:
                df = load_data(sh_card, header_idx=0)
                all_expenses.append(pd.DataFrame({'날짜': df.iloc[:,0], '금액': df.get('금액', df.iloc[:,5]).apply(clean_val), '설명': df.get('가맹점명', df.iloc[:,3]), '출처': '신한카드'}))
            if wr_card:
                df = load_data(wr_card, header_idx=1)
                all_expenses.append(pd.DataFrame({'날짜': df.iloc[:,0], '금액': df.get('이용금액(원)', df.iloc[:,7]).apply(clean_val), '설명': df.get('이용가맹점(은행)명', df.iloc[:,3]), '출처': '우리카드'}))
            if sh_bank:
                df = load_data(sh_bank, header_idx=6)
                df = df[df.get('출금(원)', df.iloc[:,3]).apply(clean_val) > 0]
                all_expenses.append(pd.DataFrame({'날짜': df.iloc[:,0], '금액': df.get('출금(원)', df.iloc[:,3]).apply(clean_val), '설명': df.get('내용', df.iloc[:,5]), '출처': '신한은행'}))
            if ibk_bank:
                df = load_data(ibk_bank, header_idx=None)
                df = df[df.iloc[:,1].apply(clean_val) > 0]
                all_expenses.append(pd.DataFrame({'날짜': df.iloc[:,0], '금액': df.iloc[:,1].apply(clean_val), '설명': df.iloc[:,4], '출처': '기업은행'}))

            if all_expenses:
                exp_final = pd.concat(all_expenses, ignore_index=True)
                exp_final['날짜'] = exp_final['날짜'].astype(str).str[:10]
                exp_final = exp_final[~exp_final['설명'].apply(is_duplicate)]

                if cash_input > 0:
                    exp_final.loc[len(exp_final)] = ['수기입력', cash_input, '현금 지출 (자동합산)', '현금']

                # 키워드 설정을 반영한 자동 분류
                exp_final['카테고리'] = exp_final['설명'].apply(lambda x: auto_categorize(x, kw_salary, kw_rent, kw_tax))
                
                total_exp = exp_final['금액'].sum()
                biz_exp = exp_final[exp_final['카테고리'] == '한의원 경비']['금액'].sum()
                personal_exp = total_exp - biz_exp
                net_income = total_income - biz_exp

                st.subheader("💰 월간 통합 성적표")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("총 수입", f"{total_income:,.0f}원")
                col2.metric("한의원 경비", f"-{biz_exp:,.0f}원")
                col3.metric("원장님 순소득", f"{net_income:,.0f}원")
                col4.metric("이번 달 잉여 자산", f"{net_income - personal_exp:,.0f}원", delta_color="normal")
                
                st.divider()
                st.subheader("⚠️ 분류가 필요한 지출 (개인/기타)")
                st.caption("아래 리스트에 병원 경비가 보인다면, 왼쪽 사이드바 '키워드 설정'에 이름을 추가하세요!")
                unclassified = exp_final[exp_final['카테고리'] == '개인/기타 (미분류)'].sort_values('금액', ascending=False)
                st.dataframe(unclassified[['날짜', '설명', '금액', '출처']].reset_index(drop=True), use_container_width=True)

        except Exception as e:
            st.error(f"오류 발생: {str(e)}")
else:
    st.info("👈 파일을 업로드하세요.")
