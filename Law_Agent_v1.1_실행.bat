@echo off
chcp 65001 > nul
echo ==========================================
echo 🚀 Law Agent v1.1 (최종 버전) 서버를 시작합니다...
echo ==========================================
echo 안티그래비티 UI와 최적화된 검색 파이프라인이 적용된 최종본입니다.
echo 잠시만 기다려주세요...

cd /d "%~dp0"
start http://localhost:8501
streamlit run app.py --server.port 8501

pause
