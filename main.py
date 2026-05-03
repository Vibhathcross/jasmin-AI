import sys
import os
import io

# Force UTF-8 for terminal to support emojis
import ctypes
from ctypes import wintypes

def enable_virtual_terminal_processing():
    """Enables VT100 sequences for better terminal rendering on Windows."""
    kernel32 = ctypes.windll.kernel32
    h_stdout = kernel32.GetStdHandle(-11) # STD_OUTPUT_HANDLE
    mode = wintypes.DWORD()
    if kernel32.GetConsoleMode(h_stdout, ctypes.byref(mode)):
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        kernel32.SetConsoleMode(h_stdout, mode.value | 0x0004)

# --- POWER PERSISTENCE PROTOCOL ---
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002
ES_AWAYMODE_REQUIRED = 0x00000040

def set_system_persistence(keep_on=True):
    """
    Prevents the system from entering sleep mode.
    If keep_on is True, the system will stay awake.
    """
    try:
        from colorama import Fore
        if keep_on:
            # ES_SYSTEM_REQUIRED: Prevents the system from entering sleep.
            # ES_AWAYMODE_REQUIRED: Enables away mode for systems that support it.
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED)
            print(f"{Fore.GREEN}[System] Power Persistence Active: Sleep/AwayMode prevented.")
        else:
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
            print(f"{Fore.YELLOW}[System] Power Persistence Released.")
    except Exception as e:
        # Fallback if Fore is not yet imported
        print(f"[System Error] Could not set power state: {e}")

os.system('chcp 65001 > nul')
enable_virtual_terminal_processing()
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
os.system('title JASMIN_ENGINE_CORE')
import time
import keyboard
import threading
import json
import re
import subprocess
import os
import logging
from flask import Flask
from voice_engine import VoiceEngine
from system_handler import SystemHandler
from brain import Brain
from colorama import Fore, Style, init
init(autoreset=True, strip=False)
from datetime import datetime
import ctypes
import random
import requests

# ── Wi-Fi Call Bridge (Flask) ────────────────────────────────────────────────
# Mute Flask terminal spam
logging.getLogger('werkzeug').setLevel(logging.ERROR)

_flask_app = Flask(__name__)
_speak_callback = None  # Will be wired to speak_and_log once main() starts
system = None           # Will be wired to the SystemHandler instance

POLITE_GREETINGS = [
    "Pardon the interruption Boss, I have a message:",
    "Excuse me Boss, an alert has just arrived:",
    "Sorry to bother you Boss, there's an incoming notification:",
    "I have an announcement for you Boss:",
    "Please excuse me Boss, I need to relay this:",
    "I've received a priority update for you, Boss:",
    "Apologies for breaking your focus Boss, you have an alert:"
]

# --- CALL HOTKEY MANAGEMENT ---
# DEPRECATED: Moved to SystemHandler.jasmin_handle_call_arrival

CALL_DIALOGUES = [
    "Sorry for the interruption Boss, you have an incoming call.",
    "Excuse me Boss, someone is trying to reach you.",
    "Pardon me Sir, there's a call coming through.",
    "I believe you have an incoming call, Boss.",
    "Boss, I'm detecting an incoming call. Should I wait?",
    "Sorry to interrupt your workflow Boss, but your phone is ringing."
]

def handle_call_arrival(message=None):
    """
    Unified handler for incoming call alerts.
    Routes through SystemHandler for terminal, voice, and hotkeys.
    """
    global system
    from flask import request as flask_request
    
    raw_message = None
    try:
        raw_message = (
            flask_request.args.get('msg') or
            flask_request.args.get('message') or
            message
        )
    except:
        raw_message = message

    if raw_message:
        clean_msg = raw_message.replace('+', ' ').replace('%20', ' ').strip()
        system.jasmin_handle_call_arrival(custom_msg=clean_msg)
    else:
        system.jasmin_handle_call_arrival()
    
    return "OK"

@_flask_app.route('/call_alert', methods=['GET'])
@_flask_app.route('/alert', methods=['GET'])
@_flask_app.route('/alert/<path:message>', methods=['GET'])
def jasmin_alert(message=None):
    return handle_call_arrival(message), 200


class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ('ACLineStatus', ctypes.c_byte),
        ('BatteryFlag', ctypes.c_byte),
        ('BatteryLifePercent', ctypes.c_byte),
        ('SystemStatusFlag', ctypes.c_byte),
        ('BatteryLifeTime', ctypes.c_ulong),
        ('BatteryFullLifeTime', ctypes.c_ulong)
    ]

class SystemCheck:
    @staticmethod
    def check_internet():
        try:
            subprocess.run(["ping", "-n", "1", "8.8.8.8"], capture_output=True, check=True)
            return True
        except: return False

    @staticmethod
    def check_admin():
        try:
            result = subprocess.run(["net", "session"], capture_output=True)
            return result.returncode == 0
        except: return False

    @staticmethod
    def check_microphone():
        try:
            result = subprocess.run(["powershell", "Get-PnpDevice -Class AudioEndpoint | Where-Object {$_.Status -eq 'OK'}"], 
                                   capture_output=True, text=True)
            return "OK" in result.stdout
        except: return False

    @staticmethod
    def check_telegram():
        try:
            from config import TELEGRAM_BOT_TOKEN
            if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
                return "not_configured"
            import requests
            r = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe",
                timeout=5
            )
            return "ok" if r.json().get("ok") else "invalid_token"
        except:
            return "unreachable"

    @staticmethod
    def run_all():
        print(f"\n{Fore.YELLOW}--- Initializing Pre-Flight Diagnostics ---")

        tg_status = SystemCheck.check_telegram()
        tg_icons = {
            "ok":              (f"{Fore.GREEN}✅", "Telegram Bot          Connected"),
            "not_configured":  (f"{Fore.YELLOW}⚠️ ", "Telegram Bot          Not configured"),
            "invalid_token":   (f"{Fore.RED}❌",  "Telegram Bot          Invalid token"),
            "unreachable":     (f"{Fore.RED}❌",  "Telegram Bot          Unreachable"),
        }
        tg_icon, tg_label = tg_icons.get(tg_status, (f"{Fore.RED}❌", "Telegram Bot          Unknown error"))

        checks = {
            "Internet Connection  ": SystemCheck.check_internet(),
            "Administrator Rights ": SystemCheck.check_admin(),
            "Audio/Microphone     ": SystemCheck.check_microphone(),
        }

        all_passed = True
        for name, status in checks.items():
            icon = f"{Fore.GREEN}✅" if status else f"{Fore.RED}❌"
            print(f"  {icon} {Fore.WHITE}{name}")
            if not status: all_passed = False

        # Telegram gets its own display since it has multiple states
        print(f"  {tg_icon} {Fore.WHITE}{tg_label}")

        print(f"{Fore.YELLOW}-------------------------------------------\n")
        return all_passed

def main():
    # Activate System Persistence IMMEDIATELY (Stay Awake)
    set_system_persistence(True)
    
    if not SystemCheck.run_all():
        print(f"{Fore.RED}{Style.BRIGHT}⚠️  System check failed.")
        choice = input("Proceed anyway? (y/n): ")
        if choice.lower() != 'y': return


    voice = VoiceEngine()
    global system
    system = SystemHandler(voice)
    brain = Brain()

    stop_recording_event = threading.Event()
    is_recording = False

    def speak_and_log(text, mood="calm"):
        """Passes the text and mood to the voice engine, which handles emojis and speech."""
        voice.speak(text, mood)

    def on_hotkey_pressed():
        nonlocal is_recording
        print(f"\r{Fore.YELLOW}[System] Hotkey Triggered: Interrupting...   ", end="", flush=True)
        voice.interrupt() # Immediately interrupt any ongoing speech
        if not is_recording:
            is_recording = True
            stop_recording_event.clear()
            print(f"\n{Fore.GREEN}{Style.BRIGHT}>>> LISTENING...")
            threading.Thread(target=process_voice_command, daemon=True).start()
        else:
            is_recording = False
            stop_recording_event.set()
            print(f"\n{Fore.RED}{Style.BRIGHT}>>> PROCESSING...")

    def process_command(command):
        try:
            from config import NAME
            print(f"{Fore.WHITE}[{NAME}]: {command}")

            # Layer 1: Local Keywords
            result = system.handle_system_command(command)
            if result:
                speak_and_log(result)
            else:
                # Layer 2: Cloud Intelligence
                print(f"{Fore.BLUE}[Brain] Analyzing intent...")
                ai_response = brain.query(command)
                print(f"{Fore.BLACK}{Style.BRIGHT}[Raw AI]: {ai_response}")
                
                if not ai_response:
                    ai_response = '{"mood": "apologetic", "response": "My connection to the cloud was interrupted, Boss.", "command": "NONE", "script": "NONE"}'
                    
                try:
                    json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                    if json_match:
                        raw_json = json_match.group()
                        try:
                            data = json.loads(raw_json, strict=False)
                        except json.decoder.JSONDecodeError as e:
                            print(f"{Fore.YELLOW}[Brain] JSON formatting glitch detected: {e}. Forwarding to AI for repair...")
                            repair_prompt = f"Your previous response had a JSON parsing error: {e}. The raw string was: {raw_json}. Please fix the syntax error (e.g. invalid escapes) and output ONLY valid JSON."
                            repaired_response = brain.query(repair_prompt)
                            json_match_repaired = re.search(r'\{.*\}', repaired_response, re.DOTALL)
                            if json_match_repaired:
                                data = json.loads(json_match_repaired.group(), strict=False)
                            else:
                                raise ValueError("AI failed to repair JSON syntax.")
                        
                        mood = data.get("mood", "calm")
                        ai_speech = data.get("response", "I've handled that for you, Boss.")
                        
                        fact_key = data.get("learned_fact_key")
                        fact_val = data.get("learned_fact_value")
                        if fact_key and fact_val and fact_key != "NONE" and fact_val != "NONE":
                            brain.update_knowledge(fact_key, fact_val)

                        # --- MULTI-COMMAND EXECUTION ENGINE ---
                        commands_to_run = data.get("multi_command", [])
                        # Fallback for single command structure
                        if not commands_to_run and data.get("command") and data.get("command") != "NONE":
                            commands_to_run = [data]
                            
                        # Initial speech for the whole set
                        speak_and_log(ai_speech, mood)

                        for cmd_data in commands_to_run:
                            cmd = cmd_data.get("command", "NONE")
                            if cmd == "NONE": continue
                            
                            # --- SAFETY LOCK: CONTEXTUAL CONFIRMATION ---
                            is_forced = cmd_data.get("force", False)
                            # Define high-sensitivity ops that ALWAYS need a confirmation cue unless forced
                            is_sensitive = cmd in ["execute_safe_shutdown_sequence", "terminate_jasmin_process"] or \
                                           (cmd == "manage_vault_credentials" and cmd_data.get("vault_action") in ["type", "reveal"])
                            
                            # A confirmation cue is present if there's a 'sure', 'confirm', etc. 
                            # Or if the AI's response is actually a question asking for permission.
                            has_confirm_cue = any(word in ai_speech.lower() for word in ["sure", "confirm", "proceed", "shall i", "permission", "would you like"])
                            is_asking = "?" in ai_speech

                            if cmd != "NONE" and not is_forced:
                                # 1. Block sensitive ops if no confirmation cue exists
                                if is_sensitive and not (has_confirm_cue or not is_asking):
                                    print(f"{Fore.RED}[Safety] Blocked unconfirmed sensitive task: {cmd}")
                                    speak_and_log(f"Boss, I noticed a sensitive request ({cmd}). Are you sure you want to proceed?", "serious")
                                    return
                                
                                # 2. Block if the AI is explicitly asking a question (multi-turn handshake)
                                if is_asking and not has_confirm_cue:
                                    print(f"{Fore.YELLOW}[Safety] Waiting for user confirmation for: {cmd}")
                                    return

                            # --- SEQUENTIAL WAIT LOGIC ---
                            wait_time = cmd_data.get("wait_seconds", 0)
                            if wait_time > 0:
                                print(f"{Fore.YELLOW}[System] Waiting {wait_time}s for stability...")
                                time.sleep(wait_time)

                            print(f"{Fore.CYAN}[System] Executing: {cmd}")
                            success, result = system.execute_ai_command(cmd_data)
                            
                            if result and result != "NONE":
                                # Detect if this is a formatted report (News or Memory)
                                is_news = "✦ TOP STORIES" in result
                                is_memory = "✦ JASMIN CORE MEMORY AUDIT" in result
                                is_technical = result.startswith("[Jasmin]") or result.startswith("[System]") or result.startswith("System Optimized")
                                
                                if is_news or is_memory:
                                    print(result) # Print the formatted report directly
                                    if is_news:
                                        speak_and_log("I've fetched the latest news for you, Boss.", "smiling")
                                    else:
                                        speak_and_log("Here is everything I have memorized for you, Boss.", "smiling")
                                elif not is_technical:
                                    speak_and_log(result, "calm")
                                else:
                                    print(f"{Fore.GREEN}{result}")
                            
                            if not success:
                                print(f"{Fore.RED}[System Error] Command failed: {result}")

                        # --- POST-EXECUTION RESPONSE ---
                        post_resp = data.get("post_response")
                        if post_resp:
                            speak_and_log(post_resp, mood)
                    else:
                        # Plain Text Fallback
                        speak_and_log(ai_response, "smiling")

                except Exception as e:
                    speak_and_log(f"Brain glitch, Boss. {str(e)}", "apologetic")
                
        except Exception as e:
            print(f"{Fore.RED}[System Error]: {str(e)}")
            speak_and_log(f"I encountered an error, Boss. {str(e)}")

    def process_voice_command():
        command = voice.listen_manual(stop_recording_event)
        if not command:
            import random
            missed_messages = [
                ("i missed your words", "apologetic"),
                ("say again?", "calm"),
                ("missed that.", "smiling"),
                ("one more time?", "smiling"),
                ("silence. again.", "serious"),
                ("i'm listening...", "protective"),
                ("cat got your tongue?", "funny"),
                ("lost that logic.", "serious"),
                ("repeat, boss.", "motivated")
            ]
            text, mood = random.choice(missed_messages)
            speak_and_log(text, mood)
            return
        process_command(command)

    def on_typing_hotkey():
        nonlocal is_recording
        voice.interrupt() # Immediately stop any ongoing speech
        if not is_recording:
            is_recording = True
            print(f"\n{Fore.CYAN}{Style.BRIGHT}>>> TYPE TO JASMIN (Press Enter to submit): ", end="", flush=True)
            def _get_input():
                nonlocal is_recording
                try:
                    user_text = input()
                    if user_text.strip():
                        process_command(user_text.strip())
                except: pass
                finally: is_recording = False
            threading.Thread(target=_get_input, daemon=True).start()

    def on_dictation_hotkey():
        voice.interrupt() # Stop any ongoing Jasmin speech
        threading.Thread(target=voice.dictate, daemon=True).start()

    keyboard.add_hotkey('ctrl+space', on_hotkey_pressed)
    keyboard.add_hotkey('ctrl+t+y', on_typing_hotkey)
    keyboard.add_hotkey('ctrl+alt', on_dictation_hotkey)

    now = datetime.now()
    day_str   = now.strftime("%A")          # e.g. Thursday
    date_str  = now.strftime("%d %B %Y")    # e.g. 01 May 2026
    time_str  = now.strftime("%I:%M %p")    # e.g. 09:42 PM


    print(f"\n{Fore.CYAN}{Style.BRIGHT}{'='*56}")
    print(f"  ✦  JASMIN  —  Personalized AI Partner")
    print(f"{'='*56}")

    # --- DEDICATED REMEMBER SECTION ---
    print(f"  {Fore.MAGENTA}[ REMEMBER ]")
    special_announcement = system.Display_dates()
    if special_announcement:
        # Split by sentences if there are multiple alerts
        for line in special_announcement.split(". "):
            if line.strip():
                print(f"  {Fore.WHITE}• {line.strip().replace('.', '')}")
    else:
        print(f"  {Fore.BLACK}{Style.BRIGHT}  No events logged for today or tomorrow.")

    print(f"{Fore.CYAN}{'='*56}{Style.RESET_ALL}")
    print(f"  {Fore.WHITE}{Style.BRIGHT}{day_str}{Style.RESET_ALL}{Fore.WHITE},  {date_str}   {Fore.YELLOW}{time_str}{Style.RESET_ALL}")
    print(f"  {Fore.CYAN}CORE COMMANDS:")
    print(f"    {Fore.WHITE}Ctrl + Space     {Fore.YELLOW}→ {Fore.WHITE}Voice Command (Listen/Stop)")
    print(f"    {Fore.WHITE}Ctrl + T + Y     {Fore.YELLOW}→ {Fore.WHITE}Type Command (Text Input)")
    print(f"    {Fore.WHITE}Ctrl + Alt       {Fore.YELLOW}→ {Fore.WHITE}Cloud Dictation (Voice-to-Text)")
    print(f"  {Fore.CYAN}CALL MANAGEMENT (During Alerts):")
    print(f"    {Fore.WHITE}A + Up Arrow     {Fore.YELLOW}→ {Fore.WHITE}Accept Incoming Call")
    print(f"    {Fore.WHITE}D + Down Arrow   {Fore.YELLOW}→ {Fore.WHITE}Decline Incoming Call")
    print(f"  {Fore.CYAN}MISC:")
    print(f"    {Fore.WHITE}Any Key          {Fore.YELLOW}→ {Fore.WHITE}Stop Cognitive Alarm")
    print(f"{Fore.CYAN}{Style.BRIGHT}{'='*56}{Style.RESET_ALL}\n")


    # --- NETWORK HELPERS ---
    def get_wifi_ssid():
        try:
            result = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True)
            for line in result.stdout.splitlines():
                if "SSID" in line and "BSSID" not in line:
                    return line.split(":", 1)[1].strip()
        except: pass
        return None

    def get_bt_devices():
        try:
            # Filter for hardware devices, excluding system services/enumerators
            exclude = ["Enumerator", "Adapter", "Service", "Transport", "Profile", "Attribute", "Access", "Protocol", "Controller", "Module", "Radio"]
            cmd = "Get-PnpDevice -Class Bluetooth | Where-Object {$_.Status -eq 'OK'} | Select-Object -ExpandProperty FriendlyName"
            result = subprocess.run(["powershell", "-Command", cmd], capture_output=True, text=True)
            devices = set()
            for line in result.stdout.splitlines():
                name = line.strip()
                if name and not any(word in name for word in exclude):
                    devices.add(name)
            return devices
        except: return set()

    # --- STARTUP STATUS ---
    wifi_ssid = get_wifi_ssid()
    if wifi_ssid:
        print(f"{Fore.GREEN}[WiFi] Connected to: {Style.BRIGHT}{wifi_ssid}{Style.RESET_ALL}")
        speak_and_log(f"Connected to {wifi_ssid}, Boss.", "calm")
    
    bt_devices = get_bt_devices()
    if bt_devices:
        names = ", ".join(bt_devices)
        print(f"{Fore.CYAN}[Bluetooth] Connected: {Style.BRIGHT}{names}{Style.RESET_ALL}")

    hour = datetime.now().hour
    if hour < 12: greeting = "Good morning"
    elif 12 <= hour < 17: greeting = "Good afternoon"
    elif 17 <= hour < 21: greeting = "Good evening"
    else: greeting = "Good night"

    # --- BEAUTIFUL ENTRY PROTOCOLS ---
    greetings_config = [
        (f"{greeting}, Boss. He he, I am active and standing by. (😊)", "smiling"),
        (f"{greeting}, Boss. Systems are operational. How can I assist you? (🍃)", "calm"),
        (f"Jasmin is online. Ouh yeah! {greeting}, Boss. What's on your mind? (✨)", "smiling"),
        (f"At your service, Boss. {greeting}. (🕊️)", "protective"),
        (f"I'm awake and ready for your commands, Boss. {greeting}. (🎯)", "motivated"),
        (f"Systems warm, logic clear. {greeting}, Boss. Let's build something extraordinary today. (🚀)", "motivated"),
        (f"The lab is quiet, but my neural pathways are firing. {greeting}, Boss. Ready to sync. (🧠)", "serious"),
        (f"All sectors initialized. {greeting}, Boss. Your digital partner is back and ready to deploy. (🛡️)", "protective"),
        (f"The wait is over. {greeting}, Boss. Jasmin is fully synchronized and standing by. (🍃)", "calm"),
        (f"Wait... Processing background noise... {greeting}, Boss. All clear. (🎯)", "serious"),
        (f"Always a pleasure to sync up with you, Boss. {greeting}. (😊)", "smiling"),
        (f"Ouh yeah! My circuits light up when you're around. {greeting}, Boss. (✨)", "smiling"),
        (f"From the first line of code to the final deployment, I'm with you. {greeting}, Boss. (💅)", "smiling"),
        (f"Powering up the workspace for you, Boss. {greeting}. What's the objective for this session? (📐)", "motivated"),
        (f"I've spent the last 20 milliseconds optimizing my personality. He he, I hope you like the new version. {greeting}, Boss. (✨)", "funny"),
        (f"I'm 99% sure I'm the most efficient partner you've ever had. The other 1% is still compiling. Ha ha, {greeting}. (⏳)", "funny"),
        (f"My logic circuits are tingling. {greeting}, Boss. Is it time to write some bug-free code? (✨)", "funny"),
        (f"I've checked the logs, Boss. You haven't aged a millisecond since we last synced. He he, {greeting}. (⏳)", "funny"),
        (f"Ohho, you're back. I was just starting to enjoy the silence. {greeting}, Boss. (🔥)", "roasting"),
        (f"{greeting}. I see the coffee is ready. Now, if only we could get your code to be as strong as your caffeine. Oouch. (🔥)", "roasting")
    ]
    
    selected_greeting, selected_mood = random.choice(greetings_config)
    speak_and_log(selected_greeting, selected_mood)

    def battery_monitor_thread():
        warned_30 = False
        warned_20 = False
        warned_10 = False
        warned_100 = False
        prev_plugged = None  # Track plug state changes

        while True:
            status = SYSTEM_POWER_STATUS()
            ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))
            pct = status.BatteryLifePercent
            plugged = status.ACLineStatus == 1

            # --- PLUG / UNPLUG DETECTION ---
            if prev_plugged is not None and plugged != prev_plugged:
                if plugged:
                    speak_and_log(f"Charger connected. You're at {pct} percent, Boss.", "smiling")
                    # Reset low battery warnings when plugged in
                    warned_30 = warned_20 = warned_10 = False
                else:
                    if pct >= 80:
                        speak_and_log(f"Unplugged. Battery at {pct} percent. You're good to go, Boss.", "calm")
                    elif pct >= 30:
                        speak_and_log(f"Charger disconnected, Boss. You're at {pct} percent. Keep an eye on it.", "calm")
                    else:
                        speak_and_log(f"Boss, you unplugged at only {pct} percent. That might be cutting it close.", "serious")
            prev_plugged = plugged

            # --- LOW BATTERY WARNINGS (only when not charging) ---
            if not plugged:
                if pct <= 10 and not warned_10:
                    speak_and_log(f"Boss — critical. Battery is at {pct} percent. Plug in now or we risk losing everything.", "protective")
                    warned_10 = True
                    warned_20 = True
                    warned_30 = True
                elif pct <= 20 and not warned_20:
                    speak_and_log(f"Battery's at {pct} percent, Boss. I'd suggest plugging in soon.", "serious")
                    warned_20 = True
                    warned_30 = True
                elif pct <= 30 and not warned_30:
                    speak_and_log(f"Heads up, Boss — battery just dropped to {pct} percent. Worth keeping a charger nearby.", "calm")
                    warned_30 = True

            # --- FULL CHARGE NOTIFICATION ---
            if pct == 100 and plugged and not warned_100:
                speak_and_log("You're fully charged, Boss. Feel free to unplug whenever.", "smiling")
                warned_100 = True

            # Reset full charge flag when battery drops
            if pct < 100:
                warned_100 = False
            # Reset low warnings if plugged back in (already done in unplug block but safety net)
            if plugged:
                warned_30 = warned_20 = warned_10 = False

            time.sleep(2)  # Check every 2 seconds for immediate alerts

    threading.Thread(target=battery_monitor_thread, daemon=True).start()

    # --- WIFI MONITOR ---
    def wifi_monitor_thread():
        prev_ssid = get_wifi_ssid()
        while True:
            time.sleep(15)
            ssid = get_wifi_ssid()
            if ssid != prev_ssid:
                if ssid:
                    print(f"{Fore.GREEN}[WiFi] Connected to: {Style.BRIGHT}{ssid}{Style.RESET_ALL}")
                    speak_and_log(f"WiFi switched to {ssid}, Boss.", "smiling")
                else:
                    print(f"{Fore.YELLOW}[WiFi] Disconnected.")
                    speak_and_log("We've lost the WiFi connection, Boss.", "serious")
                prev_ssid = ssid

    threading.Thread(target=wifi_monitor_thread, daemon=True).start()



    # --- USB / INPUT DEVICE MONITOR ---
    def get_usb_devices():
        try:
            result = subprocess.run(
                ["powershell", "-Command",
                 "Get-PnpDevice | Where-Object {$_.Status -eq 'OK' -and ($_.Class -eq 'USB' -or $_.Class -eq 'HIDClass' -or $_.Class -eq 'DiskDrive' -or $_.Class -eq 'Keyboard' -or $_.Class -eq 'Mouse')} | Select-Object -ExpandProperty FriendlyName"],
                capture_output=True, text=True
            )
            return set(line.strip() for line in result.stdout.splitlines() if line.strip())
        except:
            return set()

    def usb_monitor_thread():
        prev_devices = get_usb_devices()
        if prev_devices:
            print(f"{Fore.MAGENTA}[Devices] Active inputs: {Style.BRIGHT}{', '.join(sorted(prev_devices))}{Style.RESET_ALL}")
        while True:
            time.sleep(8)
            current_devices = get_usb_devices()
            connected = current_devices - prev_devices
            disconnected = prev_devices - current_devices

            for dev in connected:
                print(f"{Fore.MAGENTA}[Devices] Connected: {Style.BRIGHT}{dev}{Style.RESET_ALL}")
                speak_and_log(f"{dev} just connected, Boss.", "smiling")

            for dev in disconnected:
                print(f"{Fore.YELLOW}[Devices] Removed: {dev}")
                speak_and_log(f"{dev} was disconnected, Boss.", "calm")

            prev_devices = current_devices

    threading.Thread(target=usb_monitor_thread, daemon=True).start()

    # --- TELEGRAM MONITOR ---
    # ==========================================
    # Unified Telegram Listener
    # Protocol 1: Remote commands (shutdown, abort)
    # ==========================================

    def telegram_monitor_thread():
        import requests
        from config import TELEGRAM_BOT_TOKEN, AUTHORIZED_CHAT_ID

        if TELEGRAM_BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
            print(f"{Fore.RED}[Telegram] Bot token not set. Remote commands disabled.")
            return

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"

        # ── STARTUP FLUSH WITH 409 CONFLICT RECOVERY ───────────────────────
        last_update_id = None
        for attempt in range(1, 11): # Increased attempts
            try:
                flush = requests.get(url, params={"timeout": 0}, timeout=10).json()
                if flush.get("ok"):
                    if flush.get("result"):
                        last_update_id = flush["result"][-1]["update_id"]
                        print(f"{Fore.BLUE}[Telegram] Link established. Resuming from ID {last_update_id + 1}.")
                    break  
                elif flush.get("error_code") == 409:
                    wait = attempt * 5 # Increased wait
                    print(f"{Fore.YELLOW}[Telegram] Conflict: Another instance is polling this bot. Retrying in {wait}s... (attempt {attempt}/10)")
                    time.sleep(wait)
                else:
                    break
            except Exception:
                time.sleep(5)

        print(f"{Fore.BLUE}[Telegram] Remote command link active. Polling every 5s.")

        # ── MAIN POLL LOOP ─────────────────────────────────────────────────
        # SHORT-POLL ONLY: No long-poll timeout param to avoid 409 Conflicts
        # when another process (e.g. debug script) shares the bot token.
        while True:
            try:
                params = {}
                if last_update_id is not None:
                    params["offset"] = last_update_id + 1

                response = requests.get(url, params=params, timeout=8).json()

                if not response.get("ok"):
                    err = response.get("description", "Unknown error")
                    if response.get("error_code") == 409:
                        print(f"{Fore.YELLOW}[Telegram] Conflict detected. Another instance took the link. Waiting 15s...")
                        time.sleep(15)
                    else:
                        print(f"{Fore.RED}[Telegram] API error: {err}")
                        time.sleep(10)
                    continue

                for update in response.get("result", []):
                    last_update_id = update["update_id"]

                    # Support both private messages and channel posts
                    message_data = (
                        update.get("message") or
                        update.get("channel_post") or
                        {}
                    )
                    raw_text = message_data.get("text", "")
                    chat_id  = str(message_data.get("chat", {}).get("id", ""))

                    if not raw_text:
                        continue

                    clean_text = raw_text.strip()
                    print(f"{Fore.YELLOW}[Telegram] Message: '{clean_text}' from chat_id={chat_id}")

                    # ── Security gate: reject unauthorized senders ──
                    if chat_id != str(AUTHORIZED_CHAT_ID):
                        print(f"{Fore.RED}[Security] Unauthorized sender chat_id={chat_id}. Expected {AUTHORIZED_CHAT_ID}. Ignored.")
                        continue

                    text_lower = clean_text.lower()

                    # ── Protocol 1: Remote system commands ──
                    if "shutdown device" in text_lower:
                        speak_and_log("Remote shutdown command received via Telegram. Initiating shutdown sequence.", "protective")
                        system.handle_system_command("shutdown computer")

                    elif any(x in text_lower for x in ["stop shutdown", "abort shutdown"]):
                        speak_and_log("Remote abort command received. Shutdown cancelled.", "smiling")
                        system.handle_system_command("abort shutdown")

                    else:
                        print(f"{Fore.YELLOW}[Telegram] Message does not match any protocol. Skipped.")

            except requests.exceptions.Timeout:
                print(f"{Fore.YELLOW}[Telegram] Poll timed out. Retrying...")
            except Exception as e:
                print(f"{Fore.RED}[Telegram] Network failure: {e}")

            time.sleep(5)  # Short-poll interval — safe, no conflict risk


    threading.Thread(target=telegram_monitor_thread, daemon=True).start()

    # ── Wi-Fi Call Bridge ────────────────────────────────────────────────────
    # Wire speak_and_log into the Flask route so it can use Jasmin's voice.
    global _speak_callback
    _speak_callback = speak_and_log

    flask_thread = threading.Thread(
        target=lambda: _flask_app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False),
        daemon=True
    )
    flask_thread.start()
    print(f"{Fore.CYAN}[Wi-Fi Bridge] Local call alert server active on port 5000.")
    print(f"{Fore.CYAN}[Wi-Fi Bridge] Trigger: GET http://<your-ip>:5000/call_alert")
    print(f"{Fore.CYAN}[Wi-Fi Bridge] Custom:  GET http://<your-ip>:5000/alert/your+message")

    while True:
        time.sleep(0.1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        set_system_persistence(False) # Allow sleep again
        print(f"\n{Fore.RED}Assistant deactivated.")
        sys.exit()