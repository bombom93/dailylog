
import streamlit as st
import pandas as pd
from datetime import date, timedelta
import os

st.set_page_config(page_title="데일리로그(주간 표)", layout="wide")

# =========================
# 설정
# =========================
LOG_FILE = "weekly_log.csv"   # 로컬 CSV 저장(개인용)
DATE_FMT = "%Y-%m-%d"

# 주간 표에 쓸 항목(행)
ROWS = [
    "오늘의 할일", "오늘의 성취", "기분", "에너지", "수면", "식욕",
    "집중력", "가장 미룬일", "두통", "특이사항", "감정한줄일기"
]

# =========================
# 유틸
# =========================
def load_log():
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE, dtype=str, encoding="utf-8-sig")
        if "date" not in df.columns:
            df["date"] = ""
        return df
    return pd.DataFrame(columns=["date"] + ROWS)

def save_log(df: pd.DataFrame):
    df = df.copy()
    # 날짜 컬럼을 문자열로
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.strftime(DATE_FMT)
    df.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")

def get_monday(d: date) -> date:
    return d - timedelta(days=(d.weekday()))  # 월요일=0

def week_dates(monday: date):
    return [monday + timedelta(days=i) for i in range(7)]

def ensure_dates_exist(df: pd.DataFrame, dates: list[date]) -> pd.DataFrame:
    """해당 주의 날짜 행이 df에 없으면 빈 값으로 추가"""
    existing = set(pd.to_datetime(df["date"], errors="coerce").dt.date.dropna().tolist())
    rows_to_add = []
    for d in dates:
        if d not in existing:
            row = {"date": d.strftime(DATE_FMT)}
            for r in ROWS:
                row[r] = ""
            rows_to_add.append(row)
    if rows_to_add:
        df = pd.concat([df, pd.DataFrame(rows_to_add)], ignore_index=True)
    return df

def to_week_matrix(df_week: pd.DataFrame, dates: list[date]) -> pd.DataFrame:
    """행=항목, 열=날짜 문자열 로 테이블 구성"""
    cols = [d.strftime(DATE_FMT) for d in dates]
    mat = pd.DataFrame(index=ROWS, columns=cols, dtype=object)
    for d in dates:
        ds = d.strftime(DATE_FMT)
        row = df_week.loc[df_week["date"] == ds]
        if not row.empty:
            row = row.iloc[0]
            for r in ROWS:
                mat.at[r, ds] = row.get(r, "")
    return mat

def apply_matrix_to_df(df: pd.DataFrame, edited_mat: pd.DataFrame):
    """수정된 주간 매트릭스를 원본 df에 반영"""
    df = df.copy()
    for ds in edited_mat.columns:
        # 이 날짜 행이 없으면 추가
        if not ((df["date"] == ds).any()):
            new_row = {"date": ds}
            for r in ROWS:
                new_row[r] = edited_mat.at[r, ds] if (r in edited_mat.index) else ""
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        else:
            idx = df.index[df["date"] == ds][0]
            for r in ROWS:
                df.at[idx, r] = edited_mat.at[r, ds] if (r in edited_mat.index) else df.at[idx, r]
    return df

# =========================
# 화면
# =========================
st.title("📅 데일리 로그 – 주간 표(행=항목, 열=날짜)")

# 좌측: 주 선택 + 이동
with st.sidebar:
    st.header("주 선택")
    today = date.today()
    default_monday = get_monday(today)
    picked = st.date_input("주 기준일(아무 날짜나 선택)", today)
    monday = get_monday(picked)

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("◀ 지난주"):
            monday = monday - timedelta(days=7)
    with col_b:
        st.write("")
    with col_c:
        if st.button("다음주 ▶"):
            monday = monday + timedelta(days=7)

    st.caption(f"표 기간: {monday.strftime(DATE_FMT)} ~ {(monday+timedelta(days=6)).strftime(DATE_FMT)}")

# 로그 불러오기 & 주간 데이터 준비
df = load_log()
dates = week_dates(monday)
df = ensure_dates_exist(df, dates)

# 이번 주만 필터
mask = pd.to_datetime(df["date"], errors="coerce").dt.date.isin(dates)
df_week = df[mask].copy()

# 주간 표 생성 (행=항목, 열=날짜)
mat = to_week_matrix(df_week, dates)

st.subheader("📝 주간 입력 표 (수정 가능)")
st.caption("셀을 직접 수정 후 아래 ‘저장’ 버튼을 눌러 반영하세요.")

edited = st.data_editor(
    mat,
    use_container_width=True,
    height=480,
    num_rows="fixed",
    key=f"week_table_{monday}",
)

# 저장/내보내기
col1, col2, col3 = st.columns([1,1,2])
with col1:
    if st.button("💾 저장하기", type="primary"):
        df_updated = apply_matrix_to_df(df, edited)
        save_log(df_updated)
        st.success("저장 완료!")
with col2:
    if st.download_button(
        "⬇️ CSV 다운로드",
        data=df.to_csv(index=False, encoding="utf-8-sig"),
        file_name="weekly_log_export.csv",
        mime="text/csv",
    ):
        pass
with col3:
    st.info("팁: ‘두통’ 같은 항목은 ‘O/X’ 또는 자유 입력으로 기록하세요. 수면/에너지 등은 숫자(예: 7h, 3/5)도 좋아요.")

# 오늘 빠르게 입력(옵션)
with st.expander("⚡ 오늘 빠른 입력"):
    ds = today.strftime(DATE_FMT)
    quick = {}
    for r in ROWS:
        quick[r] = st.text_input(r, key=f"quick_{r}")
    if st.button("오늘 항목 반영"):
        if (df["date"] == ds).any():
            idx = df.index[df["date"] == ds][0]
        else:
            idx = len(df)
            df.loc[idx, "date"] = ds
        for r in ROWS:
            df.loc[idx, r] = quick[r]
        save_log(df)
        st.success("오늘 기록 반영 완료!")
