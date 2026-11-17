# backend/db_auth.py
import os
import re
import secrets
import smtplib
import sqlite3
import hashlib
from email.message import EmailMessage
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "electro_app.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _normalize_phone(phone: str) -> str:
    return re.sub(r"[^0-9]", "", phone or "")


def _hash_password(password: str, salt: Optional[str] = None) -> str:
    if salt is None:
        salt = os.urandom(16).hex()
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${dk.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, _ = stored.split("$", 1)
        return _hash_password(password, salt) == stored
    except Exception:
        return False


def validate_username(username: str) -> tuple[bool, str]:
    u = (username or "").strip()
    if not re.match(r"^[A-Za-z0-9_]{4,20}$", u):
        return False, "아이디는 영문, 숫자, 밑줄(_) 조합 4~20자로 입력해 주세요."
    return True, ""


def validate_password_policy(password: str) -> tuple[bool, str]:
    pw = password or ""
    if len(pw) < 8:
        return False, "비밀번호는 8자 이상이어야 합니다."
    if not re.search(r"[A-Za-z]", pw):
        return False, "비밀번호에 영문자가 최소 1자 이상 포함되어야 합니다."
    if not re.search(r"[0-9]", pw):
        return False, "비밀번호에 숫자가 최소 1개 이상 포함되어야 합니다."
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};:'\",.<>/?\\|`~]", pw):
        return False, "비밀번호에 특수문자(!@#$% 등)가 최소 1자 이상 포함되어야 합니다."
    return True, ""


def init_db():
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            name TEXT NOT NULL,
            phone TEXT UNIQUE,
            email TEXT UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        )
    """)
    # 기존 DB 파일 자동 마이그레이션 (username 컬럼 추가)
    cur.execute("PRAGMA table_info(users)")
    cols = [r["name"] for r in cur.fetchall()]
    if "username" not in cols:
        cur.execute("ALTER TABLE users ADD COLUMN username TEXT")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username ON users(username)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS verification_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            method TEXT NOT NULL,
            target TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            verified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inquiries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_login_id TEXT,
            author_name TEXT NOT NULL,
            contact TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT '접수됨',
            admin_reply TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    # 기본 관리자 계정 보장 (ID: admin / PW: admin1234!)
    cur.execute("SELECT id FROM users WHERE email = ?", ("admin@electro.ai",))
    admin_row = cur.fetchone()
    if not admin_row:
        cur.execute(
            "INSERT INTO users (username, name, phone, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("admin", "관리자", "01000000000", "admin@electro.ai", _hash_password("admin1234!"), "admin", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
    else:
        cur.execute("UPDATE users SET username = 'admin' WHERE id = ? AND username IS NULL", (admin_row["id"],))
    conn.commit()
    conn.close()


def send_otp_code(
    method: str,
    raw_target: str,
    smtp_host: str = "",
    smtp_port: int = 587,
    smtp_user: str = "",
    smtp_pass: str = "",
) -> tuple[bool, Optional[str], str]:
    """
    6자리 인증번호 생성 및 발송 (이메일 SMTP 실제 발송 지원, 미설정 시 테스트 모의 발송)
    """
    if method == "phone":
        target = _normalize_phone(raw_target)
        if not re.match(r"^01[0-9]{8,9}$", target):
            return False, None, "올바른 휴대폰 번호(예: 01012345678)를 입력해 주세요."
    else:
        target = (raw_target or "").strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", target):
            return False, None, "올바른 이메일 주소를 입력해 주세요."

    # 이미 가입된 연락처인지 확인
    conn = _get_conn()
    cur = conn.cursor()
    col = "phone" if method == "phone" else "email"
    cur.execute(f"SELECT id FROM users WHERE {col} = ?", (target,))
    if cur.fetchone():
        conn.close()
        return False, None, f"이미 가입되어 있는 {'휴대폰 번호' if method == 'phone' else '이메일'}입니다."

    code = f"{secrets.randbelow(1000000):06d}"
    now = datetime.now()
    expires = (now + timedelta(minutes=3)).strftime("%Y-%m-%d %H:%M:%S")
    cur.execute(
        "INSERT INTO verification_codes (method, target, code, expires_at, verified, created_at) VALUES (?, ?, ?, ?, 0, ?)",
        (method, target, code, expires, now.strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()

    # 이메일 + SMTP 정보가 설정된 경우 실제 이메일 발송
    if method == "email" and smtp_user.strip() and smtp_pass.strip():
        try:
            msg = EmailMessage()
            msg["Subject"] = "[홈전기 AI 설계사] 회원가입 본인인증 번호 (6자리)"
            msg["From"] = smtp_user.strip()
            msg["To"] = target
            msg.set_content(f"안녕하세요.\n\n회원가입 본인인증 번호 6자리는 [{code}] 입니다.\n3분 이내에 입력해 주세요.")
            with smtplib.SMTP(smtp_host.strip(), int(smtp_port), timeout=10) as server:
                server.starttls()
                server.login(smtp_user.strip(), smtp_pass.strip())
                server.send_message(msg)
            return True, None, f"📧 {target} 주소로 인증번호 6자리를 실제 발송했습니다! (메일함을 확인하세요)"
        except Exception as e:
            return False, None, f"이메일 발송 실패(SMTP 설정을 확인하세요): {e}"

    # SMS 또는 SMTP 미설정 시 테스트 발송 안내
    label = "문자(SMS)" if method == "phone" else "이메일"
    return True, code, f"[테스트 발송 모드] 실제 {label} API 연동 전 테스트를 위해 6자리 인증번호가 생성되었습니다."


def verify_otp_code(method: str, raw_target: str, input_code: str) -> tuple[bool, str]:
    target = _normalize_phone(raw_target) if method == "phone" else (raw_target or "").strip().lower()
    code_in = (input_code or "").strip()
    if not re.match(r"^[0-9]{6}$", code_in):
        return False, "인증번호 숫자 6자리를 정확히 입력해 주세요."

    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM verification_codes WHERE method = ? AND target = ? ORDER BY id DESC LIMIT 1",
        (method, target),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "먼저 인증번호 발송 버튼을 눌러주세요."

    exp_dt = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > exp_dt:
        conn.close()
        return False, "인증번호 유효시간(3분)이 만료되었습니다. 재발송해 주세요."

    if not secrets.compare_digest(row["code"], code_in):
        conn.close()
        return False, "인증번호가 일치하지 않습니다. 다시 확인해 주세요."

    cur.execute("UPDATE verification_codes SET verified = 1 WHERE id = ?", (row["id"],))
    conn.commit()
    conn.close()
    return True, "✅ 본인인증이 완료되었습니다!"


def register_user(
    username: str,
    name: str,
    password: str,
    auth_method: str,
    auth_target: str,
    extra_phone: str = "",
    extra_email: str = "",
) -> tuple[bool, str]:
    u_ok, u_msg = validate_username(username)
    if not u_ok:
        return False, u_msg
    name = (name or "").strip()
    if not name:
        return False, "이름을 입력해 주세요."

    p_ok, p_msg = validate_password_policy(password)
    if not p_ok:
        return False, p_msg

    norm_target = _normalize_phone(auth_target) if auth_method == "phone" else (auth_target or "").strip().lower()
    phone_val = norm_target if auth_method == "phone" else (_normalize_phone(extra_phone) or None)
    email_val = norm_target if auth_method == "email" else ((extra_email or "").strip().lower() or None)

    conn = _get_conn()
    cur = conn.cursor()
    # 서버 DB에서 본인인증 완료 여부 최종 검증
    cur.execute(
        "SELECT verified FROM verification_codes WHERE method = ? AND target = ? ORDER BY id DESC LIMIT 1",
        (auth_method, norm_target),
    )
    vrow = cur.fetchone()
    if not vrow or vrow["verified"] != 1:
        conn.close()
        return False, "휴대폰 또는 이메일 6자리 본인인증을 먼저 완료해 주세요."

    try:
        cur.execute(
            "INSERT INTO users (username, name, phone, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?, 'user', ?)",
            (username.strip(), name, phone_val, email_val, _hash_password(password), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        conn.commit()
        return True, f"🎉 [{username.strip()}]님 회원가입이 완료되었습니다! 이제 로그인해 주세요."
    except sqlite3.IntegrityError:
        return False, "이미 사용 중인 아이디, 전화번호 또는 이메일입니다."
    finally:
        conn.close()


def login_user(login_id: str, password: str) -> tuple[bool, Optional[Dict[str, Any]], str]:
    raw_id = (login_id or "").strip()
    norm_phone = _normalize_phone(raw_id)
    norm_email = raw_id.lower()

    if not raw_id or not password:
        return False, None, "아이디(또는 전화번호/이메일)와 비밀번호를 입력하세요."

    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM users WHERE username = ? OR (email = ? AND email IS NOT NULL) OR (phone = ? AND phone IS NOT NULL)",
        (raw_id, norm_email, norm_phone),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return False, None, "존재하지 않는 계정입니다."
    if not _verify_password(password, row["password_hash"]):
        return False, None, "비밀번호가 일치하지 않습니다."
    return True, dict(row), "로그인 성공"


def find_user_id(name: str, contact_hint: str) -> tuple[bool, str]:
    name = (name or "").strip()
    hint = (contact_hint or "").strip()
    norm_phone = _normalize_phone(hint)
    norm_email = hint.lower()

    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT username, phone, email FROM users WHERE name = ? AND ((email = ? AND email IS NOT NULL) OR (phone = ? AND phone IS NOT NULL))",
        (name, norm_email, norm_phone),
    )
    row = cur.fetchone()
    conn.close()

    if not row:
        return False, "일치하는 회원 정보를 찾을 수 없습니다."
    parts = [f"아이디: {row['username']}"]
    if row["phone"]:
        parts.append(f"휴대폰: {row['phone']}")
    if row["email"]:
        parts.append(f"이메일: {row['email']}")
    return True, "가입된 계정 → " + " / ".join(parts)


def reset_user_password(login_id: str, name: str, new_password: str) -> tuple[bool, str]:
    p_ok, p_msg = validate_password_policy(new_password)
    if not p_ok:
        return False, p_msg

    raw_id = (login_id or "").strip()
    norm_phone = _normalize_phone(raw_id)
    norm_email = raw_id.lower()
    name = (name or "").strip()

    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM users WHERE name = ? AND (username = ? OR (email = ? AND email IS NOT NULL) OR (phone = ? AND phone IS NOT NULL))",
        (name, raw_id, norm_email, norm_phone),
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return False, "아이디와 이름이 일치하는 회원이 없습니다."

    cur.execute("UPDATE users SET password_hash = ? WHERE id = ?", (_hash_password(new_password), row["id"]))
    conn.commit()
    conn.close()
    return True, "비밀번호가 성공적으로 변경되었습니다. 새 비밀번호로 로그인하세요."


def create_inquiry(user_login_id: str, author_name: str, contact: str, title: str, message: str) -> tuple[bool, str]:
    if not (author_name.strip() and contact.strip() and title.strip() and message.strip()):
        return False, "이름, 연락처, 제목, 문의 내용을 모두 입력해 주세요."
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO inquiries (user_login_id, author_name, contact, title, message, status, created_at) VALUES (?, ?, ?, ?, ?, '접수됨', ?)",
        (user_login_id, author_name.strip(), contact.strip(), title.strip(), message.strip(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()
    return True, "문의가 정상 접수되었습니다. 관리자 웹브라우저에서 즉시 확인합니다."


def get_all_inquiries() -> List[Dict[str, Any]]:
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("SELECT * FROM inquiries ORDER BY id DESC")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def reply_inquiry(inq_id: int, reply_text: str):
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE inquiries SET admin_reply = ?, status = '답변완료' WHERE id = ?", ((reply_text or "").strip(), inq_id))
    conn.commit()
    conn.close()
