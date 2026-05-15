# 입시 나침반 v4.0 — 웹 서비스 버전

## 프로젝트 구조
```
nacheemban/
├── manage.py                 # Django 관리 스크립트
├── requirements.txt          # Python 패키지
├── Procfile                  # Render.com 실행 설정
├── build.sh                  # Render.com 빌드 스크립트
├── nacheemban/               # Django 프로젝트 설정
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── compass/                  # 메인 앱
│   ├── views.py              # API 엔드포인트
│   └── urls.py
├── templates/
│   └── index.html            # 메인 페이지
└── static/
    └── data/
        └── univ_db.json      # 학종 DB (100개 대학)
```

## 로컬 실행 (Windows)
```powershell
cd E:\download\nacheemban
pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py runserver
# 브라우저에서 http://127.0.0.1:8000 접속
```

## GitHub + Render.com 배포

### 1. GitHub 저장소 생성
```powershell
cd E:\download\nacheemban
git init
git add .
git commit -m "입시 나침반 v4.0 웹 서비스"
git branch -M main
git remote add origin https://github.com/ai100shark-aha/nacheemban.git
git push -u origin main
```

### 2. Render.com 설정
1. https://render.com → New Web Service
2. GitHub 연결 → nacheemban 저장소 선택
3. 설정:
   - **Name**: nacheemban
   - **Runtime**: Python
   - **Build Command**: `bash build.sh`
   - **Start Command**: `gunicorn nacheemban.wsgi:application --bind 0.0.0.0:$PORT`
4. Environment Variables:
   - `DJANGO_SECRET_KEY` = (랜덤 문자열 생성)
   - `DEBUG` = False

## API 엔드포인트
- `GET /` — 메인 페이지
- `GET /api/db/` — DB JSON 반환
- `POST /api/db/update/` — DB 전체 교체
- `POST /api/db/merge/` — DB 병합 (추가/갱신)
- `GET /api/db/export/` — DB JSON 다운로드

## DB 업데이트 방법
1. 웹 앱의 "DB 관리" 탭에서 JSON 파일 업로드
2. 또는 API 직접 호출:
   ```bash
   curl -X POST https://nacheemban.onrender.com/api/db/merge/ \
     -H "Content-Type: application/json" \
     -d @new_data.json
   ```
