import json, os
BASE = os.path.dirname(os.path.abspath(__file__))

# v2 로드
v2_path = os.path.join(BASE, "counseling_db_v2.json")
with open(v2_path, "r", encoding="utf-8") as f:
    v2 = json.load(f)
print(f"기존: {len(v2['chunks'])}개 청크")

# 패치 로드
with open(os.path.join(BASE, "ld_patch.json"), "r", encoding="utf-8") as f:
    patch = json.load(f)

# 이미 추가됐는지 확인
existing_ids = {c["id"] for c in v2["chunks"]}
new_count = 0
for c in patch["new_chunks"]:
    if c["id"] not in existing_ids:
        v2["chunks"].append(c)
        new_count += 1
print(f"새 청크: {new_count}개 추가")

# 구조에 파트 추가
part_ids = [p["id"] for p in v2["structure"]]
if patch["new_part"]["id"] not in part_ids:
    v2["structure"].append(patch["new_part"])
    print(f"새 파트 추가: {patch['new_part']['title']}")

# 시나리오 추가
for k, v in patch["new_scenario"].items():
    v2["counseling_scenarios"][k] = v
    print(f"새 시나리오: {k}")

# 메타 업데이트
v2["meta"] = patch["updated_meta"]

# 저장
with open(v2_path, "w", encoding="utf-8") as f:
    json.dump(v2, f, ensure_ascii=False, separators=(",", ":"))

sz = os.path.getsize(v2_path)
print(f"\n완료! {sz/1024:.1f}KB, {len(v2['chunks'])}개 청크")
