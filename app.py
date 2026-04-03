import streamlit as st
import pandas as pd
import plotly.express as px

# 1. 페이지 설정
st.set_page_config(page_title="Healer's Balance Pro", layout="wide", page_icon="🏥")

# 2. 데이터 정제 및 분류 함수
def clean_val(x):
    """숫자 데이터 정제 (콤마, 원 등 제거)"""
    if pd.isna(x) or x == '-': return 0.0
    if isinstance(x, (int, float)): return float(x)
    val = str(x).replace(',', '').replace('"', '').replace('원', '').strip()
    try: return float(val)
    except: return 0.0

def load_data(file_obj, header_idx):
    """어떤 인코딩/확장자든 뚫고 읽어내는 파일 로더"""
    if file_obj.name.lower().endswith(('.xls', '.xlsx')):
        return pd.read_excel(file_obj, header=header_idx)
    
    # CSV 파일인 경우 여러 인코딩 시도
    encodings = ['utf-8', 'cp949', 'euc-kr', 'utf-8-sig']
    for enc in encodings:
        try:
            file_obj.seek(0) # 스트림 위치 초기화
            df = pd.read_csv(file_obj, header=header_idx, encoding=enc)
            if len(df.columns) > 1: return df
        except:
            continue
            
    # 다 실패하면 강제로 엑셀 엔진으로 시도
    file_obj.seek(0)
    return pd.read_excel(file_obj, header=header_idx)

def auto_categorize(desc):
    """가맹점 이름 기반 자동 분류 엔진"""
    desc = str(desc).replace(' ', '')
    if any(k in desc for k in ['이마트', '다이소', '씨유', 'CU', '편의점', '마트']): return '생활비/마트'
    if any(k in desc for k in ['쿠팡', '네이버페이', '카카오페이']): return '온라인쇼핑'
    if any(k in desc for k in ['세무', '보험약', '한약', '경옥고', '소모품', '원외탕전']): return '한의원 경비'
    if any(k in desc for k in ['에너지', '주유', '자동차', '주차']): return '차량/교통'
    if any(k in desc for k in ['식당', '카페', '커피', '배달', '요기요', '배달의민족']): return '외식/식비'
    return '기타/미분류'

# 3. UI 사이드바 (파일 업로드)
with st.sidebar:
    st.header("📂 월간 데이터 업로드")
    st.info("은행/카드사에서 다운로드한 엑셀/CSV 파일을 그대로 올려주세요.")
    
    st.subheader("1. 병원 수입")
    inc_file = st.file_uploader("한의맥 년월결산", type=['csv', 'xls', 'xlsx'])
    
    st.subheader("2. 지출 원본 (다중 선택 가능)")
    sh_card = st.file_uploader("신한카드 내역", type=['csv', 'xls', 'xlsx'])
    wr_card = st.file_uploader("우리카드 내역", type=['csv', 'xls', 'xlsx'])
    sh_bank = st.file_uploader("신한은행 내역", type=['csv', 'xls', 'xlsx'])
    ibk_bank = st.file_uploader("기업은행 내역", type=['csv', 'xls', 'xlsx'])
    
    st.subheader("3. 수기 입력")
    cash_input = st.number_input("이번 달 현금 지출 총액", min_value=0, value=0, step=10000)

# 4. 메인 화면 및 데이터 처리
st.title("🏥 원장님 맞춤형 통합 자산관리 대시보드")

if inc_file or sh_card or wr_card or sh_bank or ibk_bank or cash_input > 0:
    with st.spinner("데이터를 자동으로 취합하고 분류하는 중입니다..."):
        try:
            total_income = 0
            rev_val = 0
            claim_val = 0
            
            # --- 수입 (한의맥) ---
            if inc_file:
                inc_df = load_data(inc_file, header_idx=2)
                # 빈 줄 삭제 및 '합계' 행 날리기
                inc_df = inc_df.dropna(subset=['진료일자'])
                mask = inc_df['보험'].astype(str).str.contains('합계|총계|총합|소계', na=False)
                inc_clean = inc_df[~mask].copy()
                
                rev_val = inc_clean['총수납액'].apply(clean_val).sum()
                claim_val = inc_clean['청구액'].apply(clean_val).sum()
                total_income = rev_val + claim_val

            # --- 지출 통합 ---
            all_expenses = []

            # 1. 신한카드 (헤더 0)
            if sh_card:
                df = load_data(sh_card, header_idx=0)
                df_p = pd.DataFrame({
                    '날짜': df.get('거래일', df.iloc[:,0]),
                    '금액': df.get('금액', df.iloc[:,5]).apply(clean_val),
                    '설명': df.get('가맹점명', df.iloc[:,3]),
                    '출처': '신한카드'
                })
                all_expenses.append(df_p)

            # 2. 우리카드 (헤더 1)
            if wr_card:
                df = load_data(wr_card, header_idx=1)
                df_p = pd.DataFrame({
                    '날짜': df.get('이용일', df.iloc[:,0]),
                    '금액': df.get('이용금액(원)', df.iloc[:,7]).apply(clean_val),
                    '설명': df.get('이용가맹점(은행)명', df.iloc[:,3]),
                    '출처': '우리카드'
                })
                all_expenses.append(df_p)

            # 3. 신한은행 (헤더 6)
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

            # 4. 기업은행 (헤더 없음 -> header=None)
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

            # --- 데이터 병합 및 시각화 ---
            if all_expenses or cash_input > 0:
                if all_expenses:
                    exp_final = pd.concat(all_expenses, ignore_index=True)
                    exp_final['날짜'] = exp_final['날짜'].astype(str).str[:10]
                else:
                    exp_final = pd.DataFrame(columns=['날짜', '금액', '설명', '출처'])

                if cash_input > 0:
                    exp_final.loc[len(exp_final)] = ['수기입력', cash_input, '현금 지출 (자동합산)', '현금']

                # 자동 분류 적용
                exp_final['카테고리'] = exp_final['설명'].apply(auto_categorize)
                
                total_exp = exp_final['금액'].sum()
                biz_exp = exp_final[exp_final['카테고리'] == '한의원 경비']['금액'].sum()
                personal_exp = total_exp - biz_exp
                net_income = total_income - biz_exp

                # 상단 핵심 지표
                st.subheader("💰 월간 통합 성적표")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("총 수입 (매출+청구)", f"{total_income:,.0f}원")
                col2.metric("한의원 자동 경비", f"-{biz_exp:,.0f}원")
                col3.metric("원장님 순소득", f"{net_income:,.0f}원")
                col4.metric("최종 잉여 자산", f"{net_income - personal_exp:,.0f}원", delta_color="normal")
                
                st.divider()
                
                # 차트 섹션
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("#### 💳 결제 수단별 지출 비중")
                    fig1 = px.pie(exp_final, values='금액', names='출처', hole=0.4)
                    st.plotly_chart(fig1, use_container_width=True)
                with c2:
                    st.markdown("#### 🛒 소비 카테고리별 비중")
                    fig2 = px.pie(exp_final[exp_final['카테고리'] != '한의원 경비'], values='금액', names='카테고리', hole=0.4)
                    st.plotly_chart(fig2, use_container_width=True)
                
                st.divider()
                
                # 상세 테이블
                st.subheader("📋 전체 결제 내역 (자동 분류 완료)")
                st.dataframe(
                    exp_final.sort_values('금액', ascending=False).reset_index(drop=True),
                    use_container_width=True,
                    height=400
                )
            else:
                st.info("지출 내역 파일이나 현금 지출액을 입력해주세요.")
                
        except Exception as e:
            st.error(f"데이터 처리 중 오류가 발생했습니다: {str(e)}")
            st.info("업로드한 파일이 정확한지 확인해 주세요.")
else:
    st.info("👈 왼쪽 사이드바에 파일들을 업로드하면 대시보드가 자동으로 생성됩니다.")
