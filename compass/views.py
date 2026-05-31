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

# Sheets 컬럼 구조
GRADE_KEYS = ['인문','자연','의예','치의예','한의예','수의예','약학','간호','물리치료','방사선','임상병리','작업치료','치위생']
SHEET_HEADERS = ['nm','rg','lc','tp','pg_name','pg_q','pg_method','pg_iv','pg_mn','pg_cr']               + [f'gr_{k}' for k in GRADE_KEYS] + ['dept_json','updated_at']

def _db_to_rows(db):
    """DB 리스트 → Sheets 행 리스트 변환"""
    rows = [SHEET_HEADERS]
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    for u in db:
        for pg in u.get('pg', []):
            grades = pg.get('grades', {})
            depts  = pg.get('dept', [])
            row = [
                u.get('nm',''), u.get('rg',''), u.get('lc',''), u.get('tp',''),
                pg.get('n',''), str(pg.get('q','')), pg.get('m',''),
                str(pg.get('iv','')), pg.get('mn',''), str(pg.get('cr','')),
            ]
            for k in GRADE_KEYS:
                g = grades.get(k, {})
                if g:
                    val = str(g.get('avg',''))
                    if g.get('fill'): val += f" ({g['fill']}명)"
                else:
                    val = ''
                row.append(val)
            row.append(json.dumps(depts, ensure_ascii=False) if depts else '')
            row.append(now)
            rows.append(row)
    return rows

def _rows_to_db(rows):
    """Sheets 행 리스트 → DB 리스트 복원"""
    import re as _re
    if not rows or len(rows) < 2: return []
    headers = rows[0]
    db_map = {}
    for row in rows[1:]:
        if not row or not row[0]: continue
        while len(row) < len(headers): row.append('')
        d = dict(zip(headers, row))
        nm = d.get('nm','').strip()
        if not nm: continue
        if nm not in db_map:
            db_map[nm] = {'nm':nm,'rg':d.get('rg',''),'lc':d.get('lc',''),'tp':d.get('tp',''),'pg':[]}
        pg = {}
        if d.get('pg_name'): pg['n'] = d['pg_name']
        if d.get('pg_q'):
            try: pg['q'] = int(d['pg_q'])
            except: pg['q'] = d['pg_q']
        if d.get('pg_method'): pg['m'] = d['pg_method']
        if d.get('pg_iv'):
            try: pg['iv'] = int(d['pg_iv'])
            except: pass
        if d.get('pg_mn'): pg['mn'] = d['pg_mn']
        if d.get('pg_cr'):
            try: pg['cr'] = float(d['pg_cr'])
            except: pg['cr'] = d['pg_cr']
        grades = {}
        for k in GRADE_KEYS:
            val = d.get(f'gr_{k}','').strip()
            if val:
                m = _re.match(r'([\d.]+)\s*(?:\((\d+)명\))?', val)
                if m:
                    gd = {'avg': float(m.group(1))}
                    if m.group(2): gd['fill'] = int(m.group(2))
                    grades[k] = gd
        if grades: pg['grades'] = grades
        dept_json = d.get('dept_json','').strip()
        if dept_json:
            try: pg['dept'] = json.loads(dept_json)
            except: pass
        if pg.get('n'):
            db_map[nm]['pg'].append(pg)
    return list(db_map.values())

def _load_db_from_sheets():
    """Sheets에서 행 단위로 DB 읽기"""
    sheet = _get_sheet()
    if not sheet:
        return None
    try:
        all_rows = sheet.get_all_values()
        if not all_rows or len(all_rows) < 2:
            return None
        # 헤더가 새 구조인지 확인
        if all_rows[0] and all_rows[0][0] == 'nm':
            db = _rows_to_db(all_rows)
            if db:
                print(f"[Sheets] 읽기 완료: {len(db)}개 대학")
                return db
    except Exception as e:
        print(f"[Sheets] 읽기 실패: {e}")
    return None

def _save_db_to_sheets(data):
    """DB → Sheets 행 단위 저장 (필드별 컬럼, 직접 수정 가능)"""
    if not SHEETS_KEY:
        return
    sheet = _get_sheet()
    if not sheet:
        return
    try:
        rows = _db_to_rows(data)
        # 기존 데이터 전체 지우고 새로 쓰기
        sheet.clear()
        sheet.update('A1', rows)
        # 헤더 굵게 (선택)
        try:
            sheet.format('A1:Y1', {'textFormat': {'bold': True}})
        except: pass
        print(f"[Sheets] 저장 완료: {len(data)}개 대학, {len(rows)-1}개 전형")
    except Exception as e:
        print(f"[Sheets] 저장 실패: {e}")
        import traceback
        traceback.print_exc()

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

def career(request):
    return render(request, 'career.html')

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
                # 새 구조: 1행=헤더, 2행부터 데이터 → 마지막 행의 updated_at 확인
                all_vals = sheet.get_all_values()
                row_count = len(all_vals) - 1  # 헤더 제외
                # updated_at은 Y열(인덱스 24)
                last_updated = ''
                univ_names = set()
                for row in all_vals[1:]:
                    if row and len(row) > 24 and row[24]: last_updated = row[24]
                    if row and row[0]: univ_names.add(row[0])
                status.update({
                    'sheets_ok': True,
                    'last_updated': last_updated or '(저장된 데이터 없음)',
                    'univ_count': str(len(univ_names)),
                    'pg_count': str(row_count),
                    'structure': '행단위 (필드별 컬럼)'
                })
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


# ───────────────────────────────────────────────
# 학급 현황 (담임 교사용)
# Google Sheets Sheet2 에 저장
# ───────────────────────────────────────────────

def _get_consult_sheet():
    """학생 상담 기록용 Sheet2 반환"""
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
        spreadsheet = client.open_by_key(SHEETS_KEY)
        # Sheet2 없으면 생성
        try:
            sheet = spreadsheet.worksheet('students')
        except:
            sheet = spreadsheet.add_worksheet(title='students', rows=1000, cols=15)
            sheet.append_row(['sid','name','grade_yr','class_no','stu_no',
                              'inner_grade','major','target','top_univs','univ_count','saved_at'])
        return sheet
    except Exception as e:
        print(f"[Consult Sheet] 연결 실패: {e}")
        return None

@csrf_exempt
def save_consult(request):
    """학생 상담 기록 저장"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST only'}, status=405)
    try:
        data = json.loads(request.body)
        sid = str(data.get('sid', '')).strip()
        if not sid:
            return JsonResponse({'error': '학번이 필요합니다'}, status=400)

        if not SHEETS_KEY:
            return JsonResponse({'error': 'Sheets 미설정'}, status=503)

        sheet = _get_consult_sheet()
        if not sheet:
            return JsonResponse({'error': 'Sheets 연결 실패'}, status=503)

        # 기존 기록 찾아서 업데이트 (없으면 추가)
        try:
            cell = sheet.find(sid)
            row_idx = cell.row
            sheet.update(f'A{row_idx}:K{row_idx}', [[
                sid,
                data.get('name',''),
                data.get('grade_yr',''),
                data.get('class_no',''),
                data.get('stu_no',''),
                data.get('inner_grade',''),
                data.get('major',''),
                data.get('target',''),
                data.get('top_univs','[]'),
                str(data.get('univ_count',0)),
                data.get('saved_at','')
            ]])
        except:
            # 새 행 추가
            sheet.append_row([
                sid,
                data.get('name',''),
                data.get('grade_yr',''),
                data.get('class_no',''),
                data.get('stu_no',''),
                data.get('inner_grade',''),
                data.get('major',''),
                data.get('target',''),
                data.get('top_univs','[]'),
                str(data.get('univ_count',0)),
                data.get('saved_at','')
            ])

        return JsonResponse({'ok': True, 'message': '상담 기록 저장 완료'})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def get_class_students(request):
    """담임 교사 - 반별 학생 조회"""
    class_no = request.GET.get('class_no', '')
    pw       = request.GET.get('pw', '')

    if not class_no:
        return JsonResponse({'error': '반을 선택하세요'}, status=400)

    # 비밀번호 검증
    correct_pw = os.environ.get('CLASS_PASSWORD', 'teacher1234')
    if pw != correct_pw:
        return JsonResponse({'error': '비밀번호가 틀렸습니다'}, status=401)

    if not SHEETS_KEY:
        return JsonResponse({'error': 'Sheets 미설정'}, status=503)

    sheet = _get_consult_sheet()
    if not sheet:
        return JsonResponse({'error': 'Sheets 연결 실패'}, status=503)

    try:
        all_rows = sheet.get_all_records()
        students = [r for r in all_rows if str(r.get('class_no','')) == str(class_no)]
        return JsonResponse({'ok': True, 'students': students, 'total': len(students)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
