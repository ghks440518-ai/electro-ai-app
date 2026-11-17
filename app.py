# app.py
import io
import os
import sys
from datetime import datetime
import pandas as pd
import streamlit as st

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.db_auth import (
    init_db, register_user, login_user, find_user_id, reset_user_password,
    send_otp_code, verify_otp_code, create_inquiry, get_all_inquiries, reply_inquiry,
)
from backend.i18n import LANGUAGES, t
from backend.kec_engine import ELEMENT_DB, DesignElementInput, search_elements, calculate_kec_and_cost
from backend.vision_blueprint import (
    prepare_image, create_sample_floorplan, run_ai_design_analysis,
    run_demo_design_analysis, render_2d_placement_blueprint, render_construction_electrical_diagram,
)

init_db()
st.set_page_config(page_title="홈전기 KEC AI 설계·견적", page_icon="⚡", layout="centered")

defaults = {
    "user": None, "lang": "ko", "step": 1, "view_mode": "app",
    "auth_page": "login", "auth_flash": "", "prefill_id": "",
    "floor_img": None, "ai_res": None, "img_res1": None, "img_res2": None, "cost_res": None,
    "otp_sent": False, "otp_verified": False, "otp_demo_code": None, "otp_target": "", "otp_method": "phone",
    "elements": [
        {"element_key": "tv", "room_hint": "거실", "mat_price": 18000, "qty": 1},
        {"element_key": "lighting", "room_hint": "거실", "mat_price": 45000, "qty": 1},
        {"element_key": "outlet", "room_hint": "안방", "mat_price": 8000, "qty": 2},
        {"element_key": "refrigerator", "room_hint": "주방", "mat_price": 10000, "qty": 1},
        {"element_key": "aircon", "room_hint": "거실", "mat_price": 15000, "qty": 1},
    ],
    "labor_per_person": 250000, "worker_count": 2, "work_days": 1.0,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

lang = st.session_state.lang
rtl_css = "direction: rtl; text-align: right;" if lang == "ar" else ""
max_w = "960px" if (st.session_state.user and st.session_state.view_mode == "admin") else "460px"

st.markdown(f"""
<style>
/* 상단 기본 Streamlit 헤더 제거로 위쪽 UI 잘림 완벽 방지 */
header[data-testid="stHeader"] {{
    display: none !important;
}}
div[data-testid="stMainBlockContainer"], .block-container {{
    max-width: min(96vw, {max_w}) !important;
    width: 100% !important;
    padding: 1.1rem 1rem 2rem 1rem !important;
    margin: 0.6rem auto 1.5rem auto !important;
    background-color: #F8FAFC;
    border-radius: 20px;
    box-shadow: 0 8px 26px rgba(15, 23, 42, 0.08);
    box-sizing: border-box !important;
    overflow-x: hidden !important;
    {rtl_css}
}}
.stButton > button, div[data-testid="stPopover"] > button {{
    font-size: 0.84rem !important;
    padding: 0.42rem 0.45rem !important;
    white-space: normal !important;
    word-break: keep-all !important;
    line-height: 1.25 !important;
}}
.hero-cost {{
    background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
    color: #fff; padding: 15px; border-radius: 14px; margin: 8px 0 12px 0;
}}
.hero-cost .won {{ font-size: 1.6rem; font-weight: 800; color: #38BDF8; margin: 4px 0; }}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 상단 바 (파란 타이틀 배너 제거, 옵션 톱니바퀴만 깔끔하게 우측 배치)
# ==========================================
top_l, top_r = st.columns([2.6, 1.4])
with top_l:
    if st.session_state.user is not None:
        u_info = st.session_state.user
        st.caption(f"👤 **{u_info['name']}** (`{u_info.get('username') or ''}`)")
with top_r:
    with st.popover("⚙️ 옵션", width="stretch"):
        st.markdown(f"**{t('lang_label', lang)}**")
        lang_keys = list(LANGUAGES.keys())
        sel_lang = st.selectbox(
            "언어", options=lang_keys, index=lang_keys.index(lang),
            format_func=lambda x: LANGUAGES[x], label_visibility="collapsed",
        )
        if sel_lang != st.session_state.lang:
            st.session_state.lang = sel_lang
            st.rerun()

        st.divider()
        st.markdown(f"**{t('inquiry_title', lang)}**")
        u = st.session_state.user
        inq_name = st.text_input("이름", value=(u["name"] if u else ""), key="inq_n")
        inq_contact = st.text_input("연락처/이메일", value=((u.get("phone") or u.get("email") or "") if u else ""), key="inq_c")
        inq_title = st.text_input("문의 제목", key="inq_t")
        inq_msg = st.text_area("문의 내용", height=80, key="inq_m")
        if st.button("📩 문의 전송", type="primary", width="stretch"):
            uid = (u.get("username") or u.get("email") or "guest") if u else "guest"
            ok, msg = create_inquiry(uid, inq_name, inq_contact, inq_title, inq_msg)
            st.success(msg) if ok else st.error(msg)

# ==========================================
# 0번: 로그인 / 회원가입 / ID찾기 / PW재설정
# ==========================================
if st.session_state.user is None:
    ap = st.session_state.auth_page

    if ap == "login":
        st.subheader(f"🔐 {t('login_tab', lang)}")
        if st.session_state.auth_flash:
            st.success(st.session_state.auth_flash)

        lid = st.text_input("아이디 (또는 전화번호 / 이메일)", value=st.session_state.prefill_id, placeholder="myid123 또는 01012345678")
        lpw = st.text_input(t("pw_label", lang), type="password")

        if st.button(t("login_tab", lang), type="primary", width="stretch"):
            ok, u_data, msg = login_user(lid, lpw)
            if ok:
                st.session_state.user = u_data
                st.session_state.auth_flash = ""
                st.session_state.prefill_id = ""
                st.session_state.view_mode = "admin" if u_data["role"] == "admin" else "app"
                st.rerun()
            else:
                st.error(msg)

        st.divider()
        b1, b2, b3 = st.columns(3)
        if b1.button(t("signup_tab", lang), width="stretch"):
            st.session_state.auth_page = "signup"
            st.session_state.auth_flash = ""
            st.rerun()
        if b2.button(t("find_id_tab", lang), width="stretch"):
            st.session_state.auth_page = "find_id"
            st.session_state.auth_flash = ""
            st.rerun()
        if b3.button(t("find_pw_tab", lang), width="stretch"):
            st.session_state.auth_page = "find_pw"
            st.session_state.auth_flash = ""
            st.rerun()

        st.caption("💡 관리자 테스트: `admin` / PW: `admin1234!`")

    elif ap == "signup":
        if st.button("⬅️ 로그인 화면으로 돌아가기"):
            st.session_state.auth_page = "login"
            st.rerun()

        st.subheader(f"📝 {t('signup_tab', lang)}")
        su_id = st.text_input("사용할 아이디 (영문·숫자·_ 조합 4~20자)", placeholder="예: electro_kim", key="su_id")
        su_name = st.text_input("이름 (실명)", key="su_name")
        su_pw = st.text_input("비밀번호 (영문 + 숫자 + 특수문자 포함 8자 이상)", type="password", key="su_pw")
        su_pw2 = st.text_input("비밀번호 확인", type="password", key="su_pw2")

        st.divider()
        st.markdown("**본인인증 선택 (필수)**")
        auth_choice = st.radio("인증 수단", ["📱 휴대폰 문자 인증 (6자리)", "📧 이메일 인증 (6자리)"], horizontal=True)
        auth_method = "phone" if "휴대폰" in auth_choice else "email"

        if auth_method == "phone":
            auth_target = st.text_input("휴대폰 번호 (- 없이 입력)", placeholder="01012345678", key="auth_ph")
            smtp_host, smtp_port, smtp_user, smtp_pass = "", 587, "", ""
        else:
            auth_target = st.text_input("인증받을 이메일 주소", placeholder="name@gmail.com", key="auth_em")
            with st.expander("📨 실제 이메일 발송(SMTP) 설정 (선택: 미입력 시 테스트 모드)"):
                smtp_host = st.text_input("SMTP 서버", value="smtp.gmail.com")
                smtp_port = st.number_input("포트", value=587, step=1)
                smtp_user = st.text_input("보내는 Gmail/네이버 이메일")
                smtp_pass = st.text_input("앱 비밀번호 (App Password)", type="password")

        if auth_target != st.session_state.otp_target or auth_method != st.session_state.otp_method:
            st.session_state.otp_sent = False
            st.session_state.otp_verified = False
            st.session_state.otp_demo_code = None

        if st.button("📲 인증번호 6자리 발송", width="stretch"):
            ok, demo_code, msg = send_otp_code(auth_method, auth_target, smtp_host, smtp_port, smtp_user, smtp_pass)
            if ok:
                st.session_state.otp_sent = True
                st.session_state.otp_verified = False
                st.session_state.otp_demo_code = demo_code
                st.session_state.otp_target = auth_target
                st.session_state.otp_method = auth_method
                st.success(msg)
            else:
                st.error(msg)

        if st.session_state.otp_sent and not st.session_state.otp_verified:
            if st.session_state.otp_demo_code:
                kind = "문자(SMS)" if auth_method == "phone" else "이메일"
                st.info(f"📩 **[테스트 {kind} 수신함]** 발송된 6자리 인증번호: **`{st.session_state.otp_demo_code}`** (3분 이내 입력)")
            oc1, oc2 = st.columns([2.2, 1.3])
            in_code = oc1.text_input("인증번호 6자리 입력", max_chars=6, placeholder="123456", key="otp_in")
            oc2.write("")
            oc2.write("")
            if oc2.button("인증 확인", type="primary", width="stretch"):
                v_ok, v_msg = verify_otp_code(auth_method, auth_target, in_code)
                if v_ok:
                    st.session_state.otp_verified = True
                    st.rerun()
                else:
                    st.error(v_msg)

        if st.session_state.otp_verified:
            st.success("✅ 6자리 본인인증이 완료되었습니다! 아래 버튼을 누르면 가입이 완료됩니다.")

        if st.button("✅ 최종 회원가입 완료", type="primary", width="stretch", disabled=(not st.session_state.otp_verified)):
            if su_pw != su_pw2:
                st.error("비밀번호와 비밀번호 확인이 일치하지 않습니다.")
            else:
                ok, msg = register_user(su_id, su_name, su_pw, auth_method, auth_target)
                if ok:
                    st.session_state.otp_sent = False
                    st.session_state.otp_verified = False
                    st.session_state.otp_demo_code = None
                    st.session_state.prefill_id = su_id.strip()
                    st.session_state.auth_flash = msg
                    st.session_state.auth_page = "login"
                    st.rerun()
                else:
                    st.error(msg)

    elif ap == "find_id":
        if st.button("⬅️ 로그인 화면으로 돌아가기"):
            st.session_state.auth_page = "login"
            st.rerun()
        st.subheader(f"🔎 {t('find_id_tab', lang)}")
        fi_name = st.text_input("가입 시 등록한 이름", key="fi_n")
        fi_hint = st.text_input("인증했던 휴대폰 번호 또는 이메일", key="fi_h")
        if st.button("내 아이디 찾기", type="primary", width="stretch"):
            ok, msg = find_user_id(fi_name, fi_hint)
            st.success(msg) if ok else st.error(msg)

    elif ap == "find_pw":
        if st.button("⬅️ 로그인 화면으로 돌아가기"):
            st.session_state.auth_page = "login"
            st.rerun()
        st.subheader(f"🔑 {t('find_pw_tab', lang)}")
        fp_id = st.text_input("가입 아이디 (또는 휴대폰/이메일)", key="fp_id")
        fp_name = st.text_input("가입자 이름", key="fp_n")
        fp_new = st.text_input("새 비밀번호 (영문+숫자+특수문자 8자 이상)", type="password", key="fp_pw")
        if st.button("비밀번호 재설정", type="primary", width="stretch"):
            ok, msg = reset_user_password(fp_id, fp_name, fp_new)
            if ok:
                st.session_state.auth_flash = msg
                st.session_state.auth_page = "login"
                st.rerun()
            else:
                st.error(msg)

    st.stop()

# ==========================================
# 로그인 완료 후: 관리자 전환 / 로그아웃 바
# ==========================================
user = st.session_state.user
if user["role"] == "admin":
    ac1, ac2 = st.columns(2)
    next_mode = "app" if st.session_state.view_mode == "admin" else "admin"
    lbl_mode = "📱 앱 화면 보기" if st.session_state.view_mode == "admin" else "🖥️ 관리자 문의함"
    if ac1.button(lbl_mode, width="stretch"):
        st.session_state.view_mode = next_mode
        st.rerun()
    if ac2.button("로그아웃", width="stretch"):
        st.session_state.user = None
        st.session_state.view_mode = "app"
        st.session_state.auth_page = "login"
        st.rerun()
else:
    if st.button("로그아웃", width="stretch"):
        st.session_state.user = None
        st.session_state.view_mode = "app"
        st.session_state.auth_page = "login"
        st.rerun()

if user["role"] == "admin" and st.session_state.view_mode == "admin":
    st.subheader("🖥️ 관리자 웹브라우저 — 고객 문의 내역")
    if st.button("🔄 새로고침"):
        st.rerun()
    inquiries = get_all_inquiries()
    if not inquiries:
        st.info("접수된 고객 문의가 아직 없습니다.")
    else:
        st.dataframe(pd.DataFrame([{
            "번호": x["id"], "상태": x["status"], "작성자": x["author_name"], "연락처": x["contact"],
            "제목": x["title"], "내용": x["message"], "접수일시": x["created_at"], "답변": x["admin_reply"],
        } for x in inquiries]), width="stretch", hide_index=True)
        for inq in inquiries:
            with st.expander(f"#{inq['id']} [{inq['status']}] {inq['title']} — {inq['author_name']}"):
                st.info(inq["message"])
                rep = st.text_input("관리자 답변", value=inq["admin_reply"], key=f"rep_{inq['id']}")
                if st.button("답변 저장", key=f"rbtn_{inq['id']}", type="primary"):
                    reply_inquiry(inq["id"], rep)
                    st.rerun()
    st.stop()

with st.expander("🔑 AI 도면 인식 키 (Gemini API 키 — 미입력 시 시뮬레이션 모드)"):
    api_key = st.text_input("Gemini API Key", value=os.environ.get("GEMINI_API_KEY", ""), type="password")

nav = st.columns(5)
for i, short_lbl in enumerate(["1.도면", "2.요소", "3.인건비", "4.분석", "5.결과"], start=1):
    if nav[i - 1].button(short_lbl, key=f"n_{i}", type=("primary" if st.session_state.step == i else "secondary"), width="stretch"):
        st.session_state.step = i
        st.rerun()
st.progress(st.session_state.step / 5)

if st.session_state.step == 1:
    st.subheader(f"1️⃣ {t('step1', lang)}")
    enhan
