import os
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "AIzaSyC70I6uDuPrUn6xLM1B4MRl1SoffLpx02Q"))

model = genai.GenerativeModel('gemini-3.5-flash')
try:
    # What if we just ask it a question?
    res = model.generate_content("hello", stream=True)
    for c in res:
        print(c.text)
except Exception as e:
    print(f"Error: {e}")
