import os
import json
import dropbox
from dotenv import load_dotenv

load_dotenv("G:/2개인작업/11_AI스터디/안티그래비티/Law_Agent_v2.0/.env", override=True)
DBX_TOKEN = os.environ.get("DROPBOX_ACCESS_TOKEN", "")

if not DBX_TOKEN:
    print("Dropbox token not found!")
    exit(1)

dbx = dropbox.Dropbox(DBX_TOKEN)
v1_cases_dir = "G:/2개인작업/11_AI스터디/안티그래비티/Law_Agent_v1.1/cases"

for folder_name in os.listdir(v1_cases_dir):
    folder_path = os.path.join(v1_cases_dir, folder_name)
    if os.path.isdir(folder_path):
        history_file = os.path.join(folder_path, "history.json")
        if os.path.exists(history_file):
            print(f"Uploading history.json for {folder_name}...")
            dropbox_path = f"/{folder_name}/history.json"
            
            # 먼저 폴더가 없으면 생성 (에러 무시)
            try:
                dbx.files_create_folder_v2(f"/{folder_name}")
            except Exception:
                pass
            
            with open(history_file, 'rb') as f:
                data = f.read()
                try:
                    dbx.files_upload(data, dropbox_path, mode=dropbox.files.WriteMode("overwrite"))
                    print(f"  -> Success: {dropbox_path}")
                except Exception as e:
                    print(f"  -> Failed: {e}")

print("Migration completed.")
