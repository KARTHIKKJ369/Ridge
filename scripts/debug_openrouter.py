import os
from dotenv import load_dotenv
load_dotenv()

from langchain_openrouter import ChatOpenRouter

print("OPENROUTER_API_KEY set:", bool(os.environ.get("OPENROUTER_API_KEY")))

llm = ChatOpenRouter(model="meta-llama/llama-3.3-70b-instruct:free", temperature=0)

try:
    response = llm.invoke("Say hello in one word.")
    print("SUCCESS:", response.content)
except Exception as e:
    print("EXCEPTION TYPE:", type(e))
    for attr in ("response_data", "http_res_text", "http_res", "status_code", "args"):
        if hasattr(e, attr):
            print(f"--- {attr} ---")
            print(getattr(e, attr))