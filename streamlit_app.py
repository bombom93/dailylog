import streamlit as st
import pandas as pd
from datetime import date, timedelta, datetime
import calendar, json, os

st.set_page_config(page_title="데일리 로그", layout="wide")

# =========================
# 로그인 (st.rerun 사용)
# =========================
def login_required():
    if st.session_state.get("authed", False):
        return

    st.markdown("### 🔐 로그인")
    required_user = st.secrets.get("APP_USERNAME", None)
    pwd = st.text_input("비밀번호", type="password")
    user_ok = True
    if required_user:
        user = st.text_input("아이디")
        user_ok = (user == required_user)

    if st.button("로그인", type="primary", use_container_width=True):
        if user_ok and pwd == st.secrets.get("APP_PASSWORD", ""):
            st.session_state["authed"] = True
            st.rerun()
        else:
            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
    st.stop()

def logout_button():
    with st.sidebar:
        if st.session_state.get("authed", False) and st.button("로그아웃"):
            st.session_state.clear()
            st.rerun()

login_required()
logout_button()

# =========================
# 기본 설정
# =========================
LOG_FILE = "weekly_log.csv"
DATE_FMT = "%Y-%m-%d"

ROWS = [
    "오늘의 할일", "오늘의 성취",
    "기분", "에너지", "수면", "식욕",
    "집중력", "가장 미룬일", "두통", "특이사항", "감정한줄일기"
]
NUMERIC_1_5 = ["기분", "에너지"]  # 통계용 (원하면 "식욕" 추가 가능)
TASKS_COL = "오늘의 할일"

MOOD_LABELS   = {1:"😞", 2:"😐", 3:"🙂", 4:"😊", 5:"🤩"}
ENERGY_LABELS = {1:"⚡×", 2:"⚡", 3:"⚡⚡", 4:"⚡⚡⚡", 5:"🚀"}
APP_LABELS    = {1:"🍽×", 2:"🍽", 3:"🍽🍽", 4:"🍽🍽🍽", 5:"🍱"}

# =========================
# 유틸
# =========================
def load_log():
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE, dtype=str, encoding="utf-8-sig")
        if "date" not in df.columns:
            df["date"] = ""
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

def coerce_1_5(x):
    try:
        v = int(float(str(x).strip()))
        return v if 1 <= v <= 5 else None
    except Exception:
        return None

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

def day_row(df: pd.DataFrame, d: date):
    ds = d.strftime(DATE_FMT)
    if (df["date"] == ds).any():
        idx = df.index[df["date"] == ds][0]
    else:
        idx = len(df)
        df.loc[idx, "date"] = ds
        for r in ROWS:
            df.loc[idx, r] = "" if r != TASKS_COL else "[]"
    return idx

def month_dates(year: int, month: int):
    last_day = calendar.monthrange(year, month)[1]
    return [date(year, month, i) for i in range(1, last_day+1)]

def stats_week_month(df: pd.DataFrame, monday: date, ref_day: date):
    dfx = df.copy()
    for col in NUMERIC_1_5:
        dfx[col] = dfx[col].apply(coerce_1_5)
    dfx["d"] = pd.to_datetime(dfx["date"], errors="coerce").dt.date

    week_set = set(week_dates(monday))
    week_df = dfx[dfx["d"].isin(week_set)]

    mstart = date(ref_day.year, ref_day.month, 1)
    next_m = (mstart.replace(day=28) + timedelta(days=4)).replace(day=1)
    mend = next_m - timedelta(days=1)
    month_df = dfx[(dfx["d"] >= mstart) & (dfx["d"] <= mend)]

    def _avg(frame):
        res = {}
        for col in NUMERIC_1_5:
            s = pd.to_numeric(frame[col], errors="coerce")
            res[col] = round(s.mean(), 2) if s.notna().any() else None
        return res

    return _avg(week_df), _avg(month_df), mstart, mend

def done_ratio(cell):
    items = parse_tasks(cell)
    if not items: return None
    tot = len(items); done = sum(1 for x in items if x.get("done"))
    return round(done/tot, 2) if tot else None

# =========================
# 사이드바: 주/월 선택
# =========================
today = date.today()
with st.sidebar:
    st.header("보기 기준")
    # 주
    picked_for_week = st.date_input("주 기준일", today, key="week_pick")
    monday = get_monday(picked_for_week)
    st.caption(f"주 범위: {monday.strftime(DATE_FMT)} ~ {(monday+timedelta(days=6)).strftime(DATE_FMT)}")

    # 월
    col_y, col_m = st.columns(2)
    with col_y:
        year_sel = st.number_input("연도", min_value=2000, max_value=2100, value=today.year, step=1)
    with col_m:
        month_sel = st.number_input("월", min_value=1, max_value=12, value=today.month, step=1)

# 데이터 로드 및 해당 기간 확보
df = load_log()
df = ensure_dates_exist(df, week_dates(monday))  # 주간 날짜 없으면 생성

# =========================
# 탭 4개
# =========================
tab1, tab2, tab3, tab4 = st.tabs(["📝 오늘거 작성", "📅 주별 모아보기", "🗓️ 월별 모아보기", "📊 기분/에너지 통계"])

# ---------------------------------------------------
# 1) 오늘거 작성
# ---------------------------------------------------
with tab1:
    st.subheader(f"오늘({today.strftime('%Y-%m-%d %a')}) 기록")
    idx = day_row(df, today)
    cols = st.columns(7)  # 한 줄 고정 레이아웃 느낌 유지

    with cols[0]:
        mood_init = coerce_1_5(df.loc[idx, "기분"]) or 3
        mood = st.radio("기분", [1,2,3,4,5],
                        format_func=lambda x: f"{x} {MOOD_LABELS[x]}",
                        horizontal=True, index=[1,2,3,4,5].index(mood_init))
    with cols[1]:
        energy_init = coerce_1_5(df.loc[idx, "에너지"]) or 3
        energy = st.radio("에너지", [1,2,3,4,5],
                          format_func=lambda x: f"{x} {ENERGY_LABELS[x]}",
                          horizontal=True, index=[1,2,3,4,5].index(energy_init))

    with cols[2]:
        sleep = st.text_input("수면", value=str(df.loc[idx, "수면"]))
    with cols[3]:
        appetite = st.text_input("식욕",value=str(df.loc[idx, "식욕"]))
    with cols[4]:
        concentrate = st.text_input("집중력", value=str(df.loc[idx, "집중력"]))
    with cols[5]:
        postpone = st.text_input("가장 미룬일", value=str(df.loc[idx, "가장 미룬일"]))
    with cols[6]:
        headache = st.text_input("두통",value=str(df.loc[idx, "두통"]))
    
    achv = st.text_input("오늘의 성취", value=str(df.loc[idx, "오늘의 성취"]))
        
    special = st.text_input('특이사항',value = str(df.loc[idx,'특이사항']))

    memo = st.text_area("감정 한 줄 일기", value=str(df.loc[idx, "감정한줄일기"]), height=100)

    if st.button("💾 오늘 저장", type="primary", use_container_width=True):
        df.loc[idx, "기분"] = str(mood)
        df.loc[idx, "에너지"] = str(energy)
        df.loc[idx, "식욕"] = appetite
        df.loc[idx, "두통"] = headache
        df.loc[idx, "수면"] = sleep
        df.loc[idx, "오늘의 성취"] = achv
        df.loc[idx, "가장 미룬일"] = postpone
        df.loc[idx, TASKS_COL] = dump_tasks(new_tasks)
        df.loc[idx, "감정한줄일기"] = memo
        save_log(df)
        st.success("오늘 기록 저장 완료!")

# ---------------------------------------------------
# 2) 주별 모아보기 (7열 카드)
# ---------------------------------------------------
with tab2:
    st.subheader("주별 모아보기")
    dates_week = week_dates(monday)
    df_week = df[df["date"].isin([d.strftime(DATE_FMT) for d in dates_week])].copy()

    cols = st.columns(7)  # 한 줄에 7일
    for i, d in enumerate(dates_week):
        ds = d.strftime(DATE_FMT)
        # 보장
        idx = day_row(df, d)
        with cols[i % 7]:
            with st.container(border=True):
                st.markdown(f"**{d.strftime('%m/%d (%a)')}**")
                mood = coerce_1_5(df.loc[idx, "기분"]) or "-"
                energy = coerce_1_5(df.loc[idx, "에너지"]) or "-"
                app = coerce_1_5(df.loc[idx, "식욕"]) or "-"
                dr = done_ratio(df.loc[idx, TASKS_COL])
                st.write(f"기분: {mood if mood=='-' else str(mood)+' '+MOOD_LABELS[mood]}")
                st.write(f"에너지: {energy if energy=='-' else str(energy)+' '+ENERGY_LABELS[energy]}")
                st.write(f"체크리스트 완료율: {f'{int(dr*100)}%' if dr is not None else '-'}")
                st.caption(df.loc[idx, "감정한줄일기"][:40] + ("..." if len(str(df.loc[idx, '감정한줄일기']))>40 else ""))

# ---------------------------------------------------
# 3) 월별 모아보기 (7열 카드, 해당 월만)
# ---------------------------------------------------
with tab3:
    st.subheader(f"월별 모아보기 – {int(year_sel)}-{int(month_sel):02d}")
    dates_month = month_dates(int(year_sel), int(month_sel))
    # 월 데이터 보장(없으면 생성 X — 보기 전용이라 생성은 하지 않음)
    cols = st.columns(7)
    for i, d in enumerate(dates_month):
        ds = d.strftime(DATE_FMT)
        if (df["date"] == ds).any():
            idx = df.index[df["date"] == ds][0]
            mood = coerce_1_5(df.loc[idx, "기분"]) or "-"
            energy = coerce_1_5(df.loc[idx, "에너지"]) or "-"
            app = coerce_1_5(df.loc[idx, "식욕"]) or "-"
            dr = done_ratio(df.loc[idx, TASKS_COL])
            memo = str(df.loc[idx, "감정한줄일기"])
        else:
            mood = energy = app = "-"
            dr = None
            memo = ""
        with cols[i % 7]:
            with st.container(border=True):
                st.markdown(f"**{d.strftime('%m/%d (%a)')}**")
                st.write(f"기분: {mood if mood=='-' else str(mood)+' '+MOOD_LABELS[mood]}")
                st.write(f"에너지: {energy if energy=='-' else str(energy)+' '+ENERGY_LABELS[energy]}")
                st.write(f"체크리스트 완료율: {f'{int(dr*100)}%' if dr is not None else '-'}")
                st.caption(memo[:40] + ("..." if len(memo)>40 else ""))

# ---------------------------------------------------
# 4) 기분/에너지 통계
# ---------------------------------------------------
with tab4:
    st.subheader("기분/에너지 통계")
    wk_avg, mo_avg, mstart, mend = stats_week_month(df, monday, today)

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

    # 최근 30일 표(기분/에너지) – 추세 확인용
    st.markdown("#### 최근 30일 기록표")
    dfx = df.copy()
    dfx["날짜"] = pd.to_datetime(dfx["date"], errors="coerce")
    recent = dfx.sort_values("날짜", ascending=False).head(30)
    recent["기분"] = recent["기분"].apply(coerce_1_5)
    recent["에너지"] = recent["에너지"].apply(coerce_1_5)
    st.dataframe(recent[["날짜", "기분", "에너지", "감정한줄일기"]].fillna(""), use_container_width=True)
