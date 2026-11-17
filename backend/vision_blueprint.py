# backend/vision_blueprint.py
import os
import json
import math
from typing import List, Optional, Tuple, Dict, Any
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageEnhance
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from backend.kec_engine import ELEMENT_DB

DEFAULT_VISION_MODEL = "gemini-3.8-flash"


class PlacedElementCoord(BaseModel):
    index_id: int = Field(description="요청 목록 순번 (0부터)")
    element_key: str = Field(description="설계 요소 키")
    room_name: str = Field(description="배치 공간 이름 (거실, 주방, 안방, 현관, 욕실 등)")
    x_pct: int = Field(description="건물 벽 안쪽 가로 위치 (80~920 사이)")
    y_pct: int = Field(description="건물 벽 안쪽 세로 위치 (80~920 사이)")
    wall_orientation: str = Field(description="방향: 'vertical', 'horizontal', 'center' 중 하나")
    estimated_distance_m: float = Field(description="분전반으로부터의 배선 거리(m)")
    design_reason: str = Field(description="배치 이유 및 시공 높이 가이드")


class IntegratedDesignAnalysis(BaseModel):
    detected_main_breaker_a: int = Field(description="추정 또는 권장 메인 차단기 용량(A), 기본 40")
    panel_x_pct: int = Field(description="평면도 현관 출입구 벽면 분전반 X좌표 (0~1000)")
    panel_y_pct: int = Field(description="평면도 현관 출입구 벽면 분전반 Y좌표 (0~1000)")
    floor_summary: str = Field(description="평면도 구조 요약 (예: 24평형 아파트, 거실 중앙·주방 상단·현관 우측)")
    placements: List[PlacedElementCoord] = Field(description="모든 설계 요소의 최적 배치 좌표 목록")


def prepare_image(raw_file, enhance_paper: bool = False, auto_crop: bool = True) -> Image.Image:
    """스마트폰 EXIF 회전 보정 + 바깥 흰 여백 자동 제거 + 종이 평면도 스캔 보정"""
    img = ImageOps.exif_transpose(Image.open(raw_file)).convert("RGB")
    if auto_crop:
        w, h = img.size
        corners = [img.getpixel((2, 2)), img.getpixel((w - 3, 2)), img.getpixel((2, h - 3)), img.getpixel((w - 3, h - 3))]
        if sum(1 for r, g, b in corners if r > 245 and g > 245 and b > 245) >= 2:
            mask = img.convert("L").point(lambda p: 255 if p < 242 else 0)
            bbox = mask.getbbox()
            if bbox:
                pad = max(10, int(min(w, h) * 0.02))
                box = (max(0, bbox[0] - pad), max(0, bbox[1] - pad), min(w, bbox[2] + pad), min(h, bbox[3] + pad))
                if (box[2] - box[0]) > w * 0.25 and (box[3] - box[1]) > h * 0.25:
                    img = img.crop(box)
    if enhance_paper:
        img = ImageEnhance.Contrast(img).enhance(1.35)
        img = ImageEnhance.Brightness(img).enhance(1.07)
    return img


def run_ai_design_analysis(
    floorplan_img: Image.Image,
    requested_elements: List[dict],
    api_key: Optional[str] = None,
) -> IntegratedDesignAnalysis:
    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ValueError("Gemini API 키가 필요합니다.")

    client = genai.Client(api_key=key)
    req_lines = "\n".join(
        f"- index_id={i}, element_key='{x['element_key']}', 이름='{ELEMENT_DB.get(x['element_key'], ELEMENT_DB['outlet'])['name']}', 희망위치='{x.get('room_hint','자동')}'"
        for i, x in enumerate(requested_elements)
    )

    prompt = f"""
    당신은 대한민국 빌라·아파트·주택 평면도와 KEC 전기설계 도면을 사전에 수만 건 학습한 전기설계 AI입니다.
    첨부된 집 평면도(종이 평면도 사진 또는 디지털 도면)를 보고 요청된 요소를 최적 위치에 배치하세요.

    [요청 요소 목록]
    {req_lines}

    [배치 규칙]
    1. 먼저 도면 안의 소파, 침대, 주방 싱크대, 욕실 변기, 현관 타일 입구, 창문을 식별하세요.
    2. 모든 좌표(x_pct, y_pct)는 반드시 건물 외벽 안쪽(실내 공간/내벽 선상)이어야 하며 바깥 여백은 금지합니다.
    3. 분전반(panel_x_pct, panel_y_pct)은 현관 출입구 벽면 근처에 지정하세요.
    4. 요소별 위치 기준:
       - tv: 거실 소파 맞은편 벽면 선상 (소파가 좌우를 보면 wall_orientation='vertical', 상하를 보면 'horizontal')
       - lighting: 거실/방 천장 중앙 (wall_orientation='center')
       - switch: 방/거실 출입문 옆 내벽
       - refrigerator / induction / dishwasher: 주방 싱크대·가전장 라인 안쪽
       - aircon: 거실 또는 안방 창측 코너 안쪽
       - bidet: 욕실 변기 옆 벽면
       - outlet / lan_intercom: TV 옆이나 침대/책상 벽면
    5. 요청된 index_id 0부터 끝까지 누락 없이 반환하고, 요소끼리 겹치지 않게 최소 60 이상 띄우세요.
    """

    res = client.models.generate_content(
        model=DEFAULT_VISION_MODEL,
        contents=[prompt, floorplan_img],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=IntegratedDesignAnalysis,
            temperature=0.1,
        ),
    )
    return res.parsed if res.parsed else IntegratedDesignAnalysis(**json.loads(res.text))


def run_demo_design_analysis(requested_elements: List[dict]) -> IntegratedDesignAnalysis:
    presets = {
        "tv": (435, 670, "vertical", "거실 TV벽면", 9.0, "소파 맞은편 벽면(바닥+110cm)"),
        "lighting": (530, 560, "center", "거실 천장", 8.0, "거실 중앙 메인 LED"),
        "switch": (660, 460, "vertical", "현관/거실 입구", 4.0, "출입구 옆 바닥+120cm"),
        "refrigerator": (560, 220, "vertical", "주방", 11.0, "주방 냉장고장 상시전원"),
        "induction": (615, 165, "horizontal", "주방 조리대", 12.0, "싱크대 하부 4.0sq 단독 직결"),
        "dishwasher": (615, 255, "vertical", "주방 싱크대", 11.5, "싱크대 하부 접지 콘센트"),
        "aircon": (610, 820, "horizontal", "거실 창측", 14.0, "거실 창측 코너 단독배선"),
        "washer_dryer": (330, 240, "vertical", "다용도실", 15.0, "다용도실 방우형 단독 콘센트"),
        "bidet": (790, 340, "vertical", "욕실", 10.0, "변기 옆 방우형 콘센트"),
        "outlet": (435, 550, "vertical", "거실/안방 벽", 10.0, "생활 동선 벽면 2구 콘센트"),
        "lan_intercom": (435, 760, "vertical", "거실 벽면", 9.5, "TV 하부 통합 통신단자"),
    }
    placements, seen = [], {}
    for idx, item in enumerate(requested_elements):
        k = item["element_key"]
        bx, by, ori, rname, dist, reason = presets.get(k, (500, 500, "center", "거실", 10.0, "표준 벽면 배치"))
        c = seen.get(k, 0)
        seen[k] = c + 1
        placements.append(PlacedElementCoord(
            index_id=idx, element_key=k, room_name=item.get("room_hint") or rname,
            x_pct=min(880, bx + c * 55), y_pct=min(880, by + (c % 2) * 55),
            wall_orientation=ori, estimated_distance_m=round(dist + c * 2.0, 1), design_reason=reason,
        ))
    return IntegratedDesignAnalysis(
        detected_main_breaker_a=40,
        panel_x_pct=700, panel_y_pct=390,
        floor_summary="[사전학습 시뮬레이션] API 키 입력 시 실제 도면 가구를 직접 인식합니다",
        placements=placements,
    )


def _kr_font(size: int):
    for p in ["C:\\Windows\\Fonts\\malgunbd.ttf", "C:\\Windows\\Fonts\\malgun.ttf",
              "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf", "/System/Library/Fonts/AppleGothic.ttf"]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def create_sample_floorplan() -> Image.Image:
    img = Image.new("RGB", (900, 700), "#FAFAFA")
    d = ImageDraw.Draw(img)
    f = _kr_font(22)
    d.rectangle([40, 40, 860, 660], outline="#222222", width=6)
    d.line([40, 320, 380, 320], fill="#333333", width=4)
    d.line([380, 40, 380, 500], fill="#333333", width=4)
    d.line([620, 40, 620, 660], fill="#333333", width=4)
    d.line([40, 500, 380, 500], fill="#333333", width=4)
    for pos, txt in [((140, 140), "주방"), ((120, 390), "다용도실"), ((120, 560), "현관"),
                     ((470, 300), "거실"), ((700, 180), "안방"), ((700, 480), "욕실/방2")]:
        d.text(pos, txt, fill="#777777", font=f)
    return img


def _draw_element_symbol(d: ImageDraw.ImageDraw, tx: int, ty: int, meta: dict, ori: str, fc, show_label: bool, tag_txt: str):
    sym, col = meta["symbol"], meta["color"]
    if sym == "tv":
        bw, bh = (24, 76) if ori == "vertical" else (76, 24)
        d.rectangle([tx - bw // 2 - 2, ty - bh // 2 - 2, tx + bw // 2 + 2, ty + bh // 2 + 2], fill="#FFFFFF")
        d.rectangle([tx - bw // 2, ty - bh // 2, tx + bw // 2, ty + bh // 2], fill="#1E293B", outline="#DC2626", width=3)
        d.text((tx - 9, ty - 7), "TV", fill="#FFFFFF", font=fc)
        ly = ty + bh // 2 + 3
    elif sym == "light":
        r = 13
        d.ellipse([tx - r - 2, ty - r - 2, tx + r + 2, ty + r + 2], fill="#FFFFFF")
        d.ellipse([tx - r, ty - r, tx + r, ty + r], fill="#FFF8E1", outline=col, width=3)
        d.line([tx - 8, ty - 8, tx + 8, ty + 8], fill=col, width=2)
        d.line([tx - 8, ty + 8, tx + 8, ty - 8], fill=col, width=2)
        ly = ty + r + 3
    elif sym == "switch":
        r = 11
        d.rectangle([tx - r - 2, ty - r - 2, tx + r + 2, ty + r + 2], fill="#FFFFFF")
        d.rectangle([tx - r, ty - r, tx + r, ty + r], fill="#FEF3C7", outline="#D97706", width=2)
        d.text((tx - 6, ty - 7), "S", fill="#B45309", font=fc)
        ly = ty + r + 3
    elif sym == "outlet":
        r = 11
        d.ellipse([tx - r - 2, ty - r - 2, tx + r + 2, ty + r + 2], fill="#FFFFFF")
        d.ellipse([tx - r, ty - r, tx + r, ty + r], fill="#FFFFFF", outline="#DC2626", width=3)
        d.ellipse([tx - 4, ty - 4, tx + 4, ty + 4], fill="#DC2626")
        ly = ty + r + 3
    else:
        r = 14
        d.ellipse([tx - r - 2, ty - r - 2, tx + r + 2, ty + r + 2], fill="#FFFFFF")
        d.ellipse([tx - r, ty - r, tx + r, ty + r], fill=col, outline="#FFFFFF", width=2)
        d.text((tx - 10, ty - 7), meta["short"], fill="#FFFFFF", font=fc)
        ly = ty + r + 3

    if show_label:
        tw_px = len(tag_txt) * 10 + 10
        d.rectangle([tx - tw_px // 2, ly, tx + tw_px // 2, ly + 17], fill="#0F172A")
        d.text((tx - tw_px // 2 + 5, ly + 1), tag_txt, fill="#FFFFFF", font=fc)


def render_2d_placement_blueprint(
    floorplan_img: Image.Image,
    analysis: IntegratedDesignAnalysis,
    show_labels: bool = True,
) -> Image.Image:
    """
    [결과 1] 1번에서 업로드된 2D 평면도를 그대로 가져와, 배치되는 그 자리에 최적 설계 심볼만 깔끔하게 표시
    """
    base = floorplan_img.convert("RGB")
    tw = 900
    th = int(base.height * (tw / base.width))
    base = base.resize((tw, th), Image.Resampling.LANCZOS)

    hh, fh = 46, 96
    canvas = Image.new("RGB", (tw, th + hh + fh), "#FFFFFF")
    canvas.paste(base, (0, hh))
    d = ImageDraw.Draw(canvas)
    ft, fc = _kr_font(16), _kr_font(12)

    d.rectangle([0, 0, tw, hh], fill="#1E293B")
    d.text((16, 13), f"[결과 1] AI 2D 최적 배치 설계도  |  {analysis.floor_summary[:42]}", fill="#FFFFFF", font=ft)

    for idx, p in enumerate(analysis.placements, start=1):
        m = ELEMENT_DB.get(p.element_key, ELEMENT_DB["outlet"])
        tx = int((p.x_pct / 1000.0) * tw)
        ty = hh + int((p.y_pct / 1000.0) * th)
        lbl = f"{m['name'].split()[0]}"
        _draw_element_symbol(d, tx, ty, m, p.wall_orientation, fc, show_labels, lbl)

    ly = hh + th
    d.rectangle([0, ly, tw, ly + fh], fill="#F8FAFC", outline="#CBD5E1", width=2)
    d.text((16, ly + 10), "📌 [배치 심볼 범례]  TV:벽걸이매립  |  ⊗:전등  |  ◉:콘센트  |  S:스위치  |  원형컬러:전용가전", fill="#1E293B", font=fc)
    items_str = " | ".join(f"{i}.{ELEMENT_DB.get(p.element_key, ELEMENT_DB['outlet'])['name'].split()[0]}({p.room_name})" for i, p in enumerate(analysis.placements[:7], start=1))
    d.text((16, ly + 38), f"배치 목록: {items_str}", fill="#475569", font=fc)
    d.text((16, ly + 62), "※ 위 배치 위치를 바탕으로 [결과 2] 실제 시공용 전기도면(배선·단선결선도)이 자동 도출됩니다.", fill="#2563EB", font=fc)
    return canvas


def _draw_dashed_ortho(d: ImageDraw.ImageDraw, pts: List[Tuple[int, int]], color: str, width: int = 3):
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        dx, dy = x2 - x1, y2 - y1
        dist = math.hypot(dx, dy)
        if dist == 0:
            continue
        ux, uy, cur = dx / dist, dy / dist, 0.0
        while cur < dist:
            nxt = min(dist, cur + 10)
            d.line([(x1 + ux * cur, y1 + uy * cur), (x1 + ux * nxt, y1 + uy * nxt)], fill=color, width=width)
            cur += 16


def render_construction_electrical_diagram(
    floorplan_img: Image.Image,
    analysis: IntegratedDesignAnalysis,
    kec_result: Dict[str, Any],
) -> Image.Image:
    """
    [결과 2] 결과 1의 배치를 바탕으로 실제 시공자가 현장에서 보고 시공할 수 있는
    1) 평면 배선 시공도(Wiring Route) + 2) 분전반 단선결선도(Single-Line Diagram) 통합 도출
    """
    # 상단: 평면 배선 시공도 (배선 가시성을 위해 배경 도면을 은은하게 톤다운)
    base = floorplan_img.convert("RGB")
    tw = 960
    th = int(base.height * (tw / base.width))
    base = ImageEnhance.Brightness(base.resize((tw, th), Image.Resampling.LANCZOS)).enhance(1.18)
    white_overlay = Image.new("RGB", (tw, th), "#FFFFFF")
    base = Image.blend(base, white_overlay, alpha=0.28)

    circuits = kec_result.get("circuits", [])
    hh = 50
    sld_header = 44
    row_h = 46
    sld_h = sld_header + max(3, len(circuits)) * row_h + 60
    canvas = Image.new("RGB", (tw, hh + th + sld_h), "#FFFFFF")
    canvas.paste(base, (0, hh))
    d = ImageDraw.Draw(canvas)
    ft, fl, fc = _kr_font(17), _kr_font(14), _kr_font(12)

    # 1. 상단 타이틀
    d.rectangle([0, 0, tw, hh], fill="#0F172A")
    d.text((16, 14), f"[결과 2] 실제 시공용 전기도면 (배선 시공도 + KEC 단선결선도)  |  메인 MCCB {kec_result['main_breaker_a']}A", fill="#FFFFFF", font=ft)

    # 분전반 위치
    px = int((analysis.panel_x_pct / 1000.0) * tw)
    py = hh + int((analysis.panel_y_pct / 1000.0) * th)

    # 요소별 배선 경로 및 시공 스펙 표기
    tag_to_spec = {}
    for c in circuits:
        for it in c["items"]:
            tag_to_spec[it["tag"]] = (c["circuit_id"], c["wire_sq"], c["breaker_a"])

    for idx, p in enumerate(analysis.placements, start=1):
        m = ELEMENT_DB.get(p.element_key, ELEMENT_DB["outlet"])
        tag = f"{m['short']}{idx}"
        cid, w_sq, br_a = tag_to_spec.get(tag, ("P1", 2.5, 20))
        tx = int((p.x_pct / 1000.0) * tw)
        ty = hh + int((p.y_pct / 1000.0) * th)
        ex = px + ((idx % 5) - 2) * 7
        ey = ty + ((idx % 3) - 1) * 6

        if m["dedicated"]:
            d.line([(px, py), (ex, ey), (tx, ty)], fill=m["color"], width=4)
        else:
            _draw_dashed_ortho(d, [(px, py), (ex, ey), (tx, ty)], color=m["color"], width=3)

        # 배선 중간에 회로번호 + 전선규격 표기
        mx, my = (ex + tx) // 2, ey
        spec_txt = f"{cid}:{w_sq}sq"
        d.rectangle([mx - 28, my - 9, mx + 28, my + 8], fill="#FFFFFF", outline=m["color"], width=1)
        d.text((mx - 24, my - 8), spec_txt, fill="#0F172A", font=fc)

        _draw_element_symbol(d, tx, ty, m, p.wall_orientation, fc, True, f"{tag}({cid})")

    # 분전반(DB) CAD 심볼
    d.rectangle([px - 18, py - 12, px + 18, py + 12], fill="#FFFFFF", outline="#111111", width=3)
    d.polygon([(px - 18, py + 12), (px + 18, py - 12), (px + 18, py + 12)], fill="#111111")
    d.rectangle([px - 26, py + 14, px + 26, py + 31], fill="#DC2626")
    d.text((px - 22, py + 15), "분전반DB", fill="#FFFFFF", font=fc)

    # 2. 하단: 실제 시공용 분전반 단선결선도 (Single-Line Diagram)
    sy = hh + th
    d.rectangle([0, sy, tw, sy + sld_header], fill="#1E3A8A")
    d.text((16, sy + 12), "⚡ 분전반 단선결선도 (Single-Line Panel Schedule) — KEC 121.2 표준색상: L(갈) / N(청) / PE(녹황)", fill="#FFFFFF", font=fl)

    # 왼쪽 한전 인입 -> 메인 차단기 -> 세로 모선(Bus Bar)
    bus_top = sy + sld_header + 24
    bus_bot = sy + sld_h - 32
    bus_x = 240

    # 인입선 + 메인 MCCB 박스
    d.line([(30, (bus_top + bus_bot) // 2), (100, (bus_top + bus_bot) // 2)], fill="#0F172A", width=4)
    d.text((22, (bus_top + bus_bot) // 2 - 22), "단상2선 220V", fill="#0F172A", font=fc)
    d.rectangle([100, (bus_top + bus_bot) // 2 - 22, 195, (bus_top + bus_bot) // 2 + 22], fill="#FEF2F2", outline="#DC2626", width=2)
    d.text((110, (bus_top + bus_bot) // 2 - 16), "MAIN MCCB", fill="#DC2626", font=fc)
    d.text((118, (bus_top + bus_bot) // 2 + 2), f"2P {kec_result['main_breaker_a']}A", fill="#0F172A", font=fl)
    d.line([(195, (bus_top + bus_bot) // 2), (bus_x, (bus_top + bus_bot) // 2)], fill="#0F172A", width=4)

    # 세로 모선 (Bus Bar)
    d.line([(bus_x, bus_top), (bus_x, bus_bot)], fill="#0F172A", width=5)

    # 각 분기 회로별 ELB 차단기 + 전선관/전선 + 부하
    for idx, c in enumerate(circuits):
        cy = bus_top + 14 + idx * row_h
        d.line([(bus_x, cy), (285, cy)], fill="#0F172A", width=2)
        # 분기 ELB 차단기 심볼
        d.rectangle([285, cy - 13, 385, cy + 13], fill="#EFF6FF", outline="#2563EB", width=2)
        d.text((293, cy - 8), f"ELB {c['breaker_a']}A", fill="#1E40AF", font=fc)

        # 전선/배관 사양 선
        line_col = "#DC2626" if c["circuit_id"].startswith("D") else ("#FB8C00" if c["circuit_id"].startswith("L") else "#2563EB")
        d.line([(385, cy), (620, cy)], fill=line_col, width=3)
        d.text((395, cy - 17), f"CD16mm / HFIX {c['wire_sq']}sq x 3C (e={c['vd_pct']}%)", fill="#334155", font=fc)

        # 말단 부하 박스
        d.rectangle([620, cy - 14, 940, cy + 14], fill="#F8FAFC", outline="#64748B", width=1)
        d.text((628, cy - 8), f"[{c['circuit_id']}] {c['name'][:26]} ({c['w']}W)", fill="#0F172A", font=fc)

    d.text((16, sy + sld_h - 24), "※ 시공 주의: 욕실·주방·세탁실은 감도전류 30mA 고감도형 누전차단기(ELB) 및 단독 접지선(PE 녹황) 필수 결선", fill="#64748B", font=fc)
    return canvas
