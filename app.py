import streamlit as st
import os
import json
import fitz  # PyMuPDF
import google.generativeai as genai
from dotenv import load_dotenv
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import dropbox

# 1. 환경변수 로드 및 제미나이 설정
load_dotenv(override=True)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
DBX_TOKEN = os.environ.get("DROPBOX_ACCESS_TOKEN", "")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD", "1234")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# 1-0. 보안 인증 (Auth) 모듈
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🔒 Law Agent 보안 접속")
    pwd = st.text_input("비밀번호를 입력하세요", type="password")
    if st.button("접속"):
        if pwd == LOGIN_PASSWORD:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("비밀번호가 일치하지 않습니다.")
    st.stop()

# 1-1. UI/UX 개선을 위한 커스텀 CSS 주입
custom_css = """
<style>
footer {visibility: hidden !important;}
[data-testid="stSidebar"] { min-width: 400px !important; max-width: 400px !important; }
p, li, span, div.stMarkdown { font-size: 0.92rem !important; }
[data-testid="stChatMessage"] { margin-bottom: 1rem !important; }
[data-testid="stChatMessage"]:has(img) { background-color: #1A1A1A !important; border: 1px solid #333333 !important; border-radius: 8px !important; padding: 1.2rem 1.5rem !important; }
[data-testid="stChatMessage"]:not(:has(img)) { background-color: transparent !important; border: none !important; padding: 1.5rem 0.5rem !important; }
blockquote { border-left: 5px solid #1E88E5 !important; background-color: #ffffff !important; padding: 15px 20px !important; margin: 15px 0 !important; border-radius: 0 8px 8px 0 !important; font-style: normal !important; color: #000000 !important; font-weight: 500 !important; }
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# 2. 드롭박스 API 연동 (가상 파일 시스템)
st.sidebar.markdown("### ☁️ Dropbox 사건방 목록")

@st.cache_resource
def get_dbx():
    if not DBX_TOKEN:
        return None
    return dropbox.Dropbox(DBX_TOKEN)

dbx = get_dbx()
if not dbx:
    st.sidebar.error("Dropbox Token이 설정되지 않았습니다.")
    st.stop()

try:
    # 최상위 폴더 목록 가져오기
    res = dbx.files_list_folder('')
    folders = [entry.name for entry in res.entries if isinstance(entry, dropbox.files.FolderMetadata)]
except Exception as e:
    st.sidebar.error(f"Dropbox 연결 오류: {e}")
    st.stop()

folders.sort()
if not folders:
    st.sidebar.warning("드롭박스에 생성된 사건방(폴더)이 없습니다.")
    st.stop()

selected_folder = st.sidebar.radio("방을 선택하세요:", folders)

st.sidebar.markdown("---")
st.markdown(f"<h1 style='font-size: 35px; margin-bottom: 20px;'>🏛️ {selected_folder}</h1>", unsafe_allow_html=True)

# 3. 문서 자동 인식 (PDF 파싱 - 드롭박스 실시간 마운트)
@st.cache_data(show_spinner=False)
def load_dropbox_pdfs(folder_name):
    pdf_texts = ""
    pdf_files = []
    try:
        res = dbx.files_list_folder(f'/{folder_name}')
        for entry in res.entries:
            if isinstance(entry, dropbox.files.FileMetadata) and entry.name.lower().endswith('.pdf'):
                pdf_files.append(entry.name)
                _, response = dbx.files_download(entry.path_lower)
                doc = fitz.open(stream=response.content, filetype="pdf")
                for page in doc:
                    pdf_texts += page.get_text() + "\n"
    except Exception as e:
        print(f"드롭박스 PDF 읽기 오류: {e}")
    return pdf_texts, pdf_files

with st.spinner("☁️ 드롭박스에서 사건 자료(PDF) 동기화 중..."):
    context_text, pdf_files = load_dropbox_pdfs(selected_folder)

if pdf_files:
    st.sidebar.success(f"✅ {len(pdf_files)}개의 사건 자료 인식 완료")
    with st.sidebar.expander("📂 인식된 문서 목록", expanded=True):
        for i, f in enumerate(sorted(pdf_files, reverse=True), 1):
            st.markdown(f"{i}. {f}")
else:
    st.sidebar.info("드롭박스 해당 폴더에 PDF가 없습니다.")

# 4. MCP 연결 (크로스플랫폼 지원 npx/cmd)
mcp_command = "npx.cmd" if os.name == "nt" else "npx"
mcp_args = ["-y", "korean-law-mcp"] if os.name != "nt" else ["-y", "korean-law-mcp"]
# 윈도우 로컬의 경우 cmd /c korean-law-mcp 방식 보존 (기존과 동일하게 작동)
if os.name == "nt":
    mcp_command = "cmd"
    mcp_args = ["/c", "korean-law-mcp"]

@st.cache_resource(show_spinner="MCP 도구 목록을 불러오는 중...")
def get_mcp_tools():
    async def fetch_tools():
        server_params = StdioServerParameters(command=mcp_command, args=mcp_args, env=os.environ.copy())
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_resp = await session.list_tools()
                    
                    def clean_schema(s):
                        if not isinstance(s, dict): return
                        allowed_keys = {"type", "format", "description", "nullable", "enum", "properties", "required", "items"}
                        keys_to_remove = [k for k in s.keys() if k not in allowed_keys]
                        for k in keys_to_remove: s.pop(k, None)
                        if "properties" in s:
                            for key in list(s["properties"].keys()): clean_schema(s["properties"][key])
                        if "items" in s: clean_schema(s["items"])

                    gemini_functions = []
                    for t in tools_resp.tools:
                        schema = t.inputSchema.copy()
                        if "apiKey" in schema.get("properties", {}): del schema["properties"]["apiKey"]
                        if "apiKey" in schema.get("required", []): schema["required"].remove("apiKey")
                        clean_schema(schema)
                        gemini_functions.append({"name": t.name, "description": t.description, "parameters": schema})
                    return gemini_functions
        except Exception as e:
            print(f"MCP 통신 내부 오류: {e}")
            return []
    try:
        import nest_asyncio
        nest_asyncio.apply()
    except ImportError:
        pass
    try:
        return asyncio.run(fetch_tools())
    except Exception as e:
        print(f"MCP asyncio 실행 오류: {e}")
        return []

gemini_functions = get_mcp_tools()

async def call_mcp_tool_async(tool_name: str, args: dict):
    server_params = StdioServerParameters(command=mcp_command, args=mcp_args, env=os.environ.copy())
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, args)
            if result.content:
                return "\n".join([c.text for c in result.content if hasattr(c, 'text')])
            return str(result)

# 5. Harness 아키텍처: 다중 에이전트 시스템 정의
model_name = "gemini-1.5-flash"

# Agent 1: 리서처 (도구 호출 전담)
researcher_instruction = "당신은 법률 리서처입니다. 질문을 분석하여 반드시 법제처 MCP 도구를 호출해 관련 법령 데이터를 수집하세요."
researcher_model = genai.GenerativeModel(
    model_name=model_name,
    system_instruction=researcher_instruction,
    tools=[{"function_declarations": gemini_functions}] if gemini_functions else [],
    tool_config={"function_calling_config": {"mode": "ANY"}} if gemini_functions else None
)

# Agent 2: 수석 변호사 (초안 작성 전담)
analyst_instruction = (
    "당신은 수석 변호사입니다. 리서처가 수집한 법령 데이터와 사용자의 드롭박스 사건 자료를 종합 분석하여 "
    "IRAC(쟁점, 규칙, 적용, 결론) 구조로 법리 분석 초안을 작성하세요. "
    "명확하고 간결한 개조식으로 작성하며, 데이터에 없는 내용은 절대 지어내지 마세요."
)
analyst_model = genai.GenerativeModel(model_name=model_name, system_instruction=analyst_instruction)

# Agent 3: QA 판사 (검증 전담 및 최종 스트리밍 출력)
qa_instruction = (
    "당신은 엄격한 QA 판사입니다. 수석 변호사가 작성한 초안을 원본 데이터와 교차 검증하세요. "
    "1. 환각(없는 법령이나 사실 지어내기)이 없는지 확인하세요. "
    "2. 만약 오류가 있다면 수정하여 최종 답변을 내놓고, 오류가 없다면 초안을 바탕으로 완벽한 최종 답변을 출력하세요. "
    "3. 답변 어딘가에 반드시 '제공해주신 법제처 오픈 API 실시간 검색 결과 기반입니다'라고 명시하세요."
)
qa_model = genai.GenerativeModel(model_name=model_name, system_instruction=qa_instruction)


# 6. 채팅 기록 처리 (임시 메모리 저장)
if "current_room" not in st.session_state or st.session_state.current_room != selected_folder:
    st.session_state.current_room = selected_folder
    st.session_state.messages = []

user_avatar = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Ctext x='12' y='18' font-size='20' text-anchor='middle' fill='white'%3E%E2%9D%94%3C/text%3E%3C/svg%3E"

for msg in st.session_state.messages:
    avatar = user_avatar if msg["role"] == "user" else "🟢"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# 7. 실행 로직
def execute_researcher(tool_request_parts, placeholder):
    placeholder.markdown("*(🕵️‍♂️ 리서처 에이전트: 법률 데이터 검색 중...)*")
    law_data = ""
    called_tool_name = None
    try:
        tool_chat = researcher_model.start_chat()
        tool_res = tool_chat.send_message(tool_request_parts, stream=False)
        
        if tool_res.candidates and tool_res.candidates[0].content.parts:
            for part in tool_res.candidates[0].content.parts:
                if fn := part.function_call:
                    called_tool_name = fn.name
                    placeholder.markdown(f"*(🕵️‍♂️ 리서처 에이전트: MCP 실행 중... **{called_tool_name}**)*")
                    tool_result = asyncio.run(call_mcp_tool_async(called_tool_name, dict(fn.args)))
                    law_data += f"\n--- {called_tool_name} 결과 ---\n{tool_result}\n"
                    
        if not law_data: law_data = "조회된 법령 데이터가 없습니다."
    except Exception as e:
        law_data = f"통신 실패: {str(e)}"
    return called_tool_name, law_data

def execute_analyst(context, user_text, law_data, placeholder):
    placeholder.markdown("*(👨‍⚖️ 수석 변호사 에이전트: IRAC 법리 분석 초안 작성 중...)*")
    prompt = f"사용자 질문: {user_text}\n\n[사건 자료]\n{context}\n\n[리서처 수집 법령]\n{law_data}"
    try:
        draft_response = analyst_model.generate_content(prompt, stream=False)
        return draft_response.text
    except Exception as e:
        return f"초안 작성 실패: {e}"

def stream_qa(user_text, draft, law_data, placeholder):
    placeholder.markdown("*(⚖️ QA 판사 에이전트: 팩트체크 및 최종 답변 생성 중...)*")
    
    gemini_history = []
    for msg in st.session_state.messages[:-1]:
        role = "user" if msg["role"] == "user" else "model"
        gemini_history.append({"role": role, "parts": [msg["content"]]})
        
    chat = qa_model.start_chat(history=gemini_history)
    qa_prompt = f"사용자 질문: {user_text}\n\n[변호사 초안]\n{draft}\n\n[원본 법령 데이터]\n{law_data}"
    
    full_response = ""
    try:
        response = chat.send_message(qa_prompt, stream=True)
        for chunk in response:
            full_response += chunk.text
            placeholder.markdown(full_response + "▌")
        placeholder.markdown(full_response)
    except Exception as e:
        placeholder.markdown(f"오류: {e}")
        full_response = f"응답 오류: {e}"
    return full_response

col1, col2 = st.columns([8, 2])
with col2:
    if st.button("🧹 대화 비우기", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

prompt = st.chat_input("법률 관련 질문을 입력하세요...")

if prompt:
    user_text = prompt
    with st.chat_message("user", avatar=user_avatar):
        st.markdown(user_text)
    st.session_state.messages.append({"role": "user", "content": user_text})
    
    with st.chat_message("assistant", avatar="🟢"):
        response_placeholder = st.empty()
        
        # 1. Researcher
        called_tool_name, law_data = execute_researcher([user_text], response_placeholder)
        
        # 2. Analyst
        draft = execute_analyst(context_text, user_text, law_data, response_placeholder)
        
        # 3. QA Judge (스트리밍)
        final_answer = stream_qa(user_text, draft, law_data, response_placeholder)
            
    st.session_state.messages.append({"role": "assistant", "content": final_answer})
