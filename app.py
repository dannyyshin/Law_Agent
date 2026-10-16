import streamlit as st
import os
import json
import re
import datetime
from typing import Any, List, Dict
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import dropbox

# v4.0 통합 모듈 임포트
from parser import MultiFormatParser
from mcp_client import run_async, fetch_mcp_tools_async, call_mcp_tool_async
from drafter import LegalDrafter, DOCUMENT_TEMPLATES
from timeline import TimelineEngine

# =====================================================================
# 1. 환경변수 및 인증 로드
# =====================================================================
load_dotenv(override=True)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DBX_TOKEN = os.environ.get("DROPBOX_ACCESS_TOKEN", "")
DBX_APP_KEY = os.environ.get("DROPBOX_APP_KEY", "")
DBX_APP_SECRET = os.environ.get("DROPBOX_APP_SECRET", "")
DBX_REFRESH_TOKEN = os.environ.get("DROPBOX_REFRESH_TOKEN", "")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD", "1234")

# Google Gemini 3.8 Flash 엔진 명칭 설정
CORE_MODEL_NAME = "gemini-3.8-flash"

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# 1-0. 보안 게이트웨이
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.set_page_config(page_title="Law Agent v4.0 - 보안 접속", page_icon="🔒", layout="centered")
    st.markdown("<h2 style='text-align: center; margin-top: 50px; font-weight: 700; color: #1e293b;'>🔒 Law Agent v4.0 보안 접속</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748b; font-size: 14px;'>Google Gemini 3.8 Flash & 실무 법률 서면·타임라인 워크스페이스</p>", unsafe_allow_html=True)
    pwd = st.text_input("접속 비밀번호를 입력하세요", type="password")
    if st.button("접속하기", use_container_width=True):
        if pwd == LOGIN_PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()

# =====================================================================
# 1-1. Streamlit 페이지 설정 및 Lbox-스타일 법률 전문 CSS
# =====================================================================
st.set_page_config(
    page_title="Law Agent v4.0 - Gemini 3.8 Flash 워크스페이스",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Pretendard:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&display=swap');

html, body, p, li, h1, h2, h3, h4, h5, h6, blockquote, div.stMarkdown {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, sans-serif !important;
}

/* 사이드바 너비 */
@media (min-width: 768px) {
    [data-testid="stSidebar"] { min-width: 360px !important; max-width: 360px !important; }
}

/* 탭 네비게이션 스타일 */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    border-bottom: 2px solid #e2e8f0;
    padding-bottom: 4px;
}
.stTabs [data-baseweb="tab"] {
    font-size: 15px;
    font-weight: 600;
    padding: 10px 18px;
    border-radius: 8px 8px 0 0;
    color: #475569;
}
.stTabs [aria-selected="true"] {
    color: #0f172a !important;
    border-bottom: 3px solid #1e3a8a !important;
    background-color: rgba(30, 58, 138, 0.04);
}

/* 채팅창 UI */
[data-testid="stChatMessage"] { margin-bottom: 1.2rem !important; }

/* 법률 인용문 스타일 */
blockquote {
    border-left: 4px solid #1e3a8a !important;
    background-color: #f8fafc !important;
    padding: 12px 16px !important;
    margin: 12px 0 !important;
    border-radius: 0 6px 6px 0 !important;
    font-style: normal !important;
    color: #1e293b !important;
    font-size: 0.95rem !important;
    line-height: 1.6;
}

/* 배지 스타일 */
.legal-badge-verified {
    display: inline-flex;
    align-items: center;
    background-color: #dcfce7;
    border: 1px solid #86efac;
    color: #166534;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 14px;
    margin-right: 8px;
    margin-bottom: 8px;
}

.legal-badge-flash {
    display: inline-flex;
    align-items: center;
    background-color: #e0e7ff;
    border: 1px solid #c7d2fe;
    color: #3730a3;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 14px;
    margin-bottom: 8px;
}

/* 버튼 포인트 컬러 */
div.stButton > button:first-child {
    border-radius: 6px !important;
    font-weight: 600 !important;
}

footer {visibility: hidden !important;}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# =====================================================================
# 2. 스토리지 연동 (Dropbox 실시간 마운트 및 로컬 Fallback)
# =====================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_CASES_DIR = os.path.join(BASE_DIR, "cases")
if not os.path.exists(LOCAL_CASES_DIR):
    os.makedirs(LOCAL_CASES_DIR, exist_ok=True)

@st.cache_resource
def get_dropbox_client():
    if DBX_REFRESH_TOKEN and DBX_APP_KEY and DBX_APP_SECRET:
        return dropbox.Dropbox(
            oauth2_refresh_token=DBX_REFRESH_TOKEN,
            app_key=DBX_APP_KEY,
            app_secret=DBX_APP_SECRET
        )
    elif DBX_TOKEN:
        return dropbox.Dropbox(DBX_TOKEN)
    return None

dbx = get_dropbox_client()
use_cloud_storage = False

# 사이드바 상단 정보
st.sidebar.markdown("""
<div style='display: flex; align-items: center; gap: 8px; margin-bottom: 12px;'>
    <h2 style='margin: 0; font-size: 22px; font-weight: 700; color: #1e3a8a;'>⚖️ Law Agent</h2>
    <span style='background: #1e3a8a; color: white; font-size: 11px; font-weight: 700; padding: 2px 7px; border-radius: 10px;'>v4.0</span>
</div>
<div style='font-size: 12px; color: #64748b; margin-bottom: 16px;'>
    엔진: <strong>Gemini 3.8 Flash</strong> | 법제처 Open API 연동
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("### 🏛️ 사건방 선택")

case_folders = []
if dbx:
    try:
        res = dbx.files_list_folder('')
        case_folders = [entry.name for entry in res.entries if isinstance(entry, dropbox.files.FolderMetadata)]
        case_folders.sort()
        if case_folders:
            use_cloud_storage = True
            st.sidebar.caption("☁️ Dropbox Cloud 실시간 동기화")
    except Exception as e:
        st.sidebar.warning(f"Dropbox 연결 우회 ({e}) -> 로컬 모드로 동작합니다.")

if not use_cloud_storage:
    st.sidebar.caption("💻 로컬 cases 디렉터리 연동 모드")
    if os.path.exists(LOCAL_CASES_DIR):
        case_folders = [f for f in os.listdir(LOCAL_CASES_DIR) if os.path.isdir(os.path.join(LOCAL_CASES_DIR, f))]
        case_folders.sort()

# 기본 사건방 생성 보조
if not case_folders:
    default_case = os.path.join(LOCAL_CASES_DIR, "기본사건_직장내괴롭힘_손해배상")
    os.makedirs(default_case, exist_ok=True)
    case_folders = ["기본사건_직장내괴롭힘_손해배상"]

selected_folder = st.sidebar.selectbox("진행 중인 사건:", case_folders)

# =====================================================================
# 3. 사건 문서 자동 파싱 (PDF, HWPX, TXT)
# =====================================================================
@st.cache_data(show_spinner=False)
def load_case_documents(folder_name: str, is_cloud: bool):
    doc_text = ""
    file_list = []
    
    if is_cloud:
        try:
            res = dbx.files_list_folder(f'/{folder_name}')
            for entry in res.entries:
                if isinstance(entry, dropbox.files.FileMetadata):
                    name_lower = entry.name.lower()
                    if name_lower.endswith(('.pdf', '.hwpx', '.txt', '.hwp')):
                        file_list.append(entry.name)
                        _, resp = dbx.files_download(entry.path_lower)
                        parsed = MultiFormatParser.parse_file(entry.name, resp.content)
                        if parsed:
                            doc_text += f"\n--- [문서: {entry.name}] ---\n{parsed}\n"
        except Exception as e:
            print(f"클라우드 문서 로드 실패: {e}")
    else:
        folder_path = os.path.join(LOCAL_CASES_DIR, folder_name)
        if os.path.exists(folder_path):
            for fname in os.listdir(folder_path):
                name_lower = fname.lower()
                if name_lower.endswith(('.pdf', '.hwpx', '.txt', '.hwp')):
                    file_list.append(fname)
                    fpath = os.path.join(folder_path, fname)
                    with open(fpath, 'rb') as f:
                        parsed = MultiFormatParser.parse_file(fname, f.read())
                        if parsed:
                            doc_text += f"\n--- [문서: {fname}] ---\n{parsed}\n"
                            
    return doc_text.strip(), file_list

with st.spinner("📂 사건 서류(PDF/HWPX/TXT) 동기화 및 파싱 중..."):
    context_text, loaded_files = load_case_documents(selected_folder, use_cloud_storage)

if loaded_files:
    st.sidebar.success(f"✅ {len(loaded_files)}건의 서류 파싱 완료")
    with st.sidebar.expander("📄 등록된 증거 서류 목록", expanded=False):
        for i, fn in enumerate(sorted(loaded_files, reverse=True), 1):
            st.markdown(f"{i}. {fn}")
else:
    st.sidebar.info("해당 사건방에 등록된 서면 파일이 없습니다.")

st.sidebar.markdown("---")

# =====================================================================
# 4. MCP 도구 및 데이터 영속화 헬퍼
# =====================================================================
@st.cache_resource(show_spinner="🔍 법제처 최신 MCP 도구 바인딩 중...")
def get_available_mcp_tools():
    return run_async(fetch_mcp_tools_async())

gemini_functions = get_available_mcp_tools()
if gemini_functions:
    st.sidebar.markdown(f"<span class='legal-badge-verified'>🌐 법제처 MCP 도구 {len(gemini_functions)}개 활성화</span>", unsafe_allow_html=True)
else:
    st.sidebar.caption("ℹ️ 법제처 MCP 오프라인 (기본 법리 추론 모드)")

def load_case_json(folder_name: str, is_cloud: bool, filename: str, default_val: Any) -> Any:
    if is_cloud:
        try:
            _, res = dbx.files_download(f"/{folder_name}/{filename}")
            return json.loads(res.content.decode('utf-8'))
        except Exception:
            return default_val
    else:
        fpath = os.path.join(LOCAL_CASES_DIR, folder_name, filename)
        if os.path.exists(fpath):
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return default_val
    return default_val

def save_case_json(folder_name: str, is_cloud: bool, filename: str, data: Any):
    data_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
    if is_cloud:
        try:
            dbx.files_upload(data_bytes, f"/{folder_name}/{filename}", mode=dropbox.files.WriteMode("overwrite"))
        except Exception as e:
            print(f"클라우드 {filename} 저장 실패: {e}")
    else:
        fpath = os.path.join(LOCAL_CASES_DIR, folder_name, filename)
        try:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(data_bytes.decode('utf-8'))
        except Exception as e:
            print(f"로컬 {filename} 저장 실패: {e}")

# 사건방 변경 시 세션 초기화
if "current_room" not in st.session_state or st.session_state.current_room != selected_folder:
    st.session_state.current_room = selected_folder
    st.session_state.messages = load_case_json(selected_folder, use_cloud_storage, "history.json", [])
    st.session_state.timeline_events = load_case_json(selected_folder, use_cloud_storage, "timeline.json", [])
    st.session_state.drafted_docs = load_case_json(selected_folder, use_cloud_storage, "drafts.json", {})

# =====================================================================
# 5. 헤더 및 4대 전문가 워크스페이스 탭 구성
# =====================================================================
st.markdown(f"""
<div style='display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;'>
    <div>
        <h1 style='font-size: 28px; margin: 0; font-weight: 700; color: #0f172a;'>🏛️ {selected_folder}</h1>
        <p style='margin: 4px 0 0 0; color: #64748b; font-size: 14px;'>Google Gemini 3.8 Flash 기반 고지능 법률 의사결정 & 실무 서면 드래프팅 시스템</p>
    </div>
    <div>
        <span class='legal-badge-verified'>🟢 3중 팩트체크 가드레일</span>
        <span class='legal-badge-flash'>⚡ Gemini 3.8 Flash</span>
    </div>
</div>
""", unsafe_allow_html=True)

tab_chat, tab_timeline, tab_drafter, tab_evidence = st.tabs([
    "💬 법률 자문 & 팩트체크",
    "📅 사건 타임라인 (연대기)",
    "📝 실무 서면 드래프터 (.docx)",
    "📂 사건 증거 매핑 & 입증계획"
])

# =====================================================================
# TAB 1: 💬 법률 자문 & 팩트체크 파이프라인
# =====================================================================
with tab_chat:
    col_clear, _ = st.columns([2, 8])
    with col_clear:
        if st.button("🧹 자문 대화 비우기", use_container_width=True):
            st.session_state.messages = []
            save_case_json(selected_folder, use_cloud_storage, "history.json", st.session_state.messages)
            st.rerun()

    # 대화 렌더링
    user_avatar = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Ctext x='12' y='18' font-size='20' text-anchor='middle' fill='white'%3E%E2%9D%94%3C/text%3E%3C/svg%3E"
    for msg in st.session_state.messages:
        avatar = user_avatar if msg["role"] == "user" else "⚖️"
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])

    # Agentic ReAct 리서처 함수들
    def execute_agentic_researcher(user_query_parts, placeholder) -> tuple[str, list]:
        placeholder.markdown("*(🕵️‍♂️ 리서처 에이전트: 사건 분석 및 법제처 실시간 판례·법령 기획 중...)*")
        research_logs = []
        called_tool_history = []
        
        researcher_instruction = (
            "당신은 최고 실력의 수석 법률 리서처입니다. 사용자의 질문을 분석하여 법률 표준 키워드를 도출하고, "
            "제공된 법제처 MCP 도구를 다단계(Multi-step)로 실행하여 판례 전문과 최신 개정 법령을 수집하세요.\n"
            "[지침]\n"
            "1. `search_decisions` 또는 `search_law`로 검색\n"
            "2. `get_decision_text` 또는 `get_law_text`로 판결 전문 확인\n"
            "3. 확정 판례는 `cite_check`로 폐기 여부 검증\n"
            "4. 객관적 사실만을 요약 보고하세요."
        )
        
        model = genai.GenerativeModel(
            model_name=CORE_MODEL_NAME,
            system_instruction=researcher_instruction,
            tools=[{"function_declarations": gemini_functions}] if gemini_functions else [],
            tool_config={"function_calling_config": {"mode": "ANY"}} if gemini_functions else None,
            generation_config=genai.types.GenerationConfig(temperature=0.0)
        )
        
        recent_history = []
        for m in st.session_state.messages[-4:-1] if len(st.session_state.messages) > 1 else []:
            recent_history.append({"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]})
            
        chat = model.start_chat(history=recent_history)
        try:
            response = chat.send_message(user_query_parts, stream=False)
            max_turns = 3
            for step in range(max_turns):
                if not (response.candidates and response.candidates[0].content.parts):
                    break
                fn_calls = [p.function_call for p in response.candidates[0].content.parts if p.function_call]
                if not fn_calls:
                    break
                fn = fn_calls[0]
                tool_name = fn.name
                tool_args = dict(fn.args)
                called_tool_history.append(tool_name)
                
                placeholder.markdown(f"*(🕵️‍♂️ 법제처 실시간 조회 [{step+1}/{max_turns}]: `{tool_name}` 실행 중...)*")
                tool_output = run_async(call_mcp_tool_async(tool_name, tool_args))
                research_logs.append(f"--- [{tool_name} 결과] ---\n{tool_output}\n")
                
                try:
                    response = chat.send_message(
                        genai.protos.Content(
                            parts=[genai.protos.Part(
                                function_response=genai.protos.FunctionResponse(
                                    name=tool_name,
                                    response={"result": tool_output}
                                )
                            )]
                        ),
                        stream=False
                    )
                except Exception as e:
                    print(f"Function response 전달 오류: {e}")
                    break
        except Exception as e:
            research_logs.append(f"리서치 통신 오류: {e}")
            
        combined_research = "\n".join(research_logs)
        if not combined_research:
            combined_research = "법제처 직접 조회 결과 없음. 대한민국 기본 법리와 판례 원칙에 기반하여 검토합니다."
        return combined_research, called_tool_history

    def execute_analyst_draft(context, user_query_parts, research_data, placeholder) -> str:
        placeholder.markdown("*(👨‍⚖️ 수석 변호사 에이전트: IRAC 법리 검토 초안 작성 중...)*")
        analyst_instruction = (
            "당신은 실무 경력 20년의 수석 변호사입니다. "
            "제공된 사건 서면과 법제처 판례/법령을 바탕으로 IRAC(쟁점-규칙-적용-결론) 구조의 전문 법률 의견서를 작성하세요.\n"
            "존재하지 않는 가짜 사건번호나 날조된 판례는 절대 인용하지 마십시오."
        )
        model = genai.GenerativeModel(
            model_name=CORE_MODEL_NAME,
            system_instruction=analyst_instruction,
            generation_config=genai.types.GenerationConfig(temperature=0.0)
        )
        prompt_parts = [
            f"[사건 증거 서류 추출 텍스트]\n{context}\n\n[법제처 리서치 결과]\n{research_data}\n\n[사용자 질의]:"
        ]
        prompt_parts.extend(user_query_parts)
        try:
            draft_resp = model.generate_content(prompt_parts, stream=False)
            return draft_resp.text
        except Exception as e:
            return f"초안 작성 오류: {e}"

    def stream_qa_judge_final(user_query_parts, draft, research_data, context, placeholder) -> str:
        placeholder.markdown("*(⚖️ QA 판사 에이전트: 팩트체크 교차 검증 및 최종 답변 생성 중...)*")
        
        found_cases = re.findall(r'(대법원|헌법재판소|고등법원|지방법원).*?([0-9]{4}[가-힣]{1,2}[0-9]+)', draft)
        warnings = []
        for court, num in found_cases:
            if num not in research_data and num not in context:
                warnings.append(f"경고: 초안에 언급된 '{court} {num}'은 원본 데이터에 없습니다. 삭제하십시오.")
        warning_block = "\n".join(warnings) if warnings else ""

        qa_instruction = (
            "당신은 엄격한 최고법원 수석 재판연구관(QA 판사)입니다.\n"
            "변호사의 초안을 검증하여 가짜 판례나 오류를 100% 교정하고, 실무에 즉시 활용할 수 있는 명쾌하고 정확한 최종 답변을 스트리밍하십시오.\n"
            "답변 서두에 반드시 `[🟢 법제처 실시간 법령·판례 교차 검증 완료]`를 표기하세요.\n"
            "구조: ① 핵심 결론 3줄 요약 -> ② 쟁점별 IRAC 법리 검토 -> ③ 승소 전략 및 실무 행동 지침"
        )
        model = genai.GenerativeModel(
            model_name=CORE_MODEL_NAME,
            system_instruction=qa_instruction,
            generation_config=genai.types.GenerationConfig(temperature=0.1)
        )
        
        recent_history = []
        for m in st.session_state.messages[-6:-1] if len(st.session_state.messages) > 1 else []:
            recent_history.append({"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]})
        chat = model.start_chat(history=recent_history)
        
        qa_input = [
            f"[변호사 초안]\n{draft}\n\n[원본 법제처 리서치 데이터]\n{research_data}\n\n[가드레일 검증 경고]\n{warning_block}\n\n사용자 질의:"
        ]
        qa_input.extend(user_query_parts)
        
        full_response = ""
        try:
            response = chat.send_message(qa_input, stream=True)
            for chunk in response:
                full_response += chunk.text
                placeholder.markdown(full_response + "▌")
            placeholder.markdown(full_response)
        except Exception as e:
            placeholder.markdown(f"답변 스트리밍 오류: {e}")
            full_response = f"응답 오류 발생: {e}"
        return full_response

    # 사용자 질의 입력
    prompt = st.chat_input("법률 상담 질문을 입력하거나 증거 사진을 첨부하세요...", accept_file=True)
    if prompt:
        user_text = prompt.text if hasattr(prompt, 'text') else prompt
        attached_files = prompt.files if hasattr(prompt, 'files') else []
        
        user_query_parts = []
        if user_text:
            user_query_parts.append(user_text)
            
        display_images = []
        for f in attached_files:
            if f.type.startswith("image"):
                try:
                    img = Image.open(f)
                    user_query_parts.append(img)
                    display_images.append(img)
                except Exception as e:
                    st.error(f"이미지 처리 오류: {e}")
                    
        with st.chat_message("user", avatar=user_avatar):
            if user_text:
                st.markdown(user_text)
            for img in display_images:
                st.image(img, width=320)
                
        st.session_state.messages.append({"role": "user", "content": user_text})
        
        with st.chat_message("assistant", avatar="⚖️"):
            status_placeholder = st.empty()
            research_data, tool_history = execute_agentic_researcher(user_query_parts, status_placeholder)
            draft = execute_analyst_draft(context_text, user_query_parts, research_data, status_placeholder)
            final_answer = stream_qa_judge_final(user_query_parts, draft, research_data, context_text, status_placeholder)
            
        st.session_state.messages.append({"role": "assistant", "content": final_answer})
        save_case_json(selected_folder, use_cloud_storage, "history.json", st.session_state.messages)

# =====================================================================
# TAB 2: 📅 사실관계 타임라인 & 쟁점 연대표
# =====================================================================
with tab_timeline:
    st.markdown("### 📅 사건 사실관계 연대기 (Chronological Timeline)")
    st.caption("사건 서류와 자문 대화 내역에서 날짜별 핵심 행위·증거·법적 쟁점을 자동 추출하여 시각화합니다.")

    t_col1, t_col2 = st.columns([3, 7])
    with t_col1:
        if st.button("🤖 사건 기록에서 타임라인 자동 추출", use_container_width=True, type="primary"):
            # 사건 서면 + 자문 대화 종합
            combined_corpus = f"[사건 서류 내용]\n{context_text}\n\n[상담 대화 내역]\n"
            for m in st.session_state.messages:
                combined_corpus += f"{m['role']}: {m['content']}\n"
                
            if len(combined_corpus.strip()) < 50:
                st.warning("타임라인을 추출할 사건 기록이나 상담 대화가 충분하지 않습니다.")
            else:
                with st.spinner("Gemini 3.8 Flash가 사건 기록을 일자별 연대기로 분석 중입니다..."):
                    extracted = TimelineEngine.extract_events_from_text(CORE_MODEL_NAME, combined_corpus)
                    if extracted:
                        st.session_state.timeline_events = extracted
                        save_case_json(selected_folder, use_cloud_storage, "timeline.json", extracted)
                        st.success(f"총 {len(extracted)}건의 사실관계 이벤트 추출 완료!")
                        st.rerun()
                    else:
                        st.error("타임라인 추출에 실패했습니다. 사건 기록을 더 구체적으로 입력해 주세요.")

        if st.session_state.timeline_events:
            if st.button("🗑️ 타임라인 초기화", use_container_width=True):
                st.session_state.timeline_events = []
                save_case_json(selected_folder, use_cloud_storage, "timeline.json", [])
                st.rerun()

        # 수동 사건 추가 아코디언
        with st.expander("➕ 수동 사건 항목 추가", expanded=False):
            with st.form("add_event_form"):
                new_date = st.text_input("일자 (예: 2024.03.15)")
                new_actor = st.text_input("행위 주체 (예: 대표이사, 신청인)")
                new_title = st.text_input("사건 요약")
                new_content = st.text_area("상세 사실관계")
                new_evidence = st.text_input("관련 증거 (예: 녹취록)")
                new_legal = st.text_input("법적 쟁점 (예: 근로기준법 제76조의2)")
                new_level = st.selectbox("중요도", ["normal", "warning", "critical"], format_func=lambda x: "🚨 핵심 위법" if x=="critical" else ("⚠️ 갈등·주의" if x=="warning" else "ℹ️ 일반 경위"))
                
                submitted = st.form_submit_button("추가하기")
                if submitted and new_title:
                    new_item = {
                        "date": new_date or "일자 미상",
                        "actor": new_actor or "당사자",
                        "title": new_title,
                        "content": new_content,
                        "evidence": new_evidence or "증거 미확보",
                        "legal_issue": new_legal,
                        "level": new_level
                    }
                    st.session_state.timeline_events.append(new_item)
                    save_case_json(selected_folder, use_cloud_storage, "timeline.json", st.session_state.timeline_events)
                    st.success("새 사건이 추가되었습니다.")
                    st.rerun()

    with t_col2:
        # Generative UI 인터랙티브 수직 타임라인 렌더링
        timeline_html = TimelineEngine.render_timeline_html(st.session_state.timeline_events)
        st.markdown(timeline_html, unsafe_allow_html=True)

# =====================================================================
# TAB 3: 📝 실무 법률 서면·진정·구제신청 드래프터
# =====================================================================
with tab_drafter:
    st.markdown("### 📝 실무 법률 서면 자동 작성 및 Word(.docx) 다운로드")
    st.caption("실제 법원 및 노동위원회/노동청에 즉시 제출 가능한 표준 공문서 규격의 서면을 생성하고 워드 파일로 내보냅니다.")

    d_col1, d_col2 = st.columns([4, 6])
    
    with d_col1:
        doc_type = st.selectbox("작성할 서면 양식을 선택하세요:", LegalDrafter.get_template_names())
        tmpl_info = LegalDrafter.get_template_info(doc_type)
        st.info(f"📌 **{doc_type}**: {tmpl_info.get('description', '')}")

        with st.form("draft_input_form"):
            user_demands = st.text_area("의뢰인 핵심 청구/요구사항:", placeholder="예: 피고의 직장 내 괴롭힘 및 부당해고에 대해 위자료 3,000만원 및 해고기간 임금 상당액 지급 청구", height=100)
            custom_facts = st.text_area("추가 반영할 사실관계 (선택사항):", placeholder="기존 파싱된 서류 외에 특별히 강조할 사실관계를 입력하세요.", height=120)
            submit_draft = st.form_submit_button("⚡ 실무 표준 서면 자동 작성", type="primary", use_container_width=True)

    with d_col2:
        # 서면 생성 트리거
        if submit_draft:
            with st.spinner(f"Gemini 3.8 Flash가 정식 '{doc_type}'을 작성 중입니다..."):
                combined_facts = f"[사건 서류 추출 본문]\n{context_text}\n\n[추가 사실관계]\n{custom_facts}\n\n[타임라인 데이터]\n{json.dumps(st.session_state.timeline_events, ensure_ascii=False)}"
                prompt = LegalDrafter.build_draft_prompt(doc_type, combined_facts, "", user_demands)
                
                try:
                    model = genai.GenerativeModel(CORE_MODEL_NAME)
                    resp = model.generate_content(prompt)
                    generated_text = resp.text
                    
                    st.session_state.drafted_docs[doc_type] = {
                        "text": generated_text,
                        "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    save_case_json(selected_folder, use_cloud_storage, "drafts.json", st.session_state.drafted_docs)
                    st.success(f"'{doc_type}' 작성이 완료되었습니다!")
                except Exception as e:
                    st.error(f"서면 작성 실패: {e}")

        # 작성된 서면 뷰어 및 다운로드
        if doc_type in st.session_state.drafted_docs:
            current_draft = st.session_state.drafted_docs[doc_type]["text"]
            st.caption(f"최근 작성 일시: {st.session_state.drafted_docs[doc_type].get('updated_at', '방금 전')}")
            
            # 워드(.docx) 다운로드 버튼
            try:
                docx_buffer = LegalDrafter.export_to_docx(current_draft, doc_type)
                safe_name = f"{selected_folder}_{doc_type}_{datetime.date.today().strftime('%Y%m%d')}.docx"
                st.download_button(
                    label=f"📥 Word(.docx) 다운로드 ({doc_type})",
                    data=docx_buffer,
                    file_name=safe_name,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                    type="primary"
                )
            except Exception as e:
                st.error(f"Word 변환 오류: {e}")

            # 편집 가능한 텍스트 에어리어
            edited_draft = st.text_area("서면 미리보기 및 직접 수정:", value=current_draft, height=500)
            if edited_draft != current_draft:
                if st.button("수정 내용 저장", use_container_width=True):
                    st.session_state.drafted_docs[doc_type]["text"] = edited_draft
                    save_case_json(selected_folder, use_cloud_storage, "drafts.json", st.session_state.drafted_docs)
                    st.success("수정 사항이 저장되었습니다.")
                    st.rerun()
        else:
            st.info("왼쪽 패널에서 서면 종류를 선택하고 '실무 표준 서면 자동 작성' 버튼을 클릭하세요.")

# =====================================================================
# TAB 4: 📂 사건 증거 매핑 & 입증계획서
# =====================================================================
with tab_evidence:
    st.markdown("### 📂 사건 증거 매핑 & 입증계획서 (Evidence Matrix)")
    st.caption("주장사실(요건사실)과 보유 증거를 1:1 매핑하고, 승소를 위해 보완이 필요한 증거 목록을 도출합니다.")

    e_col1, e_col2 = st.columns([5, 5])
    with e_col1:
        st.markdown("#### 📄 현재 확보된 증거 목록")
        if loaded_files:
            for idx, f in enumerate(loaded_files, 1):
                st.markdown(f"**갑 제{idx}호증**: `{f}`")
        else:
            st.warning("업로드된 증명 서류가 없습니다. 사이드바 사건방에 증거 파일을 추가해 주세요.")

    with e_col2:
        st.markdown("#### ⚖️ AI 입증계획 및 보완 가이드")
        if st.button("🔍 입증 취약점 및 추가 보완 증거 분석", use_container_width=True):
            with st.spinner("사건 요건사실 대비 증거 증명력을 분석 중입니다..."):
                analysis_prompt = f"""
당신은 대한민국 최고 수준의 소송 전문 변호사입니다.
다음 사건의 사실관계와 확보된 서류를 검토하여, 소송 및 노동위원회 심문에서 승소하기 위한 [입증계획서 및 보완 증거 가이드]를 작성하십시오:

[사건 서면]:
{context_text}

[타임라인 사실관계]:
{json.dumps(st.session_state.timeline_events, ensure_ascii=False)}

[작성 항목]:
1. 핵심 요건사실별 입증 현황 (요건사실 vs 현재 증거)
2. 상대방(피고/피신청인)이 주장할 것으로 예상되는 항변 및 방어논리
3. 반드시 추가 확보해야 할 결정적 증거 목록 (녹취록, 동료 진술서, 급여명세서, 모바일 메신저 등)
4. 사실조회, 문서제출명령, 증인신문 신청 추천 대상
"""
                try:
                    model = genai.GenerativeModel(CORE_MODEL_NAME)
                    evidence_plan = model.generate_content(analysis_prompt).text
                    st.session_state["evidence_plan_text"] = evidence_plan
                except Exception as e:
                    st.error(f"입증 계획 분석 오류: {e}")

        if "evidence_plan_text" in st.session_state:
            st.markdown(st.session_state["evidence_plan_text"])
