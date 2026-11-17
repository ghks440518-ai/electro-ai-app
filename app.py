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
max_w = "980px" if (st.session_state.user and st.session_state.view_mode == "admin") else "500px"

st.markdown(f"""
<style>
.block-container {{
    max-width: {max_w} !important; padding-top: 1rem !important; padding-bottom: 3rem !important;
    background-color: #F8FAFC; border-radius: 22px;
    box-shadow: 0 10px 30px rgba(15, 23, 42, 0.10); margin-top: 0.8rem; margin-bottom: 2rem; {rtl_css}
}}
.app-hdr {{
    background: linear-gradient(135deg, #0F172A 0%, #1E40AF 100%);
    color: #fff; padding: 14px 16px; border-radius: 14px; margin-bottom: 10px;
}}
.app-hdr h3 {{ margin: 0; font-size: 1.18rem; color: #fff; }}
.app-hdr p {{ margin: 3px 0 0 0; font-size: 0.80rem; opacity: 0.9; }}
.hero-cost {{
    background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
    color: #fff; padding: 16px; border-radius: 14px; margin: 8px 0 12px 0;
}}
.hero-cost .won {{ font-size: 1.7rem; font-weight: 800; color: #38BDF8; margin: 4px 0; }}
</style>
""", unsafe_allow_html=True)

# 상단 공통 헤더 + 옵션 톱니바퀴
h_col1, h_col2 = st.columns([3.2, 1.3])
with h_col1:
    st.markdown(f"""
    <div class="app-hdr">
      <h3>{t('app_title', lang)}</h3>
      <p>{t('app_sub', lang)}</p>
    </div>
    """, unsafe_allow_html=True)

with h_col2:
    with st.popover("⚙️ 옵션", width="stretch"):
        st.markdown(f"**{t('lang_label', lang)}**")
        lang_keys = list(LANGUAGES.keys())
        sel_lang = st.selectbox("언어", options=lang_keys, index=lang_keys.index(lang), format_func=lambda x: LANGUAGES[x], label_visibility="collapsed")
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
# 0번: 로그인 / 별도 페이지형 회원가입·ID찾기·PW재설정
# ==========================================
if st.session_state.user is None:
    ap = st.session_state.auth_page

    # 1) 로그인 메인 화면 (회원가입 입력칸 없이 깔끔한 로그인만 표시)
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

        st.caption("💡 관리자 테스트 계정: `admin` (또는 `admin@electro.ai`) / PW: `admin1234!`")

    # 2) 회원가입 화면 (완료 시 자동으로 로그인 화면으로 이동)
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

    # 3) 아이디 찾기 화면
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

    # 4) 비밀번호 재설정 화면
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
# 로그인 완료 후: 상단 사용자 바 & 메인 화면 (회원가입 UI 없음)
# ==========================================
user = st.session_state.user
u_c1, u_c2, u_c3 = st.columns([2.2, 1.8, 1])
u_c1.caption(f"👤 **{user['name']}** (`{user.get('username') or ''}`)")
if user["role"] == "admin":
    next_mode = "app" if st.session_state.view_mode == "admin" else "admin"
    lbl_mode = "📱 앱 화면" if st.session_state.view_mode == "admin" else "🖥️ 관리자 문의함"
    if u_c2.button(lbl_mode, width="stretch"):
        st.session_state.view_mode = next_mode
        st.rerun()
if u_c3.button("로그아웃", width="stretch"):
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
for i, key_name in enumerate(["step1", "step2", "step3", "step4", "step5"], start=1):
    if nav[i - 1].button(t(key_name, lang), key=f"n_{i}", type=("primary" if st.session_state.step == i else "secondary"), width="stretch"):
        st.session_state.step = i
        st.rerun()
st.progress(st.session_state.step / 5)

if st.session_state.step == 1:
    st.subheader(f"1️⃣ {t('step1', lang)}")
    enhance_p = st.checkbox("✨ 종이 평면도 스캔 선명화 보정", value=False)
    cam_on = st.toggle("📱 스마트폰 카메라로 종이 평면도 촬영", value=False)
    f_up = st.camera_input("종이 평면도 촬영") if cam_on else st.file_uploader("평면도 이미지 업로드 (JPG/PNG)", type=["jpg", "jpeg", "png"])
    if f_up is not None:
        st.session_state.floor_img = prepare_image(f_up, enhance_paper=enhance_p, auto_crop=True)
    if st.button("🖼️ 샘플 아파트 평면도로 테스트하기", width="stretch"):
        st.session_state.floor_img = create_sample_floorplan()
    if st.session_state.floor_img is not None:
        st.image(st.session_state.floor_img, caption="업로드된 2D 집 평면도", width="stretch")
    if st.button("다음: 설계 요소 & 자재가격 ➡️", type="primary", width="stretch", disabled=(st.session_state.floor_img is None)):
        st.session_state.step = 2
        st.rerun()

elif st.session_state.step == 2:
    st.subheader(f"2️⃣ {t('step2', lang)}")
    search_q = st.text_input(t("search_el", lang), placeholder="예: 콘센트, 전등, TV, 인덕션, 비데, 스위치...")
    matched_keys = search_elements(search_q)
    if not matched_keys:
        st.warning("검색 결과가 없습니다.")
    else:
        c_s1, c_s2, c_s3 = st.columns([2.4, 1.3, 1.1])
        pick_k = c_s1.selectbox("검색된 설계 요소", options=matched_keys, format_func=lambda k: f"{ELEMENT_DB[k]['name']} ({ELEMENT_DB[k]['power_w']}W)")
        pick_room = c_s2.text_input("배치 공간", value="거실")
        c_s3.write("")
        if c_s3.button("➕ 추가", type="primary", width="stretch"):
            st.session_state.elements.append({"element_key": pick_k, "room_hint": pick_room, "mat_price": ELEMENT_DB[pick_k]["default_mat_price"], "qty": 1})
            st.rerun()

    st.divider()
    st.markdown(f"**📋 구성된 설계 요소 ({len(st.session_state.elements)}개) — 옆 칸에 구입 자재 가격 입력**")
    for idx, el in enumerate(st.session_state.elements):
        meta = ELEMENT_DB[el["element_key"]]
        r1, r2, r3, r4, r5 = st.columns([2.2, 1.3, 1.7, 0.9, 0.7])
        r1.write(f"**{idx+1}. {meta['name'].split()[0]}**")
        el["room_hint"] = r2.text_input("공간", value=el["room_hint"], key=f"rm_{idx}", label_visibility="collapsed")
        el["mat_price"] = r3.number_input("가격", min_value=0, step=1000, value=int(el["mat_price"]), key=f"mp_{idx}", label_visibility="collapsed")
        el["qty"] = r4.number_input("수량", min_value=1, max_value=50, value=int(el["qty"]), key=f"qt_{idx}", label_visibility="collapsed")
        if r5.button("🗑️", key=f"dl_{idx}", width="stretch"):
            st.session_state.elements.pop(idx)
            st.rerun()

    c1, c2 = st.columns(2)
    if c1.button("⬅️ 이전", width="stretch"):
        st.session_state.step = 1
        st.rerun()
    if c2.button("다음: 인건비/인원수 ➡️", type="primary", width="stretch", disabled=(len(st.session_state.elements) == 0)):
        st.session_state.step = 3
        st.rerun()

elif st.session_state.step == 3:
    st.subheader(f"3️⃣ {t('step3', lang)}")
    st.session_state.labor_per_person = st.number_input("1인당 인건비 / 일당 (원)", min_value=50000, max_value=1000000, value=int(st.session_state.labor_per_person), step=10000)
    lc1, lc2 = st.columns(2)
    st.session_state.worker_count = lc1.number_input("공사 총 인원수 (명)", min_value=1, max_value=30, value=int(st.session_state.worker_count), step=1)
    st.session_state.work_days = lc2.number_input("예상 공사 일수 (일)", min_value=0.5, max_value=30.0, value=float(st.session_state.work_days), step=0.5)
    est_labor = int(st.session_state.labor_per_person * st.session_state.worker_count * st.session_state.work_days)
    st.info(f"👷 예상 총 인건비: **{est_labor:,} 원** ({st.session_state.labor_per_person:,}원 × {st.session_state.worker_count}명 × {st.session_state.work_days}일)")

    c1, c2 = st.columns(2)
    if c1.button("⬅️ 이전", width="stretch"):
        st.session_state.step = 2
        st.rerun()
    if c2.button("다음: AI 분석 실행 ➡️", type="primary", width="stretch"):
        st.session_state.step = 4
        st.rerun()

elif st.session_state.step == 4:
    st.subheader(f"4️⃣ {t('step4', lang)}")
    main_br = st.selectbox("기존 분전반 메인 차단기 용량 (A)", [30, 40, 50, 60, 75, 100], index=1)
    loss_pct = st.slider("KEC 배선 여유 손실률 (%)", 10, 35, 20, step=5)

    if st.button("⚡ AI 분석 및 도면·시공비 도출 시작", type="primary", width="stretch", disabled=(st.session_state.floor_img is None)):
        with st.spinner("2D 배치도, 실제 시공 전기도면, KEC 시공비를 도출 중입니다..."):
            try:
                ana = run_ai_design_analysis(st.session_state.floor_img, st.session_state.elements, api_key) if api_key else run_demo_design_analysis(st.session_state.elements)
                el_inputs = []
                for idx, p in enumerate(ana.placements):
                    src = st.session_state.elements[idx] if idx < len(st.session_state.elements) else st.session_state.elements[-1]
                    el_inputs.append(DesignElementInput(
                        element_key=p.element_key, room_name=p.room_name,
                        user_mat_price=int(src["mat_price"]), quantity=int(src["qty"]), distance_m=float(p.estimated_distance_m),
                    ))
                cost_res = calculate_kec_and_cost(
                    placed_elements=el_inputs,
                    labor_per_person=int(st.session_state.labor_per_person),
                    worker_count=int(st.session_state.worker_count),
                    work_days=float(st.session_state.work_days),
                    main_breaker_a=int(main_br), loss_rate=loss_pct / 100.0,
                )
                st.session_state.ai_res = ana
                st.session_state.cost_res = cost_res
                st.session_state.img_res1 = render_2d_placement_blueprint(st.session_state.floor_img, ana)
                st.session_state.img_res2 = render_construction_electrical_diagram(st.session_state.floor_img, ana, cost_res)
                st.session_state.step = 5
                st.rerun()
            except Exception as e:
                st.error(f"분석 오류: {e}")

    if st.button("⬅️ 이전", width="stretch"):
        st.session_state.step = 3
        st.rerun()

elif st.session_state.step == 5:
    st.subheader(f"5️⃣ {t('step5', lang)}")
    if st.session_state.ai_res is None:
        st.warning("4단계에서 먼저 AI 분석을 실행해 주세요.")
        st.stop()

    rt1, rt2, rt3 = st.tabs([t("res_tab1", lang), t("res_tab2", lang), t("res_tab3", lang)])
    cr = st.session_state.cost_res

    with rt1:
        st.image(st.session_state.img_res1, width="stretch")
        b1 = io.BytesIO()
        st.session_state.img_res1.save(b1, format="PNG")
        st.download_button("📥 [결과1] 2D 배치 설계도 다운로드 (PNG)", b1.getvalue(), "결과1_2D배치도.png", "image/png", width="stretch")

    with rt2:
        st.image(st.session_state.img_res2, width="stretch")
        b2 = io.BytesIO()
        st.session_state.img_res2.save(b2, format="PNG")
        st.download_button("📥 [결과2] 실제 시공 전기도면 다운로드 (PNG)", b2.getvalue(), "결과2_실제시공_전기도면.png", "image/png", type="primary", width="stretch")

    with rt3:
        st.markdown(f"""
        <div class="hero-cost">
            <div style="font-size:0.82rem; opacity:0.85;">최종 예상 시공비 (구입 자재 + KEC 공사자재 + 인건비)</div>
            <div class="won">{cr['final_total_cost']:,} 원</div>
            <div style="font-size:0.78rem; opacity:0.85;">
                구입자재 {cr['user_mat_total']:,}원 + KEC자재 {cr['kec_mat_total']:,}원 + 인건비 {cr['labor_total']:,}원
            </div>
        </div>
        """, unsafe_allow_html=True)

        s_txt = f"메인 차단기 {cr['main_breaker_a']}A 기준 예상 사용률 {cr['usage_pct']}% ({cr['safety_status']})"
        st.error(f"🚨 {s_txt}") if cr["safety_status"] == "위험" else (st.warning(f"⚠️ {s_txt}") if cr["safety_status"] == "주의" else st.success(f"🟢 {s_txt}"))

        st.markdown("**① 2단계 구입 자재 내역 (사용자 입력)**")
        st.dataframe(pd.DataFrame([{**x, "금액": f"{x['금액']:,}원"} for x in cr["user_mat_items"]]), width="stretch", hide_index=True)

        st.markdown("**② KEC 기반 전기공사 필수 자재 목록 및 비용 (cf.3)**")
        st.dataframe(pd.DataFrame([{**x, "금액": f"{x['금액']:,}원"} for x in cr["kec_mat_items"]]), width="stretch", hide_index=True)

        ld = cr["labor_detail"]
        st.markdown(f"**③ 시공 인건비:** {ld['labor_per_person']:,}원 × {ld['worker_count']}명 × {ld['work_days']}일 = **{cr['labor_total']:,}원**")
        quote_txt = f"[KEC 최종 시공 견적서 - {datetime.now().strftime('%Y-%m-%d')}]\n구입자재: {cr['user_mat_total']:,}원\nKEC자재: {cr['kec_mat_total']:,}원\n인건비: {cr['labor_total']:,}원\n총 합계: {cr['final_total_cost']:,}원"
        st.download_button("📥 최종 시공비 견적서 저장 (.txt)", quote_txt.encode("utf-8"), "최종시공비_견적서.txt", "text/plain", width="stretch")
