import json
import os

target = os.path.expandvars(
    r"%APPDATA%\Code\User\workspaceStorage\16f108da9f3942021e28a1fb63ea1b05\GitHub.copilot-chat\transcripts\ed3eea0a-a553-4d02-8429-87aaaa5c4dbc.jsonl"
)

found_next = False
count = 0
with open(target, encoding="utf-8") as f:
    for idx, line in enumerate(f):
        try:
            data = json.loads(line)
            if data.get("type") == "user.message":
                text = data.get("data", {}).get("content", "")
                if "categorized it into" in text:
                    print(f"User message at line {idx}")
                    found_next = True
                    continue
            if found_next and data.get("type") == "assistant.message":
                content = data.get("data", {}).get("content", "")
                if content:
                    print(f"Assistant response at line {idx}:")
                    print(content)
                    count += 1
                    if count >= 2:
                        break
        except Exception:
            pass
