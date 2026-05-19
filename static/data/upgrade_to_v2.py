#!/usr/bin/env python3
# counseling_db.json + upgrade_data.json -> counseling_db_v2.json
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))

# 1) v1 읽기
with open(os.path.join(BASE, "counseling_db.json"), "r", encoding="utf-8") as f:
    v1 = json.load(f)
print(f"v1 로드: {len(v1['chunks'])}개 청크")

# 2) 업그레이드 데이터 읽기
with open(os.path.join(BASE, "upgrade_data.json"), "r", encoding="utf-8") as f:
    upgrade = json.load(f)
print(f"업그레이드 데이터 로드: {len(upgrade.get('counseling_scenarios', {}))}개 상담 시나리오")

# 3) structure의 chunk_ids에서 section 매핑 직접 생성
chunk_map = {}
for part in upgrade["structure"]:
    for sec in part["sections"]:
        info = {
            "part_id": part["id"],
            "section_id": sec["id"],
            "section_title": sec["title"]
        }
        for cid in sec.get("chunk_ids", []):
            chunk_map[cid] = info

# front-matter (표지/목차/발간사)
for cid in range(0, 7):
    chunk_map[cid] = {"part_id": "front", "section_id": "front-matter", "section_title": "표지/목차/발간사"}

# back-matter (부록 표지, 크레딧)
for cid in [153, 167, 168]:
    chunk_map[cid] = {"part_id": "appendix", "section_id": "back-matter", "section_title": "부록/크레딧"}

print(f"섹션 매핑 생성: {len(chunk_map)}개")

# 4) 청크에 section 정보 추가
mapped = 0
for c in v1["chunks"]:
    cid = c["id"]
    if cid in chunk_map:
        c["section"] = chunk_map[cid]
        mapped += 1
print(f"섹션 매핑 적용: {mapped}/{len(v1['chunks'])}개 청크")

# 5) v2 조립
v2 = {
    "meta": upgrade["meta"],
    "structure": upgrade["structure"],
    "counseling_scenarios": upgrade["counseling_scenarios"],
    "chunks": v1["chunks"]
}

# 6) 저장
out_path = os.path.join(BASE, "counseling_db_v2.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(v2, f, ensure_ascii=False, separators=(",", ":"))

size = os.path.getsize(out_path)
print(f"\n counseling_db_v2.json 생성 완료!")
print(f"   크기: {size/1024:.1f}KB, 청크: {len(v2['chunks'])}개")
print(f"   섹션 매핑: {mapped}개, 하위섹션: {upgrade['meta']['total_subsections']}개")
print(f"   상담시나리오: {len(upgrade['counseling_scenarios'])}개")
