#!/usr/bin/env python3
"""
scripts/build_region_seed.py
------------------------------
행정안전부 공공 API + 카카오 지오코딩 API 를 이용해
전국 행정구역 데이터를 수집하고 factory/seed_regions.sql 을 생성한다.

계층 구조
---------
    Tier 0  시도       17개   (서울특별시, 경기도, ...)
    Tier 1  시군구    ~250개  (강남구, 수원시, ...)
    Tier 2  읍면동  ~3500개  (대치동, 분당동, ...)

사용 API
--------
    행정구역 코드 (인증 불필요):
        https://grpc-proxy-server-mkvo6j4wsq-du.a.run.app/v1/regcodes

    카카오 지오코딩 (KAKAO_REST_API_KEY 필요):
        https://dapi.kakao.com/v2/local/search/keyword.json

필요 환경변수
-------------
    KAKAO_REST_API_KEY=...     # 카카오 개발자 REST API 키

Usage
-----
    # 기본 (서울·경기만, 빠른 확인용)
    python scripts/build_region_seed.py --sido 서울 경기

    # 전국
    python scripts/build_region_seed.py --all

    # 읍면동 제외 (시군구까지만)
    python scripts/build_region_seed.py --all --no-dong

    # 출력 파일 지정
    python scripts/build_region_seed.py --all --output factory/seed_regions.sql

    # GPS 좌표 없이 생성 (카카오 키 없을 때)
    python scripts/build_region_seed.py --all --no-gps
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_REG_API   = "https://grpc-proxy-server-mkvo6j4wsq-du.a.run.app/v1/regcodes"
_KAKAO_API = "https://dapi.kakao.com/v2/local/search/keyword.json"
_EDU_INDEX = Path(__file__).parent / "edu_index.json"
_OUTPUT    = Path(__file__).parent.parent / "factory" / "seed_regions.sql"

_KAKAO_KEY = os.getenv("KAKAO_REST_API_KEY", "")
_DIM_ID    = 1      # category_id for 지역

# 시도 표시명 (풀네임 → 짧은 이름)
_SIDO_DISPLAY: dict[str, str] = {
    "서울특별시":   "서울",
    "부산광역시":   "부산",
    "대구광역시":   "대구",
    "인천광역시":   "인천",
    "광주광역시":   "광주",
    "대전광역시":   "대전",
    "울산광역시":   "울산",
    "세종특별자치시": "세종",
    "경기도":       "경기",
    "충청북도":     "충북",
    "충청남도":     "충남",
    "전라북도":     "전북",
    "전라남도":     "전남",
    "경상북도":     "경북",
    "경상남도":     "경남",
    "강원특별자치도": "강원",
    "제주특별자치도": "제주",
}

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _reg_fetch(parent_code: str = "0", detail: bool = False) -> list[dict]:
    """행정구역 코드 API 조회."""
    params = {"regcode_pattern": f"{parent_code}*", "is_detail": str(detail).lower()}
    r = requests.get(_REG_API, params=params, timeout=15)
    r.raise_for_status()
    return r.json().get("regcodes", [])


def _kakao_gps(query: str) -> tuple[float, float] | None:
    """카카오 키워드 검색으로 GPS 좌표 반환. 실패 시 None."""
    if not _KAKAO_KEY:
        return None
    headers = {"Authorization": f"KakaoAK {_KAKAO_KEY}"}
    params  = {"query": query, "size": 1}
    try:
        r = requests.get(_KAKAO_API, headers=headers, params=params, timeout=10)
        docs = r.json().get("documents", [])
        if docs:
            return float(docs[0]["y"]), float(docs[0]["x"])   # lat, lng
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def _strip_suffix(name: str) -> str:
    """'강남구' → '강남',  '수원시' → '수원',  '대치동' → '대치' 등."""
    return re.sub(r"(특별시|광역시|특별자치시|특별자치도|도|시|군|구|읍|면|동|리)$", "", name)


def collect_sido() -> list[dict]:
    """Tier 0 — 시도 17개."""
    rows = _reg_fetch("0")
    result = []
    for i, r in enumerate(rows, start=1):
        name = r["name"]
        display = _SIDO_DISPLAY.get(name, _strip_suffix(name))
        result.append({
            "code":         r["code"],
            "value":        name,
            "display":      display,
            "tier":         0,
            "sort_order":   i,
            "parent_value": None,
        })
    return result


def collect_sigungu(sido_list: list[dict], target_sido: list[str] | None) -> list[dict]:
    """Tier 1 — 시군구."""
    result = []
    sort_base = 100
    for sido in sido_list:
        if target_sido and sido["display"] not in target_sido and sido["value"] not in target_sido:
            continue
        rows = _reg_fetch(sido["code"][:2])
        sigungu_rows = [r for r in rows if r["code"][2:5] != "000" and r["code"][5:] == "00000"]
        for i, r in enumerate(sigungu_rows, start=1):
            name    = r["name"].split()[-1]   # '서울특별시 강남구' → '강남구'
            display = _strip_suffix(name)
            result.append({
                "code":         r["code"],
                "value":        name,
                "display":      display,
                "tier":         1,
                "sort_order":   sort_base + i,
                "parent_value": sido["value"],
                "sido_display": sido["display"],
            })
        sort_base += 100
    return result


def collect_dong(sigungu_list: list[dict]) -> list[dict]:
    """Tier 2 — 읍면동."""
    result = []
    for sg in sigungu_list:
        prefix = sg["code"][:5]
        rows   = _reg_fetch(prefix)
        dong_rows = [r for r in rows if r["code"][5:] != "00000"]
        for i, r in enumerate(dong_rows, start=1):
            name    = r["name"].split()[-1]
            display = _strip_suffix(name)
            result.append({
                "code":         r["code"],
                "value":        name,
                "display":      display,
                "tier":         2,
                "sort_order":   i,
                "parent_value": sg["value"],
                "sido_display": sg.get("sido_display", ""),
            })
    return result


# ---------------------------------------------------------------------------
# GPS enrichment
# ---------------------------------------------------------------------------

def enrich_gps(
    regions: list[dict],
    fetch_gps: bool,
    delay: float = 0.15,
) -> list[dict]:
    """카카오 API 로 GPS 좌표를 채운다."""
    if not fetch_gps:
        for r in regions:
            r["lat"] = None
            r["lng"] = None
        return regions

    for i, r in enumerate(regions):
        sido = r.get("sido_display", "")
        query = f"{sido} {r['value']}".strip()
        coords = _kakao_gps(query)
        r["lat"] = round(coords[0], 4) if coords else None
        r["lng"] = round(coords[1], 4) if coords else None
        if (i + 1) % 50 == 0:
            print(f"  GPS {i+1}/{len(regions)} 완료...", flush=True)
        time.sleep(delay)
    return regions


# ---------------------------------------------------------------------------
# edu_index lookup
# ---------------------------------------------------------------------------

def load_edu_index() -> dict[str, int]:
    if _EDU_INDEX.exists():
        data = json.loads(_EDU_INDEX.read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if not k.startswith("_")}
    return {}


def get_edu_index(name: str, edu_map: dict[str, int], tier: int) -> int:
    """시군구 이름으로 교육열 지수 조회. 미등록은 tier 별 기본값."""
    if name in edu_map:
        return edu_map[name]
    defaults = {0: 3, 1: 2, 2: 2}
    return defaults.get(tier, 2)


# ---------------------------------------------------------------------------
# SQL generation
# ---------------------------------------------------------------------------

def _json_obj(**kwargs) -> str:
    """MySQL JSON_OBJECT(...) 문자열 생성."""
    parts = []
    for k, v in kwargs.items():
        if v is None:
            parts.append(f"'{k}',NULL")
        elif isinstance(v, str):
            parts.append(f"'{k}','{v}'")
        else:
            parts.append(f"'{k}',{v}")
    return "JSON_OBJECT(" + ",".join(parts) + ")"


def build_sql(
    sido_list:    list[dict],
    sigungu_list: list[dict],
    dong_list:    list[dict],
    edu_map:      dict[str, int],
) -> str:
    lines = [
        "-- ============================================================",
        "-- seed_regions.sql — 전국 행정구역 데이터 (자동 생성)",
        "--",
        "-- 생성 스크립트: scripts/build_region_seed.py",
        "--",
        "-- Tier 0  시도",
        "-- Tier 1  시군구",
        "-- Tier 2  읍면동",
        "--",
        "-- metadata JSON",
        "--   sido        STRING  시도 표시명",
        "--   lat / lng   FLOAT   중심 좌표 (WGS84, 카카오 지오코딩)",
        "--   edu_index   INT     교육열 지수 1~5 (scripts/edu_index.json)",
        "-- ============================================================",
        "",
        "SET NAMES utf8mb4;",
        "SET FOREIGN_KEY_CHECKS = 0;",
        "",
    ]

    # ── Tier 0: 시도 ────────────────────────────────────────────────
    lines += [
        "-- ------------------------------------------------------------",
        "-- Tier 0 — 시도",
        "-- ------------------------------------------------------------",
        f"INSERT IGNORE INTO keywords",
        f"    (category_id, value, display_value, tier, sort_order, metadata)",
        "VALUES",
    ]
    sido_rows = []
    for r in sido_list:
        meta = _json_obj(
            sido   = r["display"],
            lat    = r.get("lat"),
            lng    = r.get("lng"),
            edu_index = get_edu_index(r["value"], edu_map, 0),
        )
        sido_rows.append(
            f"({_DIM_ID},'{r['value']}','{r['display']}',0,{r['sort_order']},{meta})"
        )
    lines.append(",\n".join(sido_rows) + ";")
    lines.append("")

    # ── Tier 1: 시군구 ──────────────────────────────────────────────
    lines += [
        "-- ------------------------------------------------------------",
        "-- Tier 1 — 시군구 (parent_id → 시도)",
        "-- ------------------------------------------------------------",
        "INSERT IGNORE INTO keywords",
        "    (category_id, parent_id, value, display_value, tier, sort_order, metadata)",
    ]
    sg_rows = []
    for r in sigungu_list:
        meta = _json_obj(
            sido      = r.get("sido_display", ""),
            lat       = r.get("lat"),
            lng       = r.get("lng"),
            edu_index = get_edu_index(r["value"], edu_map, 1),
        )
        sg_rows.append(
            f"((SELECT id FROM keywords WHERE category_id={_DIM_ID} AND value='{r['parent_value']}' LIMIT 1),"
            f"'{r['value']}','{r['display']}',1,{r['sort_order']},{meta})"
        )
    # subquery 형태라 VALUES 대신 SELECT UNION
    # MySQL INSERT ... SELECT 방식으로 전환
    lines[-1] = (
        "INSERT IGNORE INTO keywords\n"
        "    (category_id, parent_id, value, display_value, tier, sort_order, metadata)\n"
        "SELECT\n"
        f"    {_DIM_ID}, p.id, sub.value, sub.display, sub.tier, sub.sort_order, sub.meta\n"
        "FROM (\n"
        "    SELECT * FROM (VALUES"
    )
    sg_value_rows = []
    for r in sigungu_list:
        meta = _json_obj(
            sido      = r.get("sido_display", ""),
            lat       = r.get("lat"),
            lng       = r.get("lng"),
            edu_index = get_edu_index(r["value"], edu_map, 1),
        )
        sg_value_rows.append(
            f"        ROW('{r['parent_value']}','{r['value']}','{r['display']}',1,{r['sort_order']},{meta})"
        )
    lines[-1] += "\n" + ",\n".join(sg_value_rows)
    lines[-1] += (
        "\n    ) AS t(parent_value, value, display, tier, sort_order, meta)\n"
        ") sub\n"
        f"JOIN keywords p ON p.category_id={_DIM_ID} AND p.value=sub.parent_value;\n"
    )
    lines.append("")

    # ── Tier 2: 읍면동 ──────────────────────────────────────────────
    if dong_list:
        lines += [
            "-- ------------------------------------------------------------",
            "-- Tier 2 — 읍면동 (parent_id → 시군구)",
            "-- ------------------------------------------------------------",
        ]
        # 시군구별로 묶어서 INSERT
        from itertools import groupby
        dong_by_sg: dict[str, list] = {}
        for d in dong_list:
            dong_by_sg.setdefault(d["parent_value"], []).append(d)

        for sg_name, dongs in dong_by_sg.items():
            if not dongs:
                continue
            lines.append(
                "INSERT IGNORE INTO keywords\n"
                "    (category_id, parent_id, value, display_value, tier, sort_order, metadata)"
            )
            select_parts = []
            for d in dongs:
                meta = _json_obj(
                    lat       = d.get("lat"),
                    lng       = d.get("lng"),
                    edu_index = get_edu_index(sg_name, edu_map, 2),
                )
                select_parts.append(
                    f"SELECT {_DIM_ID},p.id,'{d['value']}','{d['display']}',2,{d['sort_order']},{meta}\n"
                    f"    FROM keywords p WHERE p.category_id={_DIM_ID} AND p.value='{sg_name}'"
                )
            lines.append(" UNION ALL\n".join(select_parts) + ";")
            lines.append("")

    lines += [
        "SET FOREIGN_KEY_CHECKS = 1;",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="전국 행정구역 시딩 SQL 생성")
    parser.add_argument("--all",     action="store_true", help="전국 (기본: 서울·경기)")
    parser.add_argument("--sido",    nargs="+",           help="특정 시도만 (예: 서울 경기 부산)")
    parser.add_argument("--no-dong", action="store_true", help="읍면동 제외 (시군구까지만)")
    parser.add_argument("--no-gps",  action="store_true", help="GPS 좌표 조회 생략")
    parser.add_argument("--output",  default=str(_OUTPUT), help="출력 파일 경로")
    parser.add_argument("--delay",   type=float, default=0.15, help="카카오 API 호출 간격(초)")
    args = parser.parse_args()

    fetch_gps = not args.no_gps
    if fetch_gps and not _KAKAO_KEY:
        print("⚠️  KAKAO_REST_API_KEY 미설정 — GPS 좌표 없이 생성합니다.")
        fetch_gps = False

    edu_map = load_edu_index()
    print(f"✅ edu_index.json 로드: {len(edu_map)}개 항목")

    # 시도 수집
    print("📡 시도 조회 중...")
    sido_list = collect_sido()
    print(f"   → {len(sido_list)}개 시도")

    # 필터링
    if not args.all:
        target = args.sido or ["서울", "경기"]
        sido_list_filtered = [
            s for s in sido_list
            if s["display"] in target or s["value"] in target
        ]
    else:
        sido_list_filtered = sido_list

    # GPS: 시도
    if fetch_gps:
        print("🌍 시도 GPS 조회 중...")
        sido_list_filtered = enrich_gps(sido_list_filtered, True, args.delay)

    # 시군구 수집
    print("📡 시군구 조회 중...")
    target_sido = None if args.all else [s["display"] for s in sido_list_filtered]
    sigungu_list = collect_sigungu(sido_list, target_sido)
    print(f"   → {len(sigungu_list)}개 시군구")

    # GPS: 시군구
    if fetch_gps:
        print("🌍 시군구 GPS 조회 중 (시간이 걸립니다)...")
        sigungu_list = enrich_gps(sigungu_list, True, args.delay)

    # 읍면동 수집
    dong_list: list[dict] = []
    if not args.no_dong:
        print("📡 읍면동 조회 중 (시간이 걸립니다)...")
        dong_list = collect_dong(sigungu_list)
        print(f"   → {len(dong_list)}개 읍면동")

        if fetch_gps:
            print("🌍 읍면동 GPS 조회 중 (매우 오래 걸립니다)...")
            dong_list = enrich_gps(dong_list, True, args.delay)

    # SQL 생성
    print("✍️  SQL 생성 중...")
    sql = build_sql(sido_list_filtered, sigungu_list, dong_list, edu_map)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(sql, encoding="utf-8")

    print(f"\n✅ 완료: {out_path}")
    print(f"   시도:   {len(sido_list_filtered)}개")
    print(f"   시군구: {len(sigungu_list)}개")
    print(f"   읍면동: {len(dong_list)}개")
    print(f"\n다음 단계:")
    print(f"  bash ./run/factory.sh db-reset   # 스키마 + seed.sql 적용")
    print(f"  # seed_regions.sql 은 seed.sql 에서 자동 포함됨")


if __name__ == "__main__":
    main()
