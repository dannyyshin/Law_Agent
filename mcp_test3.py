import json
import google.generativeai as genai

with open("mcp_tools.json", "r", encoding="utf-8") as f:
    mcp_tools = json.load(f)

gemini_functions = []
for t in mcp_tools:
    schema = t["inputSchema"]
    if "apiKey" in schema["properties"]:
        del schema["properties"]["apiKey"]
    if "apiKey" in schema.get("required", []):
        schema["required"].remove("apiKey")
    
    gemini_functions.append({
        "name": t["name"],
        "description": t["description"],
        "parameters": schema
    })

tool = {"function_declarations": gemini_functions}

import os
from dotenv import load_dotenv
load_dotenv(override=True)
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-3.5-flash", tools=[tool])

print("Model loaded with dynamic tools!")
response = model.generate_content("민법 제103조의 파급효과(impact_map)를 그려줘.")
if response.candidates[0].content.parts[0].function_call:
    fn = response.candidates[0].content.parts[0].function_call
    print(f"Tool called: {fn.name}")
    print(f"Args: {fn.args}")
