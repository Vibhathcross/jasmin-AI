"""
Standalone Telegram Live Test - ASCII only, no emojis
"""
import requests, time, sys

# Force UTF-8 output
sys.stdout.reconfigure(encoding='utf-8')

BOT_TOKEN     = "8656535426:AAFYaltJCkLqukMNzRoJEEhr8w_X7Kzn0nk"
AUTHORIZED_ID = "1208823196"
URL           = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

print("=" * 60)
print("  TELEGRAM LIVE DIAGNOSTIC  (60 second window)")
print("  >> Make sure Jasmin is NOT running")
print("  >> Send ANY message to your bot now")
print("  >> Then send one ending with '!!!!'")
print("=" * 60)

# Step 1: Flush stale messages
print("\n[1] Flushing old updates...")
flush = requests.get(URL, params={"timeout": 0}, timeout=8).json()
if flush.get("ok") and flush.get("result"):
    last_id = flush["result"][-1]["update_id"]
    print(f"    Flushed {len(flush['result'])} old update(s). Starting from ID {last_id + 1}")
else:
    last_id = None
    print("    No stale updates. Starting fresh.")

print(f"\n[2] Polling for 60 seconds... SEND YOUR MESSAGE NOW\n")

deadline   = time.time() + 60
poll_count = 0

while time.time() < deadline:
    poll_count += 1
    remaining  = int(deadline - time.time())

    params = {}
    if last_id is not None:
        params["offset"] = last_id + 1

    try:
        resp    = requests.get(URL, params=params, timeout=8).json()
        updates = resp.get("result", [])

        if not resp.get("ok"):
            print(f"[Poll #{poll_count}] API Error: {resp.get('description')}")
            time.sleep(5)
            continue

        if updates:
            for u in updates:
                last_id   = u["update_id"]
                msg       = u.get("message") or u.get("channel_post") or {}
                text      = msg.get("text", "")
                chat      = msg.get("chat", {})
                chat_id   = str(chat.get("id", "MISSING"))
                chat_type = chat.get("type", "?")
                username  = chat.get("username", chat.get("first_name", "?"))

                print("\n" + "=" * 50)
                print("  [MESSAGE RECEIVED]")
                print(f"  update_id  : {u['update_id']}")
                print(f"  chat_id    : {chat_id}")
                print(f"  chat_type  : {chat_type}")
                print(f"  username   : {username}")
                print(f"  text       : {repr(text)}")
                print(f"  ends !!!! : {text.strip().endswith('!!!!')}")
                print(f"  auth match : {chat_id == AUTHORIZED_ID}  (expected: {AUTHORIZED_ID})")
                if chat_id != AUTHORIZED_ID:
                    print(f"")
                    print(f"  *** MISMATCH DETECTED ***")
                    print(f"  Update config.py -> AUTHORIZED_CHAT_ID = \"{chat_id}\"")
                print("=" * 50)
        else:
            print(f"  [{remaining}s left] Waiting... (poll #{poll_count})", end="\r")

    except Exception as e:
        print(f"[Poll #{poll_count}] Exception: {e}")

    time.sleep(3)

print(f"\n\n[Done] {poll_count} polls completed.")
