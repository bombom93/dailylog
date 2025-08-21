import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
import json, os

st.set_page_config(page_title="데일리로그(주간+평균+체크리스트)", layout="wide")

# =========================
# 설정
# =========================
LOG_FILE = "weekly_log.csv"   # CSV 저장 (개인용)
DATE_FMT = "%Y-%m-%d"

ROWS = [
    "오늘의 할일", "오늘의 성취",
    "기분", "에너지", "수면", "식욕",
    "집중력", "가장 미룬일", "두통", "특이사항", "감정한줄일기"
]
NUMERIC_1_5 = ["기분", "에너지"]           # 1~5 평균 대상
TASKS_COL = "오늘의 할일"                  # 체크리스트는 JSON으로 저장

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
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime(DATE_FMT)
    df.to_csv(LOG_FILE, index=False, encoding="utf-8-sig")

def get_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())  # 월=0

def week_dates(monday: date):
    return [monday + timedelta(days=i) for i in range(7)]

def ensure_dates_exist(df: pd.DataFrame, dates: list[date]) -> pd.DataFrame:
    existing = set(pd.to_datetime(df["date"], errors="coerce").dt.date.dropna().tolist())
    add_rows = []
    for d in dates:
        if d not in existing:
            row = {"date": d.strftime(DATE_FMT)}
            for r in ROWS:
                row[r] = "" if r != TASKS_COL else "[]"
            add_rows.append(row)
    if add_rows:
        df = pd.concat([df, pd.DataFrame(add_rows)], ignore_index=True)
    return df

def to_week_matrix(df_week: pd.DataFrame, dates: list[date]) -> pd.DataFrame:
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
    df = df.copy()
    for ds in edited_mat.columns:
        if not (df["date"] == ds).any():
            new_row = {"date": ds}
            for r in ROWS:
                val = edited_mat.at[r, ds] if (r in edited_mat.index) else ""
                if r == TASKS_COL and (val is None or val == ""):
                    val = "[]"
                new_row[r] = str(val) if val is not None else ""
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        else:
            idx = df.index[df["date"] == ds][0]
            for r in ROWS:
                val = edited_mat.at[r, ds] if (r in edited_mat.index) else df.at[idx, r]
                if r == TASKS_COL and (val is None or val == ""):
                    val = "[]"
                df.at[idx, r] = str(val) if val is not None else ""
    return df

def parse_tasks(cell: str):
    """오늘의 할일 셀(JSON)을 파싱해 리스트[{'task': str, 'done': bool}] 반환"""
    if not cell or pd.isna(cell):
        return []
    try:
        data = json.loads(cell)
        if isinstance(data, list):
            # 문자열 목록만 저장돼 있었다면 변환
            if data and isinstance(data[0], str):
                return [{"task": t, "done": False} for t in data]
            return data
    except Exception:
        pass
    # 세미콜론 분리 등 구버전 호환
    parts = [p.strip() for p in str(cell).split(";") if p.strip()]
    return [{"task": p, "done": False} for p in parts]

def dump_tasks(tasks: list[dict]) -> str:
    # 비어있거나 task가 빈 줄인 것은 제거
    cleaned = [t for t in tasks if str(t.get("task", "")).strip() != ""]
    return json.dumps(cleaned, ensure_ascii=False)

def coerce_1_5(x):
    """문자/빈칸 → 1~5 숫자 또는 None"""
    try:
        v = int(float(str(x).strip()))
        return v if 1 <= v <= 5 else None
    except Exception:
        return None

def week_month_avg(df: pd.DataFrame, monday: date, today_dt: date):
    # 숫자 컬럼만 뽑아서 1~5로 캐스팅
    dfx = df.copy()
    for col in NUMERIC_1_5:
        dfx[col] = dfx[col].apply(coerce_1_5)

    # 주간 범위
    week_set = set(week_dates(monday))
    dfx["d"] = pd.to_datetime(dfx["date"], errors="coerce").dt.date
    week_df = dfx[dfx["d"].isin(week_set)]

    # 월간 범위(선택: 오늘 기준 month)
    month_start = date(today_dt.year, today_dt.month, 1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_end = next_month - timedelta(days=1)
    month_mask = (dfx["d"] >= month_start) & (dfx["d"] <= month_end)
    month_df = dfx[month_mask]

    def _avg(frame):
        res = {}
        for col in NUMERIC_1_5:
            series = pd.to_numeric(frame[col], errors="coerce")
            mean = series.mean() if not series.dropna().empty else None
            res[col] = round(float(mean), 2) if mean is not None else None
        return res

    return _avg(week_df), _avg(month_df), month_start, month_end

# =========================
# 화면
# =========================
st.title("📅 데일리 로그 – 주간 표 + 평균 + 체크리스트")

today = date.today()

# ---- 사이드바: 주 선택/이동 ----
with st.sidebar:
    st.header("주 선택")
    picked = st.date_input("주 기준일(아무 날짜나 선택)", today)
    monday = get_monday(picked)

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("◀ 지난주"):
            monday = monday - timedelta(days=7)
    with c2:
        st.write("")
    with c3:
        if st.button("다음주 ▶"):
            monday = monday + timedelta(days=7)

    st.caption(f"표 기간: {monday.strftime(DATE_FMT)} ~ {(monday+timedelta(days=6)).strftime(DATE_FMT)}")

# ---- 데이터 로드/보정 ----
df = load_log()
dates = week_dates(monday)
df = ensure_dates_exist(df, dates)

mask = pd.to_datetime(df["date"], errors="coerce").dt.date.isin(dates)
df_week = df[mask].copy()

# ---- 주간 표(행=항목, 열=날짜) ----
mat = to_week_matrix(df_week, dates)
st.subheader("📝 주간 입력 표 (셀 직접 수정)")
st.caption("‘기분/에너지’는 1~5 숫자로 입력하세요. 저장해야 반영됩니다.")
edited = st.data_editor(
    mat,
    use_container_width=True,
    height=420,
    num_rows="fixed",
    key=f"week_table_{monday}"
)

c_save, c_dl = st.columns([1,1])
with c_save:
    if st.button("💾 저장하기", type="primary"):
        df_updated = apply_matrix_to_df(df, edited)
        save_log(df_updated)
        st.success("저장 완료!")
        df = df_updated  # 후속 카드 갱신을 위해
with c_dl:
    st.download_button(
        "⬇️ CSV 다운로드",
        data=df.to_csv(index=False, encoding="utf-8-sig"),
        file_name="weekly_log_export.csv",
        mime="text/csv",
    )

# ---- 평균 카드 ----
wk_avg, mo_avg, mstart, mend = week_month_avg(df, monday, today)
st.subheader("📊 주·월 평균 (1~5)")
cc1, cc2, cc3, cc4 = st.columns(4)
with cc1:
    st.metric("이번주 평균 기분", wk_avg.get("기분") if wk_avg.get("기분") is not None else "-")
with cc2:
    st.metric("이번주 평균 에너지", wk_avg.get("에너지") if wk_avg.get("에너지") is not None else "-")
with cc3:
    st.metric(f"{today.strftime('%Y-%m')} 평균 기분", mo_avg.get("기분") if mo_avg.get("기분") is not None else "-")
with cc4:
    st.metric(f"{today.strftime('%Y-%m')} 평균 에너지", mo_avg.get("에너지") if mo_avg.get("에너지") is not None else "-")
st.caption(f"월 범위: {mstart.strftime(DATE_FMT)} ~ {mend.strftime(DATE_FMT)}")

# ---- 오늘 빠른 입력: 1~5 + 체크리스트 ----
st.subheader("⚡ 오늘 빠른 입력(1~5 + 체크리스트)")
ds = today.strftime(DATE_FMT)

# 오늘 행 확보
if (df["date"] == ds).any():
    idx_today = df.index[df["date"] == ds][0]
else:
    idx_today = len(df)
    df.loc[idx_today, "date"] = ds
    for r in ROWS:
        df.loc[idx_today, r] = "" if r != TASKS_COL else "[]"

# 1~5 슬라이더
col_a, col_b = st.columns(2)
with col_a:
    mood = st.slider("기분 (1~5)", min_value=1, max_value=5, value=coerce_1_5(df.loc[idx_today, "기분"]) or 3, step=1)
with col_b:
    energy = st.slider("에너지 (1~5)", min_value=1, max_value=5, value=coerce_1_5(df.loc[idx_today, "에너지"]) or 3, step=1)

# 체크리스트 편집
tasks = parse_tasks(df.loc[idx_today, TASKS_COL] if TASKS_COL in df.columns else "[]")
task_df = pd.DataFrame(tasks if tasks else [{"task": "", "done": False}])

task_df = st.data_editor(
    task_df,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "task": st.column_config.TextColumn("할 일"),
        "done": st.column_config.CheckboxColumn("완료")
    },
    key="tasks_today"
)

# 반영 버튼
if st.button("오늘 기록 반영"):
    df.loc[idx_today, "기분"] = str(mood)
    df.loc[idx_today, "에너지"] = str(energy)
    df.loc[idx_today, TASKS_COL] = dump_tasks(task_df.to_dict(orient="records"))
    save_log(df)
    st.success("오늘 기록 저장 완료!")

# ---- (옵션) 오늘 체크리스트 요약 ----
with st.expander("☑️ 오늘 할일 요약"):
    done_cnt = int(task_df["done"].sum()) if "done" in task_df.columns else 0
    total_cnt = int(len(task_df.index))
    st.write(f"완료 {done_cnt} / 총 {total_cnt}")
    if total_cnt:
        st.progress(done_cnt / total_cnt)
