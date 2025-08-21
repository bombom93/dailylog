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

# ⛏️ 오늘의 할일 제거: ROWS에서 삭제
ROWS = [
    "오늘의 성취",
    "기분", "에너지", "수면", "식욕",
    "집중력", "가장 미룬일", "두통", "특이사항", "감정한줄일기"
]
NUMERIC_1_5 = ["기분", "에너지"]  # 필요시 "식욕" 추가 가능

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
        # 누락 컬럼 보강
        for r in ROWS:
            if r not in df.columns:
                df[r] = ""
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
                row[r] = ""
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

def day_row(df: pd.DataFrame, d: date):
    ds = d.strftime(DATE_FMT)
    if (df["date"] == ds).any():
        idx = df.index[df["date"] == ds][0]
    else:
        idx = len(df)
        df.loc[idx, "date"] = ds
        for r in ROWS:
            df.loc[idx, r] = ""
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

# =========================
# 사이드바: 2025 / 월(라디오) / 주(슬라이더) + 오늘 버튼
# =========================
def iso_last_week(year: int) -> int:
    # ISO 마지막 주 — 12/28이 항상 마지막 ISO 주에 포함
    return date(year, 12, 28).isocalendar().week

today = date.today()
max_week = iso_last_week(year_sel)

# --- 라디오(월) 동일 너비 CSS ---
st.markdown("""
<style>
/* 라디오 전체 가로 정렬 + 줄바꿈 */
div[role="radiogroup"]{display:flex;flex-wrap:wrap;gap:6px}
/* 각 라벨(필)을 동일 너비로 */
div[role="radiogroup"] > label{
  flex: 0 0 56px;              /* 👈 동일 너비 */
  justify-content:center;
  border-radius:999px !important;
  white-space:nowrap;
}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("보기 기준")

    # 월: 가로 라디오(필)
    st.markdown("##### 월 선택")
    default_month = today.month if today.year == year_sel else 1
    month_sel = int(st.session_state.get("month_sel", default_month))
    month_sel = st.radio(
        "월 선택",
        options=list(range(1, 12+1)),
        index=month_sel - 1,
        format_func=lambda m: f"{m}월",
        horizontal=True,
        label_visibility="collapsed",
        key="month_radio",
    )
    st.session_state["month_sel"] = month_sel

    st.divider()

    # 주: 슬라이더
    st.markdown("##### 주 선택")
    default_week = min(today.isocalendar().week, max_week) if today.year == year_sel else 1
    week_sel = int(st.session_state.get("week_sel", default_week))
    week_sel = st.slider(
        "주 선택",
        min_value=1, max_value=max_week, value=week_sel, step=1,
        label_visibility="collapsed",
        key="week_slider",
    )
    st.session_state["week_sel"] = week_sel

    # ── 오늘 기준으로 즉시 맞추는 버튼들 ──
    bcol1, bcol2 = st.columns(2)
    if bcol1.button("오늘 기준 월 선택", use_container_width=True):
        st.session_state["month_sel"] = today.month
        st.rerun()
    if bcol2.button("오늘 기준 주 선택", use_container_width=True):
        st.session_state["week_sel"] = min(today.isocalendar().week, max_week)
        st.rerun()

# 선택한 주의 월요일 계산(페이지 본문에서 사용)
monday = date.fromisocalendar(year_sel, st.session_state["week_sel"], 1)
st.caption(f"주 범위: {monday.strftime('%Y-%m-%d')} ~ {(monday + timedelta(days=6)).strftime('%Y-%m-%d')}")

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
        appetite = st.text_input("식욕", value=str(df.loc[idx, "식욕"]))
    with cols[4]:
        concentrate = st.text_input("집중력", value=str(df.loc[idx, "집중력"]))
    with cols[5]:
        postpone = st.text_input("가장 미룬일", value=str(df.loc[idx, "가장 미룬일"]))
    with cols[6]:
        headache = st.text_input("두통", value=str(df.loc[idx, "두통"]))

    achv = st.text_input("오늘의 성취", value=str(df.loc[idx, "오늘의 성취"]))
    special = st.text_input("특이사항", value=str(df.loc[idx, "특이사항"]))
    memo = st.text_area("감정 한 줄 일기", value=str(df.loc[idx, "감정한줄일기"]), height=100)

    if st.button("💾 오늘 저장", type="primary", use_container_width=True):
        df.loc[idx, "기분"] = str(mood)
        df.loc[idx, "에너지"] = str(energy)
        df.loc[idx, "식욕"] = appetite
        df.loc[idx, "두통"] = headache
        df.loc[idx, "수면"] = sleep
        df.loc[idx, "오늘의 성취"] = achv
        df.loc[idx, "가장 미룬일"] = postpone
        df.loc[idx, "특이사항"] = special
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
        idx = day_row(df, d)
        with cols[i % 7]:
            with st.container(border=True):
                st.markdown(f"**{d.strftime('%m/%d (%a)')}**")
                mood = coerce_1_5(df.loc[idx, "기분"]) or "-"
                energy = coerce_1_5(df.loc[idx, "에너지"]) or "-"
                # 식욕을 1~5로 관리 중이면 출력에 활용 가능
                # app = coerce_1_5(df.loc[idx, "식욕"]) or "-"

                st.write(f"기분: {mood if mood=='-' else str(mood)+' '+MOOD_LABELS[mood]}")
                st.write(f"에너지: {energy if energy=='-' else str(energy)+' '+ENERGY_LABELS[energy]}")

                # 안전한 캡션 슬라이싱
                raw = df.loc[idx, "감정한줄일기"]
                text = "" if pd.isna(raw) else str(raw)
                st.caption(text[:40] + ("..." if len(text) > 40 else ""))

# ---------------------------------------------------
# 3) 월별 모아보기 (7열 카드, 해당 월만)
# ---------------------------------------------------
with tab3:
    st.subheader(f"월별 모아보기 – {int(year_sel)}-{int(month_sel):02d}")
    dates_month = month_dates(int(year_sel), int(month_sel))

    cols = st.columns(7)
    for i, d in enumerate(dates_month):
        ds = d.strftime(DATE_FMT)
        if (df["date"] == ds).any():
            idx = df.index[df["date"] == ds][0]
            mood = coerce_1_5(df.loc[idx, "기분"]) or "-"
            energy = coerce_1_5(df.loc[idx, "에너지"]) or "-"
            raw = df.loc[idx, "감정한줄일기"]
            memo = "" if pd.isna(raw) else str(raw)
        else:
            mood = energy = "-"
            memo = ""

        with cols[i % 7]:
            with st.container(border=True):
                st.markdown(f"**{d.strftime('%m/%d (%a)')}**")
                st.write(f"기분: {mood if mood=='-' else str(mood)+' '+MOOD_LABELS[mood]}")
                st.write(f"에너지: {energy if energy=='-' else str(energy)+' '+ENERGY_LABELS[energy]}")
                st.caption(memo[:40] + ("..." if len(memo) > 40 else ""))

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
