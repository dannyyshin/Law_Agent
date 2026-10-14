# 🏛️ Law Agent v3.0: 차세대 AI 법률 보조 시스템
**무결점 팩트체크(Zero-Hallucination)와 안정 구동(Zero-Crash)을 완성한 AI 법률 고문**

---

## 🌟 v3.0 핵심 업그레이드 사항

1. **🕵️‍♂️ Agentic ReAct 리서처 (Multi-turn Tool Calling)**:
   - 기존의 단 1회 검색 후 종료되던 구조적 한계를 완전히 극복.
   - **[1단계 검색 ➔ 2단계 판결/법령 전문 조회 ➔ 3단계 판례 생사 확인(cite_check)]**까지 최대 3턴 동안 AI가 자율적으로 연속 호출하여 판결 이유 전문을 완벽히 읽고 분석.
2. **📂 MultiFormatParser (다중 서면 무손실 파싱)**:
   - PDF(`PyMuPDF`)뿐만 아니라 실무에서 가장 많이 쓰이는 최신 한글 표준인 **HWPX(ZIP+XML)** 및 TXT를 100% 무손실로 파싱.
   - 구형 HWP 및 스캔본에 대한 안내 및 Fallback 지원.
3. **🛡️ 이중 팩트체크 가드레일 (Dual Guardrail)**:
   - 1차: 초안 내 법원/사건번호 정규식 전수 추출 후 원본 대조. 가짜 판례 발견 시 즉각 경고 및 삭제.
   - 2차: 법제처 최신 `verify_citations` 조문 실존 일괄 검증.
4. **🎨 엘박스(Lbox) 스타일 UI/UX 고도화**:
   - `[🟢 법제처 실시간 법령·판례 교차 검증 완료]` 공인 배지 표기.
   - 결론 3줄 요약 ➔ IRAC 심층 법리 분석 ➔ 실무 행동 가이드 체계.
5. **⚡ 하이브리드 스토리지 & 스레드 안전성**:
   - Dropbox 클라우드 실시간 동기화 우선 지원 및 로컬 `cases/` 자동 Fallback.
   - Streamlit Tornado 루프와 충돌하지 않는 `ThreadPoolExecutor` 전용 스레드 격리.

---

## 🚀 실행 방법

### 1. 원클릭 실행 (Windows)
* `Law_Agent_v3.0_실행.bat` 더블 클릭!

### 2. 수동 실행 (터미널)
```bash
cd Law_Agent_v3.0
pip install -r requirements.txt
streamlit run app.py
```

---

## ⚙️ 환경변수 설정 (`.env`)

```ini
GEMINI_API_KEY="구글_제미나이_API키"
LOGIN_PASSWORD="1234"
LAW_OC="법제처_오픈API_인증키"               # 또는 KOREAN_LAW_OPEN_API_KEY
DROPBOX_ACCESS_TOKEN="드롭박스_액세스토큰"   # 선택사항
DROPBOX_APP_KEY="드롭박스_앱키"             # OAuth2 Refresh Token 사용 시
DROPBOX_APP_SECRET="드롭박스_시크릿키"
DROPBOX_REFRESH_TOKEN="드롭박스_리프레시토큰"
```
