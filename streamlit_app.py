import streamlit as st
import pandas as pd
from datetime import date, timedelta
import json, os

st.set_page_config(page_title="데일리 로그 (보드형 UI)", layout="wide")

# =========================
# 설정
# =========================
LOG_FILE = "weekly_log.csv"
DATE_FMT = "%Y-%m-%d"

ROWS = [
    "오늘의 할일", "오늘의 성취",
    "기분", "에너지", "수면", "식욕",
    "집중력", "가장 미룬일", "두통", "특이사항", "감정한줄일기"
]
NUMERIC_1_5 = ["기분", "에너지"]     # 평균 대상
TASKS_COL = "오늘의 할일"            # 체크리스트 JSON

MOOD_LABELS = {1:"😞", 2:"😐", 3:"🙂", 4:"😊", 5:"🤩"}
ENERGY_LABELS = {1:"⚡×", 2:"⚡", 3:"⚡⚡", 4:"⚡⚡⚡", 5:"🚀"}

# =========================
# 유틸
# =========================
def load_log():
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE, dtype=str, encoding="utf-8-sig")
        if "date" not in df.columns:
            df["date"] = ""
        # 누락 컬럼 보정
        for r in ROWS:
            if r not in df.columns:
                df[r] = "" if r != TASKS_COL else "[]"
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

def parse_tasks(cell: str):
    if not cell or pd.isna(cell): return []
    try:
        data = json.loads(cell)
        if isinstance(data, list):
            if data and isinstance(data[0], str):
                return [{"task": t, "done": False} for t in data]
            return data
    except Exception:
        pass
    parts = [p.strip() for p in str(cell).split(";") if p.strip()]
    return [{"task": p, "done": False} for p in parts]

def dump_tasks(tasks: list[dict]) -> str:
    cleaned = [t for t in tasks if str(t.get("task", "")).strip() != ""]
    return json.dumps(cleaned, ensure_ascii=False)

def coerce_1_5(x):
    try:
        v = int(float(str(x).strip()))
        return v if 1 <= v <= 5 else None
    except Exception:
        return None

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

def week_month_avg(df: pd.DataFrame, monday: date, ref_day: date):
    dfx = df.copy()
    for col in NUMERIC_1_5:
        dfx[col] = dfx[col].apply(coerce_1_5)
    dfx["d"] = pd.to_datetime(dfx["date"], errors="coerce").dt.date

    week_set = set(week_dates(monday))
    week_df = dfx[dfx["d"].isin(week_set)]

    month_start = date(ref_day.year, ref_day.month, 1)
    next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    month_end = next_month - timedelta(days=1)
    month_df = dfx[(dfx["d"] >= month_start) & (dfx["d"] <= month_end)]

    def _avg(frame):
        res = {}
        for col in NUMERIC_1_5:
            series = pd.to_numeric(frame[col], errors="coerce")
            res[col] = round(series.mean(), 2) if series.notna().any() else None
        return res
    return _avg(week_df), _avg(month_df), month_start, month_end

# =========================
# UI
# =========================
st.title("📒 데일리 로그 – 보기 편한 보드 UI")

today = date.today()
with st.sidebar:
    st.header("주 선택 / 이동")
    picked = st.date_input("주 기준일", today)
    monday = get_monday(picked)

    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("◀ 지난주"):
            monday = monday - timedelta(days=7)
    with c2: st.write("")
    with c3:
        if st.button("다음주 ▶"):
            monday = monday + timedelta(days=7)

    st.caption(f"기간: {monday.strftime(DATE_FMT)} ~ {(monday+timedelta(days=6)).strftime(DATE_FMT)}")

# 데이터 준비
df = load_log()
dates = week_dates(monday)
df = ensure_dates_exist(df, dates)
mask = pd.to_datetime(df["date"], errors="coerce").dt.date.isin(dates)
df_week = df[mask].copy()

tab1, tab2, tab3 = st.tabs(["🧱 주간 보드", "📋 주간 표", "📊 통계"])

# ---- TAB 1: 주간 보드(카드형) ----
with tab1:
    st.caption("하루를 카드처럼 빠르게 입력합니다. 필요 항목만 최소 입력!")
    # 7일을 3열 그리드로 배치
    cols = st.columns(3)
    for i, d in enumerate(dates):
        ds = d.strftime(DATE_FMT)
        if (df["date"] == ds).any():
            idx = df.index[df["date"] == ds][0]
        else:
            idx = len(df); df.loc[idx, "date"] = ds
            for r in ROWS: df.loc[idx, r] = "" if r != TASKS_COL else "[]"

        with cols[i % 3]:
            with st.container(border=True):
                st.markdown(f"### {d.strftime('%m/%d (%a)')}")
                # 1~5 입력(라디오) – 이모지 라벨
                cc1, cc2 = st.columns(2)
                with cc1:
                    mood_init = coerce_1_5(df.loc[idx, "기분"]) or 3
                    mood = st.radio(
                        "기분",
                        options=[1,2,3,4,5],
                        format_func=lambda x: f"{x} {MOOD_LABELS[x]}",
                        horizontal=True,
                        index=[1,2,3,4,5].index(mood_init),
                        key=f"mood_{ds}"
                    )
                with cc2:
                    energy_init = coerce_1_5(df.loc[idx, "에너지"]) or 3
                    energy = st.radio(
                        "에너지",
                        options=[1,2,3,4,5],
                        format_func=lambda x: f"{x} {ENERGY_LABELS[x]}",
                        horizontal=True,
                        index=[1,2,3,4,5].index(energy_init),
                        key=f"energy_{ds}"
                    )

                # 체크리스트(간단 입력)
                tasks = parse_tasks(df.loc[idx, TASKS_COL])
                st.markdown("**오늘의 할일**")
                # 간단 리스트 형태로 표시/체크
                new_tasks = []
                # 기존 항목
                for t_i, item in enumerate(tasks):
                    colx, coly = st.columns([0.15, 0.85])
                    with colx:
                        done_val = st.checkbox("", value=bool(item.get("done", False)), key=f"done_{ds}_{t_i}")
                    with coly:
                        task_txt = st.text_input("", value=str(item.get("task","")), key=f"task_{ds}_{t_i}", label_visibility="collapsed")
                    new_tasks.append({"task": task_txt, "done": done_val})
                # 새 항목 한 줄
                add_txt = st.text_input("새 할일 추가", "", key=f"add_{ds}")
                if add_txt.strip():
                    new_tasks.append({"task": add_txt.strip(), "done": False})

                # 간단 메모(핵심만)
                cc3, cc4 = st.columns(2)
                with cc3:
                    headache = st.selectbox("두통", ["", "O", "X"], index=["","O","X"].index(str(df.loc[idx, "두통"]) if str(df.loc[idx, "두통"]) in ["","O","X"] else ""), key=f"head_{ds}")
                with cc4:
                    sleep = st.text_input("수면(예: 7h/6.5h)", value=str(df.loc[idx, "수면"]), key=f"sleep_{ds}")

                note = st.text_area("감정 한 줄 일기", value=str(df.loc[idx, "감정한줄일기"]), key=f"memo_{ds}", height=80)

                if st.button("저장", key=f"save_{ds}", use_container_width=True, type="primary"):
                    df.loc[idx, "기분"] = str(mood)
                    df.loc[idx, "에너지"] = str(energy)
                    df.loc[idx, TASKS_COL] = dump_tasks(new_tasks)
                    df.loc[idx, "두통"] = headache
                    df.loc[idx, "수면"] = sleep
                    df.loc[idx, "감정한줄일기"] = note
                    save_log(df)
                    st.success("저장 완료")

# ---- TAB 2: 주간 표(일괄 편집) ----
with tab2:
    st.caption("전체 항목을 표로 일괄 수정하고 싶을 때 사용하세요.")
    mat = to_week_matrix(df_week, dates)
    edited = st.data_editor(
        mat,
        use_container_width=True,
        height=500,
        num_rows="fixed",
        column_config={  # 최소한의 가독성 향상
            # 날짜별 셀 폭 자동, 편집은 자유 입력
        },
        key=f"table_{monday}"
    )
    if st.button("💾 표 저장", type="primary"):
        df_updated = apply_matrix_to_df(df, edited)
        save_log(df_updated)
        st.success("저장 완료!")
        df = df_updated

    st.download_button(
        "⬇️ CSV 다운로드",
        data=df.to_csv(index=False, encoding="utf-8-sig"),
        file_name="weekly_log_export.csv",
        mime="text/csv"
    )

# ---- TAB 3: 통계(주/월 평균) ----
with tab3:
    wk_avg, mo_avg, mstart, mend = week_month_avg(df, monday, today)
    st.markdown("### 1~5 평균")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("이번주 평균 기분", wk_avg.get("기분") if wk_avg.get("기분") is not None else "-")
    with c2:
        st.metric("이번주 평균 에너지", wk_avg.get("에너지") if wk_avg.get("에너지") is not None else "-")
    with c3:
        st.metric(f"{today.strftime('%Y-%m')} 평균 기분", mo_avg.get("기분") if mo_avg.get("기분") is not None else "-")
    with c4:
        st.metric(f"{today.strftime('%Y-%m')} 평균 에너지", mo_avg.get("에너지") if mo_avg.get("에너지") is not None else "-")
    st.caption(f"월 범위: {mstart.strftime(DATE_FMT)} ~ {mend.strftime(DATE_FMT)}")

    # 체크리스트 완료율(이번주)
    st.markdown("### 이번주 체크리스트 완료율")
    week_dates_str = [d.strftime(DATE_FMT) for d in dates]
    sub = df[df["date"].isin(week_dates_str)].copy()
    def done_ratio(cell):
        items = parse_tasks(cell)
        if not items: return None
        total = len(items)
        done = sum(1 for x in items if x.get("done"))
        return round(done/total, 2) if total > 0 else None
    sub["완료율"] = sub[TASKS_COL].apply(done_ratio)
    st.dataframe(sub[["date", "완료율"]].rename(columns={"date":"날짜"}), use_container_width=True)
