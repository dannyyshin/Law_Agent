import streamlit as st
import os
import json
import fitz  # PyMuPDF
import google.generativeai as genai
from dotenv import load_dotenv
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# 1. 환경변수 로드 및 제미나이 설정
load_dotenv(override=True)
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)

# 1-1. UI/UX 개선을 위한 커스텀 CSS 주입
custom_css = """
<style>
/* 1. 개발자 메뉴 숨김 (안전한 푸터만 숨김) */
footer {visibility: hidden !important;}

/* 2. 사이드바 너비 확장 */
[data-testid="stSidebar"] {
    min-width: 450px !important;
    max-width: 450px !important;
}

/* 3. 법률 상담용 가독성 및 안티그래비티 UI 적용 */
p, li, span, div.stMarkdown {
    font-size: 0.92rem !important;
}

[data-testid="stChatMessage"] {
    margin-bottom: 1rem !important;
}

/* 사용자 질문 창 (이미지 아바타를 가짐) */
[data-testid="stChatMessage"]:has(img) {
    background-color: #1A1A1A !important;
    border: 1px solid #333333 !important;
    border-radius: 8px !important;
    padding: 1.2rem 1.5rem !important;
}

/* AI 답변 창 (이모지 아바타를 가짐) */
[data-testid="stChatMessage"]:not(:has(img)) {
    background-color: transparent !important;
    border: none !important;
    padding: 1.5rem 0.5rem !important;
}
blockquote {
    border-left: 5px solid #1E88E5 !important;
    background-color: #ffffff !important;
    padding: 15px 20px !important;
    margin: 15px 0 !important;
    border-radius: 0 8px 8px 0 !important;
    font-style: normal !important;
    color: #000000 !important;
    font-weight: 500 !important;
}

/* 6. 로딩바 화면 중앙 고정 */
[data-testid="stSpinner"] {
    position: fixed !important;
    top: 50% !important;
    left: 50% !important;
    transform: translate(-50%, -50%) !important;
    z-index: 999999 !important;
}
</style>
"""
st.markdown(custom_css, unsafe_allow_html=True)

# 기본 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CASES_DIR = os.path.join(BASE_DIR, "cases")

# 2. 사이드바: 방(폴더) 선택
st.sidebar.markdown("### 📁 법률 상담 방 목록")

if not os.path.exists(CASES_DIR):
    st.sidebar.error("cases 폴더가 없습니다.")
    st.stop()

folders = [f for f in os.listdir(CASES_DIR) if os.path.isdir(os.path.join(CASES_DIR, f))]
folders.sort()

if not folders:
    st.sidebar.warning("생성된 사건방(폴더)이 없습니다.")
    st.stop()

selected_folder = st.sidebar.radio("방을 선택하세요:", folders)
current_folder_path = os.path.join(CASES_DIR, selected_folder)
history_file_path = os.path.join(current_folder_path, "history.json")

st.sidebar.markdown("---")

st.markdown(f"<h1 style='font-size: 40px; margin-bottom: 20px;'>🏛️ {selected_folder}</h1>", unsafe_allow_html=True)

# 3. 문서 자동 인식 (PDF 파싱)
@st.cache_data(show_spinner=False)
def load_pdf_texts(folder_path):
    pdf_texts = ""
    for filename in os.listdir(folder_path):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(folder_path, filename)
            try:
                doc = fitz.open(pdf_path)
                for page in doc:
                    pdf_texts += page.get_text() + "\n"
            except Exception as e:
                st.error(f"PDF 읽기 오류 ({filename}): {e}")
    return pdf_texts

with st.spinner("사건 자료(PDF)를 분석하는 중..."):
    context_text = load_pdf_texts(current_folder_path)

pdf_files = [f for f in os.listdir(current_folder_path) if f.lower().endswith('.pdf')]
if pdf_files:
    st.sidebar.success(f"✅ {len(pdf_files)}개의 사건 자료 인식 완료")
    with st.sidebar.expander("📂 인식된 문서 목록", expanded=True):
        for i, f in enumerate(sorted(pdf_files, reverse=True), 1):
            st.markdown(f"{i}. {f}")
else:
    st.sidebar.info("첨부된 PDF 사건 자료가 없습니다.")

# 4. MCP 연결 및 도구 로드
@st.cache_resource(show_spinner="MCP 도구 목록을 불러오는 중...")
def get_mcp_tools():
    async def fetch_tools():
        server_params = StdioServerParameters(
            command="cmd",
            args=["/c", "korean-law-mcp"],
            env=os.environ.copy()
        )
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools_resp = await session.list_tools()
                    
                    def clean_schema(s):
                        if not isinstance(s, dict):
                            return
                        allowed_keys = {"type", "format", "description", "nullable", "enum", "properties", "required", "items"}
                        keys_to_remove = [k for k in s.keys() if k not in allowed_keys]
                        for k in keys_to_remove:
                            s.pop(k, None)
                        
                        if "properties" in s:
                            for key in list(s["properties"].keys()):
                                clean_schema(s["properties"][key])
                        if "items" in s:
                            clean_schema(s["items"])

                    gemini_functions = []
                    for t in tools_resp.tools:
                        schema = t.inputSchema.copy()
                        if "apiKey" in schema.get("properties", {}):
                            del schema["properties"]["apiKey"]
                        if "apiKey" in schema.get("required", []):
                            schema["required"].remove("apiKey")
                        
                        clean_schema(schema)
                        
                        gemini_functions.append({
                            "name": t.name,
                            "description": t.description,
                            "parameters": schema
                        })
                    return gemini_functions
        except Exception as e:
            print(f"MCP 통신 오류: {e}")
            return []
    return asyncio.run(fetch_tools())

gemini_functions = get_mcp_tools()

async def call_mcp_tool_async(tool_name: str, args: dict):
    server_params = StdioServerParameters(
        command="cmd",
        args=["/c", "korean-law-mcp"],
        env=os.environ.copy()
    )
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, args)
            if result.content:
                return "\n".join([c.text for c in result.content if hasattr(c, 'text')])
            return str(result)

# 5. 모델 설정 (System Instruction 구성)
main_instruction = "당신은 유능하고 극도로 효율적인 법률 AI 고문입니다.\n\n"
main_instruction += "[핵심 규칙: 스마트 케이브맨 모드]\n"
main_instruction += "1. 인사말, 서론, 감정적 공감 등 불필요한 미사여구를 100% 생략하세요.\n"
main_instruction += "2. 답변은 무조건 결론부터 3줄 이내로 먼저 요약하세요.\n"
main_instruction += "3. 법리 분석은 IRAC(쟁점, 규칙, 적용, 결론) 구조를 따르되 최대한 간결하게 개조식으로 작성하세요.\n"
main_instruction += "4. MCP 도구 데이터가 제공되면 이를 바탕으로 답변하고, '제공해주신 법제처 오픈 API 실시간 검색 결과입니다'라고 명시하세요. 데이터가 부족하면 함부로 추측하지 마세요.\n"

if context_text:
    main_instruction += f"\n\n다음은 사용자가 제공한 사건 관련 문서 자료(PDF 추출 텍스트)입니다. 위 법령과 함께 이 문서도 분석하여 답변하세요:\n\n{context_text}"

tool_instruction = "당신은 사용자의 질문을 분석하여 가장 적합한 법률 검색어를 추출하고, 반드시 법제처 검색 도구를 호출해야 하는 검색 전담 AI입니다."

model_name = "gemini-3.5-flash"

main_model = genai.GenerativeModel(
    model_name=model_name,
    system_instruction=main_instruction
)

tool_model = genai.GenerativeModel(
    model_name=model_name,
    system_instruction=tool_instruction,
    tools=[{"function_declarations": gemini_functions}] if gemini_functions else [],
    tool_config={"function_calling_config": {"mode": "ANY"}} if gemini_functions else None
)

# 6. 채팅 기록 처리
def load_history():
    if os.path.exists(history_file_path):
        with open(history_file_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []

def save_history(history):
    with open(history_file_path, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

if "current_room" not in st.session_state or st.session_state.current_room != selected_folder:
    st.session_state.current_room = selected_folder
    st.session_state.messages = load_history()

user_avatar = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Ctext x='12' y='18' font-size='20' text-anchor='middle' fill='white'%3E%E2%9D%94%3C/text%3E%3C/svg%3E"

for msg in st.session_state.messages:
    avatar = user_avatar if msg["role"] == "user" else "🟢"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# 7. 실행 함수 정의 (1단계: 도구 전용 실행)
def execute_tool_only(tool_request_parts, placeholder):
    placeholder.markdown("*(AI가 사용자 질문에 가장 적합한 법률 도구를 찾고 있습니다...)*")
    law_data = ""
    called_tool_name = None
    
    try:
        tool_chat = tool_model.start_chat()
        # 스트리밍 없이 오직 도구 호출용 전송 (mode="ANY" 적용됨)
        tool_res = tool_chat.send_message(tool_request_parts, stream=False)
        
        if tool_res.candidates and tool_res.candidates[0].content.parts:
            for part in tool_res.candidates[0].content.parts:
                if fn := part.function_call:
                    called_tool_name = fn.name
                    tool_args = dict(fn.args)
                    
                    placeholder.markdown(f"*(MCP 도구 실행 중... **{called_tool_name}**)*")
                    
                    tool_result = asyncio.run(call_mcp_tool_async(called_tool_name, tool_args))
                    law_data += f"\n--- {called_tool_name} 결과 ---\n{tool_result}\n"
                    
        if not law_data:
            law_data = "특별히 호출된 검색 도구가 없으므로, 기본 지식과 컨텍스트를 활용합니다."
    except Exception as e:
        print(f"도구 호출 에러: {e}")
        law_data = f"MCP 시스템 통신 실패: {str(e)}"
        
    return called_tool_name, law_data

# 8. 답변 생성 함수 정의 (2단계: 스트리밍 메인 함수)
def stream_response(context, user_text, uploaded_files, placeholder, called_tool_name):
    placeholder.markdown("*(법령 데이터 분석 및 답변 생성 중...)*")
    
    gemini_history = []
    for msg in st.session_state.messages[:-1]:
        role = "user" if msg["role"] == "user" else "model"
        gemini_history.append({"role": role, "parts": [msg["content"]]})
        
    chat = main_model.start_chat(history=gemini_history)
    
    if called_tool_name:
        final_prompt = f"사용자 질문: {user_text}\n\n[{called_tool_name} MCP 도구 데이터]\n{context}"
    else:
        final_prompt = user_text
        
    request_parts = [final_prompt]
    if uploaded_files:
        for f in uploaded_files:
            request_parts.insert(0, {"mime_type": f.type, "data": f.getvalue()})
        
    full_response = ""
    try:
        # 2단계: 스트리밍 켜고 최종 답변 생성
        response = chat.send_message(request_parts, stream=True)
        for chunk in response:
            full_response += chunk.text
            placeholder.markdown(full_response + "▌")
        placeholder.markdown(full_response)
    except Exception as e:
        st.error(f"상세 에러: {e}")
        full_response = f"응답을 생성하는 중 오류가 발생했습니다. ({e})"
        
    return full_response

# 9. 하단 고정 UI 및 채팅 입력
col1, col2 = st.columns([8, 2])
with col2:
    if st.button("🧹 이 방의 대화 비우기", use_container_width=True):
        st.session_state.messages = []
        with open(history_file_path, 'w', encoding='utf-8') as f:
            json.dump([], f, ensure_ascii=False, indent=2)
        st.rerun()

prompt = st.chat_input("법률 관련 질문을 입력하세요...", accept_file="multiple", file_type=["png", "jpg", "jpeg"])

if prompt:
    user_text = prompt.text if hasattr(prompt, 'text') else (prompt["text"] if isinstance(prompt, dict) else prompt)
    uploaded_files = prompt.files if hasattr(prompt, 'files') else (prompt.get("files", []) if isinstance(prompt, dict) else [])
    
    display_text = user_text if user_text else "[이미지 파일 첨부]"
    
    with st.chat_message("user", avatar=user_avatar):
        st.markdown(display_text)
    st.session_state.messages.append({"role": "user", "content": display_text})
    save_history(st.session_state.messages)
    
    with st.chat_message("assistant", avatar="🟢"):
        response_placeholder = st.empty()
        
        # 파이프라인 구성 (도구 호출 -> 답변 스트리밍)
        tool_request_parts = [display_text]
        if uploaded_files:
            for f in uploaded_files:
                tool_request_parts.insert(0, {"mime_type": f.type, "data": f.getvalue()})
                
        # 1단계: execute_tool_only 실행
        called_tool_name, law_data = execute_tool_only(tool_request_parts, response_placeholder)
        
        # 2단계: stream_response 실행
        full_response = stream_response(law_data, display_text, uploaded_files, response_placeholder, called_tool_name)
            
    st.session_state.messages.append({"role": "assistant", "content": full_response})
    save_history(st.session_state.messages)
