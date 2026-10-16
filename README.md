# ⚖️ Law Agent v4.0 (AI 법률 에이전트 워크스페이스)

> **Google Gemini 3.8 Flash 엔진 탑재 | 대한민국 법제처 실시간 ReAct 리서처 | 실무 서면 드래프터(.docx) | 사건 연대기 타임라인**

---

## 🌟 v4.0 주요 신규 기능 및 혁신

### 1. ⚡ Google Gemini 3.8 Flash 코어 모델 탑재
- 고속·고성능 텍스트 추론 모델 `gemini-3.8-flash`를 탑재하여 법리 분석 및 판례 요건사실 적합성 검토 능력을 극대화했습니다.

### 2. 📝 실무 법률 서면·진정·구제신청 드래프터 (`drafter.py`)
- 실제 법원 및 노동위원회/노동청에 즉시 제출 가능한 표준 공문서 규격의 서면을 자동 생성합니다:
  1. **민사 소장**: 손해배상(기), 부당이득반환, 대여금 등
  2. **민사 준비서면**: 상대방 주장 반박 및 추가 증거 입증
  3. **고용노동부 진정서**: 직장 내 괴롭힘, 임금체불 등 노동청 진정
  4. **지방노동위원회 부당해고 등 구제신청서**: 원직복직 및 임금상당액 주문 신청
  5. **민사 채권가압류신청서**: 통장 예금채권 및 보증금 보전처분
- **📥 Word(.docx) 다운로드 지원**: 마크다운 서면을 한국 법원 소송서면 표준 규격(A4 여백 25mm, 맑은 고딕, 단락 간격, 청구취지 서식)의 `.docx` 파일로 즉시 변환하여 다운로드 제공.

### 3. 📅 사건 사실관계 연대기 (Chronological Timeline, `timeline.py`)
- 사건 기록 및 상담 대화 내역에서 날짜, 행위 주체, 핵심 행위, 증거, 법적 쟁점을 자동 추출(JSON 구조화).
- **Generative UI 인터랙티브 수직 타임라인**으로 사건의 흐름을 한눈에 파악.
- 핵심 위법/처분(🚨), 갈등/주의(⚠️), 일반 경위(ℹ️) 중요도별 시각적 뱃지 및 증거 매핑.
- 수동 사건 추가/수정 지원 및 사건방별 `timeline.json` 영속 저장.

### 4. 📂 사건 증거 매핑 & 입증계획서 (Evidence Matrix)
- 확보된 증거 서류 목록(갑 제N호증) 정리.
- AI가 요건사실 대비 증명력을 분석하여 상대방 예상 항변 및 **추가 확보 필요 증거(녹취록, 진단서, 사실조회 대상 등)**를 맞춤형 입증계획서로 제시.

### 5. 🌐 대한민국 법제처 Open API ReAct 리서처 & 3중 가드레일 (계승)
- `search_decisions`, `get_decision_text`, `cite_check`, `search_law`, `get_law_text`
- 가짜 사건번호 검출 및 날조 판례 100% 필터링.

---

## 📂 프로젝트 구조

```text
Law_Agent_v4.0/
├── app.py                     # Streamlit 4-Tab 워크스페이스 메인 앱
├── drafter.py                 # 실무 서면 표준 템플릿 및 Word(.docx) 생성 엔진
├── timeline.py                # 사실관계 AI 연대기 추출 및 인터랙티브 UI 렌더러
├── parser.py                  # PDF / HWPX(한글 표준) / TXT 통합 무손실 파서
├── mcp_client.py              # 법제처 MCP Stdio 비동기 클라이언트
├── requirements.txt           # 필수 패키지 목록 (python-docx 포함)
├── packages.txt               # Streamlit Cloud 리눅스 의존성
├── .env                       # API 키 및 인증 설정
├── .gitignore                 # 보안 및 임시 파일 제외 목록
├── cases/                     # 사건방별 서류 및 데이터 저장소
└── Law_Agent_v4.0_실행.bat     # 원클릭 실행 배치 파일
```

---

## 🚀 빠른 시작

### 1. 환경 설정 (.env)
```env
GEMINI_API_KEY="your-gemini-api-key"
LOGIN_PASSWORD="your-password"
LAW_OC="your-law-go-kr-oc-id" # 선택사항 (법제처 Open API OC)
```

### 2. 실행
- **Windows**: `Law_Agent_v4.0_실행.bat` 더블 클릭
- **터미널**:
  ```bash
  pip install -r requirements.txt
  streamlit run app.py
  ```
