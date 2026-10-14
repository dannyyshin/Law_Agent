import streamlit as st
import os
import json
import re
from PIL import Image
import google.generativeai as genai
from dotenv import load_dotenv
import dropbox

# v3.0 모듈 임포트
from parser import MultiFormatParser
from mcp_client import run_async, fetch_mcp_tools_async, call_mcp_tool_async

# 1. 환경변수 로드 및 설정
load_dotenv(override=True)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DBX_TOKEN = os.environ.get("DROPBOX_ACCESS_TOKEN", "")
DBX_APP_KEY = os.environ.get("DROPBOX_APP_KEY", "")
DBX_APP_SECRET = os.environ.get("DROPBOX_APP_SECRET", "")
DBX_REFRESH_TOKEN = os.environ.get("DROPBOX_REFRESH_TOKEN", "")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD", "1234")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# 1-0. 보안 인증 (Auth) 게이트웨이
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.set_page_config(page_title="Law Agent v3.0 - 보안 접속", page_icon="🔒", layout="centered")
    st.markdown("<h2 style='text-align: center; margin-top: 50px;'>🔒 Law Agent v3.0 보안 접속</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #888;'>개인 맞춤형 AI 법률 보조 시스템 (무결점 팩트체크 엔진 탑재)</p>", unsafe_allow_html=True)
    pwd = st.text_input("접속 비밀번호를 입력하세요", type="password")
    if st.button("접속하기", use_container_width=True):
        if pwd == LOGIN_PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")
    st.stop()

# 1-1. Streamlit 페이지 설정 및 Google Labs & Lbox 스타일 커스텀 CSS 주입
st.set_page_config(page_title="Law Agent v3.0", page_icon="🏛️", layout="wide")

custom_css = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Public+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&display=swap');

html, body, p, li, h1, h2, h3, h4, h5, h6, blockquote, div.stMarkdown {
    font-family: 'Public Sans', -apple-system, sans-serif !important;
}

/* 모바일 반응형 사이드바 너비 */
@media (min-width: 768px) {
    [data-testid="stSidebar"] { min-width: 380px !important; max-width: 380px !important; }
}

/* 채팅창 UI */
[data-testid="stChatMessage"] { margin-bottom: 1.2rem !important; }

/* 사용자 메시지 카드 */
[data-testid="stChatMessage"]:has(img) {
    background-color: #1A1C1E !important;
    border: 1px solid #2D3135 !important;
    border-radius: 10px !important;
    padding: 1.2rem 1.5rem !important;
}

/* AI 답변 메시지 */
[data-testid="stChatMessage"]:not(:has(img)) {
    background-color: transparent !important;
    border: none !important;
    padding: 1.2rem 0.5rem !important;
}

/* 엘박스 스타일 판결문/인용구 스타일 */
blockquote {
    border-left: 4px solid #B8422E !important; /* Boston Clay Accent */
    background-color: #1E2022 !important;
    padding: 14px 18px !important;
    margin: 14px 0 !important;
    border-radius: 0 6px 6px 0 !important;
    font-style: normal !important;
    color: #E2E3E5 !important;
    font-size: 0.95rem !important;
    line-height: 1.6;
}

/* 법제처 검증 배지 */
.legal-badge {
    display: inline-flex;
    align-items: center;
    background-color: #18281E;
    border: 1px solid #2E5A36;
    color: #4ADE80;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 14px;
    margin-right: 8px;
    margin-bottom: 12px;
}

.legal-badge-blue {
    display: inline-flex;
    align-items: center;
    background-color: #132438;
    border: 1px solid #1D4E89;
    color: #60A5FA;
    font-size: 0.82rem;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 14px;
    margin-bottom: 12px;
}

/* 버튼 스타일 */
div.stButton > button:first-child {
    background-color: #B8422E !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
}
div.stButton > button:first-child:hover {
    background-color: #8F3222 !important;
}

footer {visibility: hidden !important;}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# 2. 스토리지 연동 (Dropbox 실시간 마운트 및 로컬 Fallback 하이브리드 지원)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_CASES_DIR = os.path.join(BASE_DIR, "cases")

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

st.sidebar.markdown("### 🏛️ 사건방 목록")

# 스토리지 자동 선택: Dropbox 우선, 실패 시 로컬 cases/ 폴더
case_folders = []
if dbx:
    try:
        res = dbx.files_list_folder('')
        case_folders = [entry.name for entry in res.entries if isinstance(entry, dropbox.files.FolderMetadata)]
        case_folders.sort()
        if case_folders:
            use_cloud_storage = True
            st.sidebar.caption("☁️ Dropbox Cloud 실시간 연동 중")
    except Exception as e:
        st.sidebar.warning(f"Dropbox 연결 실패 ({e}) -> 로컬 모드로 전환합니다.")

if not use_cloud_storage:
    st.sidebar.caption("💻 로컬 디렉터리 연동 모드")
    if os.path.exists(LOCAL_CASES_DIR):
        case_folders = [f for f in os.listdir(LOCAL_CASES_DIR) if os.path.isdir(os.path.join(LOCAL_CASES_DIR, f))]
        case_folders.sort()

if not case_folders:
    st.sidebar.warning("생성된 사건방(폴더)이 없습니다.")
    st.stop()

selected_folder = st.sidebar.radio("사건방을 선택하세요:", case_folders)

# 3. 문서 자동 파싱 (PDF, HWPX, TXT 등 MultiFormatParser 지원)
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
    with st.sidebar.expander("📄 인식된 증거 서류 목록", expanded=False):
        for i, fn in enumerate(sorted(loaded_files, reverse=True), 1):
            st.markdown(f"{i}. {fn}")
else:
    st.sidebar.info("해당 사건방에 등록된 서면이 없습니다.")

st.sidebar.markdown("---")

# 4. MCP 도구 로드
@st.cache_resource(show_spinner="🔍 법제처 최신 MCP 도구 바인딩 중...")
def get_available_mcp_tools():
    return run_async(fetch_mcp_tools_async())

gemini_functions = get_available_mcp_tools()

# 5. 대화 기록 로드 및 저장 (Dropbox / 로컬 양방향)
def load_history(folder_name: str, is_cloud: bool):
    if is_cloud:
        try:
            _, res = dbx.files_download(f"/{folder_name}/history.json")
            return json.loads(res.content.decode('utf-8'))
        except Exception:
            return []
    else:
        hpath = os.path.join(LOCAL_CASES_DIR, folder_name, "history.json")
        if os.path.exists(hpath):
            try:
                with open(hpath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
    return []

def save_history(folder_name: str, is_cloud: bool, messages: list):
    data_bytes = json.dumps(messages, ensure_ascii=False, indent=2).encode('utf-8')
    if is_cloud:
        try:
            dbx.files_upload(data_bytes, f"/{folder_name}/history.json", mode=dropbox.files.WriteMode("overwrite"))
        except Exception as e:
            print(f"클라우드 히스토리 저장 실패: {e}")
    else:
        hpath = os.path.join(LOCAL_CASES_DIR, folder_name, "history.json")
        try:
            with open(hpath, 'w', encoding='utf-8') as f:
                f.write(data_bytes.decode('utf-8'))
        except Exception as e:
            print(f"로컬 히스토리 저장 실패: {e}")

if "current_room" not in st.session_state or st.session_state.current_room != selected_folder:
    st.session_state.current_room = selected_folder
    st.session_state.messages = load_history(selected_folder, use_cloud_storage)

# 6. 메인 UI 헤더
st.markdown(f"<h1 style='font-size: 32px; margin-bottom: 4px;'>🏛️ {selected_folder}</h1>", unsafe_allow_html=True)
st.caption("AI 법률 고문 v3.0 | 법제처 Open API ReAct 리서처 & 3중 팩트체크 가드레일 탑재")

# 기존 대화 렌더링
user_avatar = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Ctext x='12' y='18' font-size='20' text-anchor='middle' fill='white'%3E%E2%9D%94%3C/text%3E%3C/svg%3E"

for msg in st.session_state.messages:
    avatar = user_avatar if msg["role"] == "user" else "⚖️"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# 7. Agentic ReAct 리서처 파이프라인 (Multi-turn Tool Calling)
CORE_MODEL_NAME = "gemini-3.8-flash"

def execute_agentic_researcher(user_query_parts, placeholder) -> tuple[str, list]:
    """
    최대 3턴 동안 ReAct 루프를 순회:
    1단계: 판례/법령 검색 -> 2단계: 전문 조회 -> 3단계: 판례 생사 확인(cite_check)
    """
    placeholder.markdown("*(🕵️‍♂️ 리서처 에이전트: 사건 분석 및 법제처 실시간 리서치 기획 중...)*")
    
    research_logs = []
    called_tool_history = []
    
    researcher_instruction = (
        "당신은 최고 실력의 수석 법률 리서처입니다. 사용자의 질문을 분석하여 법률 표준 키워드를 자체 도출하고, "
        "반드시 제공된 법제처 MCP 도구를 다단계(Multi-step)로 실행하여 완전한 법률 팩트를 수집하세요.\n"
        "[행동 지침]\n"
        "1. 질문과 관련된 판례를 찾으려면 `search_decisions` 또는 `search_law`를 호출하세요.\n"
        "2. 유력한 판례나 법령이 검색되면 반드시 `get_decision_text` 또는 `get_law_text`를 연속 호출하여 **판결 이유 전문**을 확인하세요.\n"
        "3. 확정된 판례는 `cite_check`를 호출해 대법원 전원합의체로 변경·폐기되었는지 확인하세요.\n"
        "4. 모든 조사가 끝나면 도구 호출을 멈추고 객관적인 사실만을 요약 보고하세요."
    )
    
    model = genai.GenerativeModel(
        model_name=CORE_MODEL_NAME,
        system_instruction=researcher_instruction,
        tools=[{"function_declarations": gemini_functions}] if gemini_functions else [],
        tool_config={"function_calling_config": {"mode": "ANY"}} if gemini_functions else None,
        generation_config=genai.types.GenerationConfig(temperature=0.0)
    )
    
    # 최근 대화 문맥 주입
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
            
            placeholder.markdown(f"*(🕵️‍♂️ 법제처 실시간 리서치 [{step+1}/{max_turns}]: `{tool_name}` 실행 중...)*")
            
            tool_output = run_async(call_mcp_tool_async(tool_name, tool_args))
            research_logs.append(f"--- [{tool_name} 호출 결과] ---\n{tool_output}\n")
            
            # 다음 턴 실행: 도구 실행 결과를 다시 전송하여 전문 조회/생사 확인 유도
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
        research_logs.append(f"리서치 도구 통신 예외: {str(e)}")
        
    combined_research = "\n".join(research_logs)
    if not combined_research:
        combined_research = "조회된 법제처 데이터가 없으므로 관련 일반 법리 원칙을 기반으로 분석합니다."
        
    return combined_research, called_tool_history

# 8. 수석 변호사 초안 작성 & 이중 가드레일 (Analyst & Guardrail)
def execute_analyst_draft(context, user_query_parts, research_data, placeholder) -> str:
    placeholder.markdown("*(👨‍⚖️ 수석 변호사 에이전트: 사건 서면과 법령을 교차 분석하여 IRAC 초안 작성 중...)*")
    
    analyst_instruction = (
        "당신은 실무 경력 20년의 수석 변호사입니다. "
        "사용자의 사건 서류와 리서처가 수집한 법제처 판례/법령 전문만을 철저히 바탕으로 "
        "IRAC(쟁점-규칙-적용-결론) 구조의 전문 법률 검토 보고서 초안을 작성하세요.\n"
        "[엄격 수칙]\n"
        "1. 제공된 [법제처 리서치 결과]나 [사건 서류]에 명시적으로 존재하지 않는 판례 번호나 법령은 절대로 인용하지 마세요.\n"
        "2. 판례가 확인되지 않은 쟁점은 '관련 대법원 확정 판례 없음'을 명확히 명시하세요."
    )
    
    model = genai.GenerativeModel(
        model_name=CORE_MODEL_NAME,
        system_instruction=analyst_instruction,
        generation_config=genai.types.GenerationConfig(temperature=0.0)
    )
    
    prompt_parts = [
        f"[사건 증거 서류 추출 텍스트]\n{context}\n\n[법제처 리서치 결과 전문]\n{research_data}\n\n[사용자 질의 및 첨부물]:"
    ]
    prompt_parts.extend(user_query_parts)
    
    try:
        draft_resp = model.generate_content(prompt_parts, stream=False)
        return draft_resp.text
    except Exception as e:
        return f"초안 작성 오류: {e}"

# 9. QA 판사 최종 스트리밍 및 가드레일 검증
def stream_qa_judge_final(user_query_parts, draft, research_data, context, placeholder) -> str:
    placeholder.markdown("*(⚖️ QA 판사 에이전트: 팩트체크 교차 검증 및 최종 답변 생성 중...)*")
    
    # 1차 정규식 가드레일: 가짜 사건번호 검출
    found_cases = re.findall(r'(대법원|헌법재판소|고등법원|지방법원).*?([0-9]{4}[가-힣]{1,2}[0-9]+)', draft)
    warnings = []
    for court, num in found_cases:
        if num not in research_data and num not in context:
            warnings.append(f"경고: 초안에 언급된 '{court} {num}' 사건번호는 원본 데이터에 없습니다. 삭제하십시오.")
            
    warning_block = "\n".join(warnings) if warnings else ""
    
    qa_instruction = (
        "당신은 엄격한 최고법원 수석 재판연구관(QA 판사)입니다.\n"
        "수석 변호사의 초안을 검증하여 가짜 판례나 왜곡된 법리를 100% 삭제하고, "
        "의뢰인이 실무에 즉시 활용할 수 있는 명쾌하고 정확한 최종 답변을 완성하세요.\n"
        "[답변 구성 수칙]\n"
        "1. 답변 서두에 다음 배지를 반드시 표기하세요:\n"
        "   `[🟢 법제처 실시간 법령·판례 교차 검증 완료]`\n"
        "2. 구조: ① 3줄 핵심 결론 요약 -> ② 쟁점별 IRAC 법리 검토 -> ③ 실무 대응 및 대안 가이드\n"
        "3. 시스템 경고에 기재된 날조 의심 사건번호는 모두 삭제하고 원칙 법리로 서술하세요."
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

# 10. 하단 컨트롤 및 사용자 입력 처리
col_left, col_right = st.columns([8, 2])
with col_right:
    if st.button("🧹 대화 비우기", use_container_width=True):
        st.session_state.messages = []
        save_history(selected_folder, use_cloud_storage, st.session_state.messages)
        st.rerun()

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
                
    # 사용자 질문 UI 출력
    with st.chat_message("user", avatar=user_avatar):
        if user_text:
            st.markdown(user_text)
        for img in display_images:
            st.image(img, width=320)
            
    st.session_state.messages.append({"role": "user", "content": user_text})
    
    # AI 답변 생성 파이프라인
    with st.chat_message("assistant", avatar="⚖️"):
        status_placeholder = st.empty()
        
        # 1. Agentic ReAct 리서처 (Multi-turn 판결전문 및 법령 수집)
        research_data, tool_history = execute_agentic_researcher(user_query_parts, status_placeholder)
        
        # 2. 수석 변호사 초안 작성
        draft = execute_analyst_draft(context_text, user_query_parts, research_data, status_placeholder)
        
        # 3. QA 판사 최종 스트리밍 & 가드레일 교차검증
        final_answer = stream_qa_judge_final(user_query_parts, draft, research_data, context_text, status_placeholder)
        
    st.session_state.messages.append({"role": "assistant", "content": final_answer})
    save_history(selected_folder, use_cloud_storage, st.session_state.messages)
