import requests
import json

BOT_TOKEN = "8656535426:AAFYaltJCkLqukMNzRoJEEhr8w_X7Kzn0nk"
AUTHORIZED_CHAT_ID = "1208823196"

url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
response = requests.get(url, params={"timeout": 5}, timeout=10).json()

print("\n=== RAW TELEGRAM RESPONSE ===")
print(json.dumps(response, indent=2))

print("\n=== PARSED MESSAGE DETAILS ===")
if response.get("ok") and response.get("result"):
    for update in response["result"]:
        print(f"\n--- update_id: {update['update_id']} ---")
        
        msg = update.get("message")
        chan = update.get("channel_post")
        active = msg or chan
        kind = "message" if msg else "channel_post"
        
        if active:
            chat_id = str(active.get("chat", {}).get("id", "MISSING"))
            text    = active.get("text", "[no text]")
            
            print(f"  Kind     : {kind}")
            print(f"  chat_id  : {chat_id}")
            print(f"  text     : {text!r}")
            print(f"  Ends !!! : {text.strip().endswith('!!!!')}")
            print(f"  Auth OK  : {chat_id == AUTHORIZED_CHAT_ID}")
        else:
            print(f"  (no message or channel_post key) keys={list(update.keys())}")
else:
    print("No updates found or API error.")
    print(response)
