import json
import os
from datetime import datetime
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / 'static' / 'data' / 'univ_db.json'
LOG_PATH = Path(__file__).resolve().parent.parent / 'static' / 'data' / 'contrib_log.json'

def _load_db():
    if DB_PATH.exists():
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def _save_db(data):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

def _load_log():
    if LOG_PATH.exists():
        with open(LOG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def _save_log(data):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def index(request):
    return render(request, 'index.html')

def get_db(request):
    db = _load_db()
    return JsonResponse(db, safe=False, json_dumps_params={'ensure_ascii': False})

@csrf_exempt
def update_db(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        data = json.loads(request.body)
        if not isinstance(data, list):
            return JsonResponse({'error': 'JSON 배열이 필요합니다'}, status=400)
        _save_db(data)
        return JsonResponse({'ok': True, 'message': f'{len(data)}개 대학 DB 업데이트 완료', 'count': len(data)})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON 파싱 실패'}, status=400)

@csrf_exempt
def merge_db(request):
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
        return JsonResponse({'ok': True, 'message': f'{added}개 추가, {updated}개 갱신', 'added': added, 'updated': updated, 'total': len(db)})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON 파싱 실패'}, status=400)

def export_db(request):
    db = _load_db()
    response = HttpResponse(json.dumps(db, ensure_ascii=False, indent=2), content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="hakjong_db.json"'
    return response

@csrf_exempt
def contribute(request):
    """학생 기여: 개별 전형 정보 추가/수정"""
    if request.method == 'GET':
        log = _load_log()
        return JsonResponse(log[-50:], safe=False, json_dumps_params={'ensure_ascii': False})
    
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        c = json.loads(request.body)
        univ_name = c.get('nm', '').strip()
        region = c.get('rg', '').strip()
        location = c.get('lc', '').strip()
        univ_type = c.get('tp', '').strip()
        pg_name = c.get('pg_name', '').strip()
        pg_quota = int(c.get('pg_quota', 0))
        pg_method = c.get('pg_method', '').strip()
        pg_interview = c.get('pg_interview', None)
        pg_min = c.get('pg_min', '').strip()
        contributor = c.get('contributor', '익명').strip()
        source_url = c.get('source_url', '').strip()
        
        # 학과별 데이터 (선택)
        dept_data = c.get('dept', [])
        # 합격자 성적 (선택)
        grades_data = c.get('grades', None)

        if not univ_name or not pg_name:
            return JsonResponse({'error': '대학명과 전형명은 필수입니다'}, status=400)

        db = _load_db()
        
        # 대학 찾기 또는 새로 만들기
        univ_idx = next((i for i, u in enumerate(db) if u.get('nm') == univ_name), -1)
        action = ''
        
        if univ_idx < 0:
            # 새 대학 추가
            new_univ = {
                'nm': univ_name,
                'rg': region or '기타',
                'lc': location or '',
                'tp': univ_type or '',
                'pg': []
            }
            db.append(new_univ)
            univ_idx = len(db) - 1
            action = 'new_univ'
        
        univ = db[univ_idx]
        
        # 전형 찾기 또는 새로 만들기
        pg_idx = next((i for i, p in enumerate(univ['pg']) if p.get('n') == pg_name), -1)
        
        new_pg = {'n': pg_name}
        if pg_quota > 0: new_pg['q'] = pg_quota
        if pg_method: new_pg['m'] = pg_method
        if pg_interview is not None:
            try: new_pg['iv'] = int(pg_interview)
            except: pass
        if pg_min: new_pg['mn'] = pg_min
        if dept_data: new_pg['dept'] = dept_data
        if grades_data: new_pg['grades'] = grades_data
        
        if pg_idx >= 0:
            # 기존 전형 업데이트 (비어있지 않은 필드만 덮어쓰기)
            existing = univ['pg'][pg_idx]
            for k, v in new_pg.items():
                if v: existing[k] = v
            action = action or 'updated'
        else:
            univ['pg'].append(new_pg)
            action = action or 'added'
        
        _save_db(db)
        
        # 기여 로그 기록
        log = _load_log()
        log.append({
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'contributor': contributor,
            'univ': univ_name,
            'pg': pg_name,
            'action': action,
            'source': source_url
        })
        _save_log(log)
        
        msg = {
            'new_univ': f'{univ_name} 대학 + {pg_name} 전형 새로 추가!',
            'added': f'{univ_name} - {pg_name} 전형 추가 완료!',
            'updated': f'{univ_name} - {pg_name} 전형 정보 업데이트!'
        }.get(action, '처리 완료')
        
        return JsonResponse({
            'ok': True,
            'message': msg,
            'action': action,
            'total_univs': len(db),
            'total_pgs': sum(len(u.get('pg',[])) for u in db)
        })
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({'error': f'데이터 형식 오류: {str(e)}'}, status=400)
