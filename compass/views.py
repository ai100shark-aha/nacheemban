import json
import os
import threading
from datetime import datetime
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from pathlib import Path

DB_PATH  = Path(__file__).resolve().parent.parent / 'static' / 'data' / 'univ_db.json'
LOG_PATH = Path(__file__).resolve().parent.parent / 'static' / 'data' / 'contrib_log.json'

SHEETS_KEY = os.environ.get('NACHEEMBAN_SHEET_KEY', '')
_sheets_cache = {'db': None, 'ts': 0}
CACHE_TTL = 60

def _get_sheet():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        if creds_json:
            creds = Credentials.from_service_account_info(json.loads(creds_json), scopes=scope)
        else:
            creds_path = Path(__file__).resolve().parent.parent / 'credentials.json'
            creds = Credentials.from_service_account_file(str(creds_path), scopes=scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEETS_KEY).sheet1
    except Exception as e:
        print(f"[Sheets] 연결 실패: {e}")
        return None

def _load_db_from_sheets():
    sheet = _get_sheet()
    if not sheet:
        return None
    try:
        val = sheet.acell('A1').value
        if val and val.strip().startswith('['):
            return json.loads(val)
    except Exception as e:
        print(f"[Sheets] 읽기 실패: {e}")
    return None

def _save_db_to_sheets(data):
    if not SHEETS_KEY:
        return
    def _do():
        sheet = _get_sheet()
        if not sheet:
            return
        try:
            db_json = json.dumps(data, ensure_ascii=False, separators=(',',':'))
            sheet.update('A1', [[db_json]])
            sheet.update('B1', [[datetime.now().strftime('%Y-%m-%d %H:%M:%S')]])
            sheet.update('C1', [[str(len(data))]])
            print(f"[Sheets] 저장 완료: {len(data)}개 대학")
        except Exception as e:
            print(f"[Sheets] 저장 실패: {e}")
    threading.Thread(target=_do, daemon=True).start()

def _load_db():
    import time
    now = time.time()
    if _sheets_cache['db'] is not None and now - _sheets_cache['ts'] < CACHE_TTL:
        return _sheets_cache['db']
    if SHEETS_KEY:
        db = _load_db_from_sheets()
        if db:
            _sheets_cache['db'] = db
            _sheets_cache['ts'] = now
            _save_db_local(db)
            return db
    if DB_PATH.exists():
        with open(DB_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def _save_db(data):
    _save_db_local(data)
    _save_db_to_sheets(data)
    import time
    _sheets_cache['db'] = data
    _sheets_cache['ts'] = time.time()

def _save_db_local(data):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',',':'))

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
        return JsonResponse({'ok':True,'message':f'{len(data)}개 대학 DB 업데이트 완료','count':len(data),'sheets':bool(SHEETS_KEY)})
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
            idx = next((i for i,u in enumerate(db) if u.get('nm')==new_u.get('nm')), -1)
            if idx >= 0:
                for new_pg in new_u.get('pg',[]):
                    pg_idx = next((j for j,p in enumerate(db[idx]['pg']) if p.get('n')==new_pg.get('n')), -1)
                    if pg_idx >= 0:
                        db[idx]['pg'][pg_idx].update({k:v for k,v in new_pg.items() if v})
                    else:
                        db[idx]['pg'].append(new_pg)
                updated += 1
            else:
                db.append(new_u)
                added += 1
        _save_db(db)
        return JsonResponse({'ok':True,'message':f'{added}개 추가, {updated}개 갱신','added':added,'updated':updated,'total':len(db),'sheets':bool(SHEETS_KEY)})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON 파싱 실패'}, status=400)

def export_db(request):
    db = _load_db()
    response = HttpResponse(json.dumps(db, ensure_ascii=False, indent=2), content_type='application/json; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="nacheemban_db.json"'
    return response

def sheets_status(request):
    status = {'sheets_key':bool(SHEETS_KEY),'google_credentials':bool(os.environ.get('GOOGLE_CREDENTIALS')),'cache_valid':_sheets_cache['db'] is not None}
    if SHEETS_KEY:
        try:
            sheet = _get_sheet()
            if sheet:
                status.update({'sheets_ok':True,'last_updated':sheet.acell('B1').value,'univ_count':sheet.acell('C1').value})
            else:
                status['sheets_ok'] = False
        except Exception as e:
            status.update({'sheets_ok':False,'error':str(e)})
    return JsonResponse(status)

@csrf_exempt
def contribute(request):
    if request.method == 'GET':
        return JsonResponse(_load_log()[-50:], safe=False, json_dumps_params={'ensure_ascii':False})
    if request.method != 'POST':
        return JsonResponse({'error':'POST only'}, status=405)
    try:
        c = json.loads(request.body)
        univ_name   = c.get('nm','').strip()
        region      = c.get('rg','').strip()
        location    = c.get('lc','').strip()
        univ_type   = c.get('tp','').strip()
        pg_name     = c.get('pg_name','').strip()
        pg_quota    = int(c.get('pg_quota',0))
        pg_method   = c.get('pg_method','').strip()
        pg_interview= c.get('pg_interview',None)
        pg_min      = c.get('pg_min','').strip()
        contributor = c.get('contributor','익명').strip()
        source_url  = c.get('source_url','').strip()

        dept_data = c.get('dept',[])
        pg_dept_text = c.get('pg_dept','').strip()
        if pg_dept_text and not dept_data:
            import re
            for part in pg_dept_text.split('/'):
                part = part.strip()
                if not part: continue
                m = re.match(r'(.+?)\s*(\d+)\s*명?$', part)
                if m: dept_data.append({'d':m.group(1).strip(),'q':int(m.group(2))})
                else: dept_data.append({'d':part})

        grades_data = c.get('grades',None)
        if not univ_name or not pg_name:
            return JsonResponse({'error':'대학명과 전형명은 필수입니다'}, status=400)

        db = _load_db()
        univ_idx = next((i for i,u in enumerate(db) if u.get('nm')==univ_name), -1)
        action = ''
        if univ_idx < 0:
            db.append({'nm':univ_name,'rg':region or '기타','lc':location or '','tp':univ_type or '','pg':[]})
            univ_idx = len(db)-1
            action = 'new_univ'

        univ = db[univ_idx]
        pg_idx = next((i for i,p in enumerate(univ['pg']) if p.get('n')==pg_name), -1)
        new_pg = {'n':pg_name}
        if pg_quota > 0:  new_pg['q'] = pg_quota
        if pg_method:     new_pg['m'] = pg_method
        if pg_interview is not None:
            try: new_pg['iv'] = int(pg_interview)
            except: pass
        if pg_min:        new_pg['mn'] = pg_min
        if dept_data:     new_pg['dept'] = dept_data
        if grades_data:   new_pg['grades'] = grades_data

        if pg_idx >= 0:
            existing = univ['pg'][pg_idx]
            for k,v in new_pg.items():
                if v: existing[k] = v
            action = action or 'updated'
        else:
            univ['pg'].append(new_pg)
            action = action or 'added'

        _save_db(db)
        log = _load_log()
        log.append({'date':datetime.now().strftime('%Y-%m-%d %H:%M'),'contributor':contributor,'univ':univ_name,'pg':pg_name,'action':action,'source':source_url})
        _save_log(log)

        msg = {'new_univ':f'{univ_name} + {pg_name} 새로 추가!','added':f'{univ_name} - {pg_name} 추가!','updated':f'{univ_name} - {pg_name} 업데이트!'}.get(action,'처리 완료')
        return JsonResponse({'ok':True,'message':msg,'action':action,'total_univs':len(db),'total_pgs':sum(len(u.get('pg',[])) for u in db),'sheets':bool(SHEETS_KEY)})
    except (json.JSONDecodeError, ValueError) as e:
        return JsonResponse({'error':f'데이터 형식 오류: {str(e)}'}, status=400)
