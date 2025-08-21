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
APP_LABELS    = {1_
