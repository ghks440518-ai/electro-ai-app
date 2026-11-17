# backend/kec_engine.py
import math
from dataclasses import dataclass
from typing import List, Dict, Any

# 검색 키워드, KEC 특성, 기본 참고 자재가 포함 설계요소 DB
ELEMENT_DB: Dict[str, Dict[str, Any]] = {
    "outlet": {
        "name": "2구 접지 콘센트", "short": "C", "symbol": "outlet",
        "keywords": "콘센트 멀티탭 전원 2구 벽부 콘센트",
        "power_w": 1000, "dedicated": False, "type": "power", "color": "#1E88E5",
        "default_mat_price": 8000, "height_guide": "바닥+30cm",
    },
    "lighting": {
        "name": "LED 전등 / 거실등", "short": "L", "symbol": "light",
        "keywords": "전등 조명 등기구 거실등 방등 다운라이트 led",
        "power_w": 250, "dedicated": False, "type": "lighting", "color": "#FB8C00",
        "default_mat_price": 45000, "height_guide": "천장 매립(스위치 120cm)",
    },
    "switch": {
        "name": "조명 스위치 (2구/3구)", "short": "SW", "symbol": "switch",
        "keywords": "스위치 전등스위치 터치스위치 IoT",
        "power_w": 50, "dedicated": False, "type": "lighting", "color": "#F59E0B",
        "default_mat_price": 12000, "height_guide": "출입문 옆 바닥+120cm",
    },
    "tv": {
        "name": "TV (벽걸이 매립 콘센트)", "short": "TV", "symbol": "tv",
        "keywords": "tv 티비 텔레비전 벽걸이 아트월 거실tv",
        "power_w": 350, "dedicated": False, "type": "power", "color": "#2563EB",
        "default_mat_price": 18000, "height_guide": "바닥+110cm(브라켓 회피)",
    },
    "refrigerator": {
        "name": "냉장고 / 김치냉장고", "short": "REF", "symbol": "app",
        "keywords": "냉장고 김치냉장고 비스포크 주방가전",
        "power_w": 600, "dedicated": False, "type": "power", "color": "#00897B",
        "default_mat_price": 10000, "height_guide": "바닥+50cm(상시전원 권장)",
    },
    "aircon": {
        "name": "에어컨 (시스템/스탠드)", "short": "AC", "symbol": "app",
        "keywords": "에어컨 냉방기 시스템에어컨 스탠드 벽걸이에어컨",
        "power_w": 2500, "dedicated": True, "type": "power", "color": "#E53935",
        "default_mat_price": 15000, "height_guide": "전용 단독배선(바닥+30cm/천장)",
    },
    "induction": {
        "name": "인덕션 / 전기레인지", "short": "IND", "symbol": "app",
        "keywords": "인덕션 전기레인지 하이라이트 주방 3구",
        "power_w": 3400, "dedicated": True, "type": "power", "color": "#DC2626",
        "default_mat_price": 20000, "height_guide": "싱크대 하부 전용 직결/단독",
    },
    "washer_dryer": {
        "name": "세탁기 / 의류건조기", "short": "WD", "symbol": "app",
        "keywords": "세탁기 건조기 워시타워 다용도실 베란다",
        "power_w": 2000, "dedicated": True, "type": "power", "color": "#E53935",
        "default_mat_price": 14000, "height_guide": "바닥+100cm(방우형 커버)",
    },
    "dishwasher": {
        "name": "식기세척기", "short": "DW", "symbol": "app",
        "keywords": "식기세척기 식세기 주방 싱크대",
        "power_w": 1800, "dedicated": False, "type": "power", "color": "#0284C7",
        "default_mat_price": 10000, "height_guide": "싱크대 하부 접지 콘센트",
    },
    "bidet": {
        "name": "욕실 방우 콘센트 (비데)", "short": "WP", "symbol": "outlet",
        "keywords": "욕실 화장실 비데 방우 콘센트",
        "power_w": 800, "dedicated": False, "type": "power", "color": "#0EA5E9",
        "default_mat_price": 15000, "height_guide": "변기 옆 바닥+45cm(방우형/ELB필수)",
    },
    "lan_intercom": {
        "name": "월패드 / 통신·랜 콘센트", "short": "LAN", "symbol": "outlet",
        "keywords": "인터넷 랜선 공유기 월패드 인터폰 통신",
        "power_w": 100, "dedicated": False, "type": "power", "color": "#6366F1",
        "default_mat_price": 16000, "height_guide": "통합 매립박스(약전 분리배관)",
    },
}

# KEC HFIX (XLPE 90도, 공사방법 B1 매입전선관, 30도 기준) 허용전류
HFIX_B1_AMP = {1.5: 23.0, 2.5: 31.0, 4.0: 42.0, 6.0: 54.0, 10.0: 75.0}
STD_BREAKERS = [15, 20, 30, 40, 50, 60, 75, 100]

# cf.3) KEC 기반 전기공사 필수 자재 표준 단가 (원)
KEC_MATERIAL_PRICES = {
    "HFIX_1.5": 450,
    "HFIX_2.5": 650,
    "HFIX_4.0": 1050,
    "HFIX_6.0": 1600,
    "HFIX_10.0": 2700,
    "CD_16MM": 450,
    "ELB_20": 12000,
    "ELB_30": 14000,
    "ELB_40": 18000,
    "ELB_50": 22000,
    "BOX_PER_POINT": 3500,     # 스위치/콘센트 매립 철/합성수지 복스
    "SUB_MAT_PER_CIRCUIT": 8500,  # 와고 커넥터, 새들, 절연테이프 등 KEC 부자재
}


@dataclass
class DesignElementInput:
    element_key: str
    room_name: str
    user_mat_price: int          # 2단계에서 사용자가 직접 입력한 구입 자재 단가
    quantity: int = 1
    distance_m: float = 10.0


def search_elements(query: str) -> List[str]:
    """2단계 검색창용 필터 함수"""
    q = (query or "").strip().lower()
    if not q:
        return list(ELEMENT_DB.keys())
    matched = []
    for k, meta in ELEMENT_DB.items():
        hay = f"{meta['name']} {meta['keywords']} {k}".lower()
        if q in hay:
            matched.append(k)
    return matched


def _select_kec_spec(power_w: int, distance_m: float, c_type: str) -> Dict[str, Any]:
    design_i = round(power_w / 220.0, 2)
    breaker_a = next((b for b in STD_BREAKERS if b >= design_i * 1.15), 100)
    max_vd = 3.0 if c_type == "lighting" else 5.0
    min_sq = 1.5 if c_type == "lighting" else 2.5

    chosen_sq, chosen_vd = 10.0, 0.0
    for sq in sorted(HFIX_B1_AMP.keys()):
        if sq < min_sq:
            continue
        iz = HFIX_B1_AMP[sq] * 0.80  # 복수회로 집합감소계수 0.8 적용
        vd_pct = round(((35.6 * distance_m * design_i) / (1000.0 * sq) / 220.0) * 100.0, 2)
        if breaker_a <= iz and vd_pct <= max_vd:
            chosen_sq, chosen_vd = sq, vd_pct
            break

    return {
        "design_i": design_i,
        "breaker_a": breaker_a,
        "wire_sq": chosen_sq,
        "vd_pct": chosen_vd,
        "wire_color_code": "L:갈 / N:청 / PE:녹황",
    }


def calculate_kec_and_cost(
    placed_elements: List[DesignElementInput],
    labor_per_person: int,
    worker_count: int,
    work_days: float = 1.0,
    main_breaker_a: int = 40,
    loss_rate: float = 0.20,
) -> Dict[str, Any]:
    """
    2단계(사용자 자재가격) + 3단계(인건비×인원수×일수) + cf.3(KEC 필수 공사자재 목록) 통합 산출
    """
    circuits, shared_pwr, shared_lgt = [], [], []
    user_mat_items = []
    user_mat_total = 0

    for idx, el in enumerate(placed_elements, start=1):
        meta = ELEMENT_DB.get(el.element_key, ELEMENT_DB["outlet"])
        tag = f"{meta['short']}{idx}"

        # 2단계 사용자 구입 자재 비용 합산
        u_sub = int(el.user_mat_price) * int(el.quantity)
        user_mat_total += u_sub
        user_mat_items.append({
            "구분": "사용자 구입자재",
            "품목": f"{meta['name']} ({el.room_name})",
            "수량": f"{el.quantity}개",
            "단가": f"{int(el.user_mat_price):,}원",
            "금액": u_sub,
        })

        total_item_w = meta["power_w"] * int(el.quantity)
        row = {
            "tag": tag, "key": el.element_key, "name": meta["name"],
            "room": el.room_name, "dist": el.distance_m, "w": total_item_w,
        }
        if meta["dedicated"]:
            circuits.append({
                "circuit_id": f"D{len(circuits)+1}",
                "name": f"단독 [{tag}] {meta['name']} ({el.room_name})",
                "items": [row], "w": total_item_w, "dist": el.distance_m, "type": meta["type"],
            })
        elif meta["type"] == "lighting":
            shared_lgt.append(row)
        else:
            shared_pwr.append(row)

    # 일반 전열 그룹화 (회로당 최대 2,600W 이하)
    if shared_pwr:
        chunk, cw, md, ci = [], 0, 0.0, 1
        for it in shared_pwr:
            if chunk and cw + it["w"] > 2600:
                circuits.append({
                    "circuit_id": f"P{ci}",
                    "name": f"전열 분기 #{ci} ({', '.join(x['tag'] for x in chunk)})",
                    "items": chunk, "w": cw, "dist": md, "type": "power",
                })
                chunk, cw, md, ci = [], 0, 0.0, ci + 1
            chunk.append(it)
            cw += it["w"]
            md = max(md, it["dist"])
        if chunk:
            circuits.append({
                "circuit_id": f"P{ci}",
                "name": f"전열 분기 #{ci} ({', '.join(x['tag'] for x in chunk)})",
                "items": chunk, "w": cw, "dist": md, "type": "power",
            })

    # 조명 회로 그룹화
    if shared_lgt:
        circuits.append({
            "circuit_id": "L1",
            "name": f"전등(조명) 분기 ({', '.join(x['tag'] for x in shared_lgt)})",
            "items": shared_lgt,
            "w": sum(x["w"] for x in shared_lgt),
            "dist": max(x["dist"] for x in shared_lgt),
            "type": "lighting",
        })

    # KEC 기반 회로 스펙 및 필수 공사 자재 물량 산출
    circuit_specs, wire_m, breakers = [], {}, {}
    total_cd_m, total_added_w = 0.0, 0

    for c in circuits:
        total_added_w += c["w"]
        sp = _select_kec_spec(c["w"], c["dist"], c["type"])
        circuit_specs.append({**c, **sp})

        # 단상 2선(L,N) + 보호도체(PE) = 3가닥 + 분전반 결선여유 2m + 현장 로스율
        w_len = round((c["dist"] * 3 + 2.0) * (1.0 + loss_rate), 1)
        sq = sp["wire_sq"]
        wire_m[sq] = round(wire_m.get(sq, 0.0) + w_len, 1)

        total_cd_m += round(c["dist"] * 1.15, 1)
        breakers[sp["breaker_a"]] = breakers.get(sp["breaker_a"], 0) + 1

    kec_mat_items, kec_mat_total = [], 0

    for sq, meters in sorted(wire_m.items()):
        up = KEC_MATERIAL_PRICES.get(f"HFIX_{sq}", 1000)
        sub = int(meters * up)
        kec_mat_total += sub
        kec_mat_items.append({
            "구분": "KEC 배선", "품목": f"HFIX 절연전선 {sq}sq (L갈/N청/PE녹황)",
            "수량": f"{meters}m (100m {math.ceil(meters/100)}롤)", "단가": f"{up:,}원/m", "금액": sub,
        })

    cd_sub = int(total_cd_m * KEC_MATERIAL_PRICES["CD_16MM"])
    kec_mat_total += cd_sub
    kec_mat_items.append({
        "구분": "KEC 배관", "품목": "난연 CD전선관 (16mm)",
        "수량": f"{round(total_cd_m, 1)}m", "단가": f"{KEC_MATERIAL_PRICES['CD_16MM']:,}원/m", "금액": cd_sub,
    })

    for b_a, cnt in sorted(breakers.items()):
        up = KEC_MATERIAL_PRICES.get(f"ELB_{b_a}", 15000)
        sub = cnt * up
        kec_mat_total += sub
        kec_mat_items.append({
            "구분": "KEC 차단기", "품목": f"누전차단기 ELB 2P {b_a}A (30mA)",
            "수량": f"{cnt}개", "단가": f"{up:,}원", "금액": sub,
        })

    total_points = sum(int(el.quantity) for el in placed_elements)
    box_sub = total_points * KEC_MATERIAL_PRICES["BOX_PER_POINT"]
    kec_mat_total += box_sub
    kec_mat_items.append({
        "구분": "KEC 매립함", "품목": "매립 스위치/콘센트 복스",
        "수량": f"{total_points}개", "단가": f"{KEC_MATERIAL_PRICES['BOX_PER_POINT']:,}원", "금액": box_sub,
    })

    aux_sub = len(circuit_specs) * KEC_MATERIAL_PRICES["SUB_MAT_PER_CIRCUIT"]
    kec_mat_total += aux_sub
    kec_mat_items.append({
        "구분": "KEC 부자재", "품목": "와고커넥터/새들/절연테이프 일체",
        "수량": f"{len(circuit_specs)}회로분", "단가": f"{KEC_MATERIAL_PRICES['SUB_MAT_PER_CIRCUIT']:,}원", "금액": aux_sub,
    })

    # 3단계 인건비 계산 (1인당 인건비 × 공사 총 인원수 × 공사 일수)
    labor_total = int(labor_per_person * worker_count * work_days)

    # 메인 차단기 대비 안전 진단
    peak_a = round(((1000 + total_added_w) * 0.70) / 220.0, 1)
    usage_pct = round((peak_a / main_breaker_a) * 100, 1) if main_breaker_a > 0 else 0.0
    status = "위험" if usage_pct >= 95 else ("주의" if usage_pct >= 75 else "안전")

    return {
        "final_total_cost": user_mat_total + kec_mat_total + labor_total,
        "user_mat_total": user_mat_total,
        "kec_mat_total": kec_mat_total,
        "labor_total": labor_total,
        "labor_detail": {
            "labor_per_person": labor_per_person,
            "worker_count": worker_count,
            "work_days": work_days,
        },
        "user_mat_items": user_mat_items,
        "kec_mat_items": kec_mat_items,
        "circuits": circuit_specs,
        "safety_status": status,
        "peak_a": peak_a,
        "main_breaker_a": main_breaker_a,
        "usage_pct": usage_pct,
    }
