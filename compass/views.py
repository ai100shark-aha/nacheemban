import json
import os
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / 'static' / 'data' / 'univ_db.json'

def _load_db():
    """JSON DB 파일 로드"""
    if DB_PATH.exists():
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def _save_db(data):
    """JSON DB 파일 저장"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

def index(request):
    """메인 페이지"""
    return render(request, 'index.html')

def get_db(request):
    """DB JSON 반환"""
    db = _load_db()
    return JsonResponse(db, safe=False, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
def update_db(request):
    """DB 전체 교체"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        data = json.loads(request.body)
        if not isinstance(data, list):
            return JsonResponse({'error': 'JSON 배열이 필요합니다'}, status=400)
        _save_db(data)
        return JsonResponse({
            'ok': True,
            'message': f'{len(data)}개 대학 DB 업데이트 완료',
            'count': len(data)
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON 파싱 실패'}, status=400)

@csrf_exempt
def merge_db(request):
    """DB 병합 (기존에 추가/갱신)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        new_data = json.loads(request.body)
        if not isinstance(new_data, list):
            return JsonResponse({'error': 'JSON 배열이 필요합니다'}, status=400)
        
        db = _load_db()
        added, updated = 0, 0
        
        for new_u in new_data:
            idx = next((i for i, u in enumerate(db) if u.get('nm') == new_u.get('nm')), -1)
            if idx >= 0:
                db[idx] = new_u
                updated += 1
            else:
                db.append(new_u)
                added += 1
        
        _save_db(db)
        return JsonResponse({
            'ok': True,
            'message': f'{added}개 추가, {updated}개 갱신',
            'added': added,
            'updated': updated,
            'total': len(db)
        })
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON 파싱 실패'}, status=400)

def export_db(request):
    """DB JSON 다운로드"""
    db = _load_db()
    response = HttpResponse(
        json.dumps(db, ensure_ascii=False, indent=2),
        content_type='application/json; charset=utf-8'
    )
    response['Content-Disposition'] = 'attachment; filename="hakjong_db.json"'
    return response
