# backend/i18n.py
from typing import Dict

LANGUAGES: Dict[str, str] = {
    "ko": "🇰🇷 한국어",
    "en": "🇺🇸 English",
    "zh": "🇨🇳 中文 (简体)",
    "ja": "🇯🇵 日本語",
    "ar": "🇸🇦 العربية",
    "fr": "🇫🇷 Français",
    "de": "🇩🇪 Deutsch",
    "es": "🇪🇸 Español",
}

TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "app_title": {
        "ko": "⚡ 홈전기 KEC 설계·견적 AI",
        "en": "⚡ HomeElectro KEC Design & Quote AI",
        "zh": "⚡ 家装电气 KEC 设计与报价 AI",
        "ja": "⚡ ホーム電気 KEC 設計・見積 AI",
        "ar": "⚡ ذكاء تصميم وتسعير الكهرباء المنزلية KEC",
        "fr": "⚡ HomeElectro IA Conception & Devis KEC",
        "de": "⚡ HomeElectro KI-Elektroplanung & Kostenvoranschlag",
        "es": "⚡ HomeElectro IA Diseño Eléctrico y Presupuesto",
    },
    "app_sub": {
        "ko": "평면도 업로드부터 최적 2D 배치 · 실제 시공 전기도면 · 최종 시공비 산출까지",
        "en": "From floorplan upload to 2D layout, construction wiring diagram & total cost",
        "zh": "从平面图上传到 2D 最佳布局、施工电气图及最终造价计算",
        "ja": "平面図アップロードから2D配置・施工用電気図面・最終施工費算出まで",
        "ar": "من رفع المخطط إلى التوزيع ثنائي الأبعاد ومخطط التنفيذ والتكلفة النهائية",
        "fr": "Du plan d'étage au schéma 2D, plan de câblage et coût final",
        "de": "Vom Grundriss zur 2D-Platzierung, Schaltplan und Gesamtkosten",
        "es": "Desde el plano hasta el diseño 2D, diagrama eléctrico y costo final",
    },
    "login_tab": {"ko": "로그인", "en": "Login", "zh": "登录", "ja": "ログイン", "ar": "تسجيل الدخول", "fr": "Connexion", "de": "Anmelden", "es": "Iniciar sesión"},
    "signup_tab": {"ko": "회원가입", "en": "Sign Up", "zh": "注册", "ja": "新規登録", "ar": "إنشاء حساب", "fr": "S'inscrire", "de": "Registrieren", "es": "Registrarse"},
    "find_id_tab": {"ko": "아이디 찾기", "en": "Find ID", "zh": "找回账号", "ja": "ID検索", "ar": "البحث عن المعرف", "fr": "Trouver ID", "de": "ID finden", "es": "Buscar ID"},
    "find_pw_tab": {"ko": "비밀번호 찾기", "en": "Reset PW", "zh": "重置密码", "ja": "パスワード再設定", "ar": "استعادة كلمة المرور", "fr": "Mot de passe", "de": "Passwort", "es": "Recuperar clave"},
    "id_label": {
        "ko": "아이디 (전화번호 또는 이메일)",
        "en": "ID (Phone or Email)",
        "zh": "账号 (手机号或邮箱)",
        "ja": "ID (電話番号またはメール)",
        "ar": "المعرف (الهاتف أو البريد الإلكتروني)",
        "fr": "Identifiant (Tél. ou E-mail)",
        "de": "ID (Telefon oder E-Mail)",
        "es": "ID (Teléfono o Correo)",
    },
    "pw_label": {"ko": "비밀번호", "en": "Password", "zh": "密码", "ja": "パスワード", "ar": "كلمة المرور", "fr": "Mot de passe", "de": "Passwort", "es": "Contraseña"},
    "gear_btn": {"ko": "⚙️ 옵션 (언어 · 문의하기)", "en": "⚙️ Options (Language · Contact)", "zh": "⚙️ 选项 (语言 · 咨询)", "ja": "⚙️ オプション (言語・お問い合わせ)", "ar": "⚙️ الخيارات (اللغة · اتصل بنا)", "fr": "⚙️ Options (Langue · Contact)", "de": "⚙️ Optionen (Sprache · Kontakt)", "es": "⚙️ Opciones (Idioma · Contacto)"},
    "lang_label": {"ko": "🌐 언어 변경 (전 세계 언어)", "en": "🌐 Language", "zh": "🌐 语言切换", "ja": "🌐 言語変更", "ar": "🌐 تغيير اللغة", "fr": "🌐 Langue", "de": "🌐 Sprache", "es": "🌐 Idioma"},
    "inquiry_title": {"ko": "📩 고객 문의하기 (관리자 웹브라우저 전송)", "en": "📩 Contact Admin", "zh": "📩 在线咨询 (发送至管理员网页)", "ja": "📩 お問い合わせ (管理者画面へ送信)", "ar": "📩 تواصل مع الإدارة", "fr": "📩 Contacter l'administrateur", "de": "📩 Support kontaktieren", "es": "📩 Contactar al administrador"},
    "step1": {"ko": "1. 평면도 업로드", "en": "1. Floorplan", "zh": "1. 上传平面图", "ja": "1. 平面図", "ar": "1. المخطط", "fr": "1. Plan", "de": "1. Grundriss", "es": "1. Plano"},
    "step2": {"ko": "2. 설계요소/자재가", "en": "2. Elements/Price", "zh": "2. 要素与材料价", "ja": "2. 要素・資材費", "ar": "2. العناصر والأسعار", "fr": "2. Éléments", "de": "2. Elemente", "es": "2. Elementos"},
    "step3": {"ko": "3. 인건비/인원수", "en": "3. Labor/Crew", "zh": "3. 人工与人数", "ja": "3. 人件費・人数", "ar": "3. العمالة والطاقم", "fr": "3. Main-d'œuvre", "de": "3. Arbeitskosten", "es": "3. Mano de obra"},
    "step4": {"ko": "4. AI 분석", "en": "4. AI Analyze", "zh": "4. AI 分析", "ja": "4. AI分析", "ar": "4. تحليل AI", "fr": "4. Analyse IA", "de": "4. KI-Analyse", "es": "4. Análisis IA"},
    "step5": {"ko": "5. 최종 결과", "en": "5. Results", "zh": "5. 最终结果", "ja": "5. 最終結果", "ar": "5. النتائج", "fr": "5. Résultats", "de": "5. Ergebnisse", "es": "5. Resultados"},
    "search_el": {
        "ko": "🔍 설계할 요소 검색 (예: 콘센트, 전등, TV, 냉장고, 에어컨, 인덕션...)",
        "en": "🔍 Search electrical element (Outlet, Light, TV, Fridge, AC...)",
        "zh": "🔍 搜索电气要素 (插座、灯具、电视、冰箱、空调...)",
        "ja": "🔍 設計要素を検索 (コンセント、照明、TV、冷蔵庫、エアコン...)",
        "ar": "🔍 ابحث عن العنصر الكهربائي (مقبس، إضاءة، تلفاز، ثلاجة...)",
        "fr": "🔍 Rechercher un élément (Prise, Éclairage, TV, Frigo, Clim...)",
        "de": "🔍 Element suchen (Steckdose, Licht, TV, Kühlschrank, Klima...)",
        "es": "🔍 Buscar elemento (Enchufe, Luz, TV, Nevera, Aire...)",
    },
    "mat_price_col": {"ko": "구입 자재 가격(원)", "en": "Material Price (KRW)", "zh": "材料单价 (韩元)", "ja": "購入資材価格 (ウォン)", "ar": "سعر المادة (وون)", "fr": "Prix matériel (KRW)", "de": "Materialpreis (KRW)", "es": "Precio material (KRW)"},
    "res_tab1": {"ko": "📐 결과1: 2D 배치도", "en": "📐 1) 2D Layout", "zh": "📐 结果1: 2D 布局图", "ja": "📐 結果1: 2D配置図", "ar": "📐 1) التوزيع 2D", "fr": "📐 1) Plan 2D", "de": "📐 1) 2D-Plan", "es": "📐 1) Diseño 2D"},
    "res_tab2": {"ko": "⚡ 결과2: 시공 전기도면", "en": "⚡ 2) Wiring Diagram", "zh": "⚡ 结果2: 施工电气图", "ja": "⚡ 結果2: 施工電気図面", "ar": "⚡ 2) مخطط التنفيذ", "fr": "⚡ 2) Schéma électrique", "de": "⚡ 2) Schaltplan", "es": "⚡ 2) Diagrama eléctrico"},
    "res_tab3": {"ko": "💰 결과3: KEC 최종 시공비", "en": "💰 3) Final Cost (KEC)", "zh": "💰 结果3: KEC 最终造价", "ja": "💰 結果3: 最終施工費", "ar": "💰 3) التكلفة النهائية", "fr": "💰 3) Coût final", "de": "💰 3) Gesamtkosten", "es": "💰 3) Costo final"},
}


def t(key: str, lang: str = "ko") -> str:
    row = TRANSLATIONS.get(key, {})
    return row.get(lang) or row.get("en") or row.get("ko") or key
