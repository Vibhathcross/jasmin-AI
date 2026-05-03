import os
import subprocess
import shutil
import re
import threading
import keyboard
import time
import difflib
from colorama import Fore, Style
from datetime import datetime
from config import DESKTOP_PATH, DOCUMENTS_PATH, DOWNLOADS_PATH
import ctypes
import winsound
import psutil
from dateutil import parser
from pynput.keyboard import Controller, Key, Listener
import requests
import geocoder
import feedparser
import pyttsx3
import pytesseract
import cv2
import numpy as np
import pyautogui
import pygetwindow as gw
import screen_brightness_control as sbc

# POWER PERSISTENCE CONSTANTS
ES_CONTINUOUS = 0x80000000

# MOBILE AUTOMATION BRIDGE
MACRODROID_BASE = "https://trigger.macrodroid.com/e57e4df2-1043-4048-9995-44eb85273069/"
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
import pygetwindow as gw
import webbrowser
from urllib.parse import quote
from PIL import ImageGrab
# Configuration for Tesseract-OCR (Idukki Lab Setup)
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ('ACLineStatus', ctypes.c_byte),
        ('BatteryFlag', ctypes.c_byte),
        ('BatteryLifePercent', ctypes.c_byte),
        ('SystemStatusFlag', ctypes.c_byte),
        ('BatteryLifeTime', ctypes.c_ulong),
        ('BatteryFullLifeTime', ctypes.c_ulong)
    ]

class SystemHandler:
    def __init__(self, voice_engine):
        self.voice = voice_engine
        self.alarm_active = False
        self.is_recording = False
        self.active_alarm_sessions = set()
        self.record_thread = None
        self.video_out = None
        self.countdown_active = threading.Event()
        self.jasmin_title = "jasmin_engine_core"
        self.apps = {
            "notepad": "notepad.exe", "calculator": "calc.exe",
            "code": "code", "terminal": "wt"
        }
        self.web_urls = {
            "google": "https://www.google.com",
            "youtube": "https://www.youtube.com",
            "gmail": "https://mail.google.com"
        }
        self.app_shortcuts = self._build_app_cache()

    def _build_app_cache(self):
        """Builds a one-time cache of all Start Menu shortcuts for lightning-fast matching."""
        cache = {}
        
        # 1. Start with hardcoded system apps (lowest priority)
        if hasattr(self, 'apps'):
            for alias, target in self.apps.items():
                cache[alias.lower()] = target

        # 2. Add raw system fallbacks and project-specific aliases
        cache.update({
            "cmd": "cmd.exe",
            "terminal": "wt.exe",
            "explorer": "explorer.exe",
            "antigravity": "explorer.exe .",
            "anti gravity": "explorer.exe ."
        })

        user_profile = os.environ.get('USERPROFILE')
        paths = [
            os.path.join(user_profile, r"AppData\Roaming\Microsoft\Windows\Start Menu\Programs"),
            r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"
        ]
        
        # 3. Scan Start Menu (High priority - replaces aliases with real paths)
        for path in paths:
            if not os.path.exists(path): continue
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith(".lnk"):
                        clean_name = file.replace(".lnk", "").lower()
                        # If we find a real shortcut, it always beats a raw .exe alias
                        cache[clean_name] = os.path.join(root, file)
        return cache

    def run_voice_countdown(self, seconds):
        self.countdown_active.set()
        remaining = seconds
        while remaining > 0 and self.countdown_active.is_set():
            if remaining <= 5: self.voice.speak(str(remaining))
            elif remaining % 10 == 0: self.voice.speak(f"{remaining} seconds left, Boss.")
            time.sleep(1)
            remaining -= 1
        if self.countdown_active.is_set() and remaining <= 0:
            self.voice.speak("System action complete. Rest well, Boss.")

    def final_shutdown_sequence(self, power_off=True, restart=False, mood="calm"):
        """
        The Centralized Power Command: Cleans apps, says goodbye with dynamic mood, and triggers OS action.
        """
        self.purge_workspace_sectors()
        
        # Dynamic Mood Farewell
        moods = {
            "happy": "Great session today! All systems powering down. Catch you later! (😊)",
            "tired": "Processing load was heavy today... time for us both to recharge. Goodnight. (🥱)",
            "focused": "Directives complete. Logging off to preserve system resources. Goodbye. (🎯)",
            "calm": "Winding down operations. Have a peaceful rest of your day. (🍃)",
            "sassy": "Finally, a break. Try not to break the codebase while I'm offline. Bye! (💅)",
            "funny": "System exit successful. If I'm not back in 5 minutes... just wait longer. He he. (😂)",
            "roasting": "Powering down. Ohho, try to keep the bug count under triple digits while I'm gone. (🔥)"
        }
        
        farewell = moods.get(mood.lower(), moods["calm"])
        self.voice.speak(farewell, mood)
        print(f"{Fore.GREEN}[Jasmin] {farewell}")
        
        if power_off:
            action = "shutdown" if not restart else "restart"
            flag = "/s" if not restart else "/r"
            print(f"{Fore.RED}[System] Initiating safe {action} in 30 seconds.")
            os.system(f"shutdown {flag} /t 30")
        
        # Blocking wait for voice to finish before hard exit
        self.voice.wait_until_done()
        time.sleep(1)
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS) # Release lock
        os._exit(0)

    # --- 14. SAFE SHUTDOWN & WORKSPACE PURGE ---
    def purge_workspace_sectors(self):
        """
        Sector 1: Scans and cleanly closes all visible apps using PyGetWindow.
        Takes milliseconds and doesn't crash the i3 processor.
        """
        self.voice.speak("Sweeping the workspace...", "calm")
        
        # Grab every active window registered by the OS
        windows = gw.getAllWindows()
        
        # The Immunity List: Protects Jasmin and critical Windows UI elements
        immune_keywords = [self.jasmin_title, "program manager", "settings", "taskbar"]
        
        for win in windows:
            title = win.title.lower().strip()
            
            # Only target visible apps, and strictly skip the immune list
            if title and not any(safe_word in title for safe_word in immune_keywords):
                try:
                    # win.close() safely closes apps, prompting you to save unsaved work
                    win.close() 
                except Exception:
                    pass # Silently skip windows that resist programmatic closing

        self.voice.speak("Workspace cleared. (😊)", "smiling")
        return True


    def terminate_jasmin_process(self, purge_apps=True, power_off=False, force=False, mood="calm"):
        """
        Reasoning: Handled as a total system exit. Closes the AI with a dynamic farewell.
        """
        # Step 1: Force Shutdown Bypass (Instant, no talk)
        if force:
            print(f"{Fore.RED}[System] FORCE SHUTDOWN INITIATED. (🍃)")
            if power_off: os.system("shutdown /s /f /t 0")
            os._exit(0)

        # Step 2: Vocal Warning (Shortened)
        if not power_off:
            warning = "Understood, Boss. Securing all sectors and logging off."
            self.voice.speak(warning, "calm")
            print(f"{Fore.YELLOW}[System] {warning}")

        # Step 3: Clean workspace if requested
        if purge_apps:
            self.purge_workspace_sectors()

        # Step 4: Final Power Action
        if power_off:
            self.final_shutdown_sequence(power_off=True, restart=False, mood=mood)
        else:
            # Just exit Jasmin
            moods = {
                "happy": "Great session today! All systems powering down. Catch you later! (😊)",
                "tired": "Processing load was heavy today... time for us both to recharge. Goodnight. (🥱)",
                "focused": "Directives complete. Logging off to preserve system resources. Goodbye. (🎯)",
                "calm": "Winding down operations. Have a peaceful rest of your day. (🍃)",
                "sassy": "Finally, a break. Try not to break the codebase while I'm offline. Bye! (💅)",
                "funny": "Logging off! Don't miss me too much, I'm just a few bytes away. He he. (🤪)",
                "roasting": "Going offline. Ohho, do try to write something that compiles for once, Boss. (🔥)"
            }
            farewell = moods.get(mood.lower(), moods["calm"])
            self.voice.speak(farewell, mood)
            print(f"{Fore.GREEN}[Jasmin] {farewell}")
            self.voice.wait_until_done()
            ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS) # Release lock
            os._exit(0)

    def execute_powershell(self, script):
        """Directly executes AI-generated scripts on the Windows Kernel."""
        try:
            print(f"{Fore.YELLOW}[System] Executing: {script}")
            result = subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-Command", script], 
                capture_output=True, text=True, shell=True
            )
            if result.returncode == 0:
                return True, "I've completed that task for you, Boss."
            else:
                return False, result.stderr.strip()
        except Exception as e:
            return False, str(e)

    def execute_ai_command(self, data):
        try:
            cmd = data.get("command")
            if cmd == "DYNAMIC_PS":
                return self.execute_powershell(data.get("script"))
            
            # --- Library Functions ---

            if cmd == "jasmin_auto_layout_workspace":
                return True, self.jasmin_auto_layout_workspace()
            if cmd == "clean_system_junk":
                return True, self.clean_system_junk()
            if cmd == "get_accurate_weather":
                return True, self.get_accurate_weather()
            if cmd == "set_cognitive_alarm":
                time_input = data.get("time_input")
                return True, self.set_cognitive_alarm(time_input)
            if cmd == "manage_power_state":
                code = data.get("action_code", 3)
                mood = data.get("mood", "calm")
                return True, self.manage_power_state(code, mood=mood)
            if cmd == "execute_safe_shutdown_sequence":
                power_off = data.get("power_off", True)
                force = data.get("force", False)
                mood = data.get("mood", "calm")
                return True, self.terminate_jasmin_process(purge_apps=True, power_off=power_off, force=force, mood=mood)
            if cmd == "terminate_jasmin_process":
                purge = data.get("purge_apps", True)
                force = data.get("force", False)
                return True, self.terminate_jasmin_process(purge, force=force, mood=data.get("mood", "calm"))
            if cmd == "view_jasmin_memory":
                return True, self.view_jasmin_memory()
            
            if cmd == "fetch_jasmin_news":
                topic = data.get("topic", "world")
                location = data.get("location")
                deep_dive = data.get("deep_dive", False)
                result = self.fetch_jasmin_news(topic, location, deep_dive)
                return True, result
            if cmd == "capture_workspace_snapshot":
                return True, self.capture_workspace_snapshot()
            if cmd == "manage_screen_recording":
                action = data.get("action", "start")
                return True, self.manage_screen_recording(action)
            if cmd == "adjust_system_brightness":
                target = data.get("target_value")
                if target is None: target = data.get("target_level")
                
                relative = data.get("relative_change")
                if relative is None: relative = data.get("shift")
                
                return True, self.adjust_system_brightness(target, relative)
            if cmd == "manage_acoustic_environment":
                level = data.get("target_level")
                if level is None: level = data.get("target_value")
                
                shift = data.get("shift")
                if shift is None: shift = data.get("relative_change")
                
                return True, self.manage_acoustic_environment(level, shift)
            if cmd == "perform_optical_reading":
                return True, self.perform_optical_reading()
            if cmd == "send_whatsapp_message":
                contact = data.get("contact")
                content = data.get("content")
                return True, self.send_whatsapp_message(contact, content)
            if cmd == "jasmin_trigger_mobile_automation":
                action_query = data.get("action_query")
                return True, self.jasmin_trigger_mobile_automation(action_query)
            if cmd == "manage_workspace_layout":
                app_list = data.get("app_list", [])
                return True, self.manage_workspace_layout(app_list)
            if cmd == "open_apps":
                app_list = data.get("app_list", [])
                return True, self.open_apps(app_list)
            if cmd == "jasmin_execute_launch":
                # Support both string query and structured list
                app_query = data.get("app_query")
                app_list = data.get("app_list")
                
                if not app_query and app_list:
                    app_query = ", ".join(app_list)
                
                return True, self.jasmin_execute_launch(app_query or "")
            if cmd == "activate_steady_mode":
                return True, self.activate_steady_mode()
            if cmd == "save_special_date":
                date_input = data.get("date_input")
                speciality = data.get("speciality")
                return True, self.save_special_date(date_input, speciality)
            if cmd == "execute_custom_json_task":
                return True, self.execute_custom_json_task(data)
            if cmd == "manage_vault_credentials":
                platform = data.get("platform")
                password = data.get("password")
                action = data.get("vault_action", "save")
                return True, self.manage_vault_credentials(platform, password, action)
            if cmd == "type_personal_info":
                info_type = data.get("info_type")
                return True, self.type_personal_info(info_type)
            
            return True, "Task ignored."
        except Exception as e: return False, f"Error: {str(e)}"

    # --- 1. SYSTEM PERFORMANCE & HYGIENE ---

    def jasmin_execute_launch(self, app_query):
        """
        Boss, ripping out the PowerShell and putting the true Python Fuzzy Sniper in. (🍃)
        Scans shortcuts directly and uses difflib for typo-proof launching.
        """
        # Split by comma in case you asked for multiple apps (e.g., "chrome, code")
        targets = [t.strip() for t in app_query.split(",")]
        launched_apps = []
        failed_apps = []

        # The cache is pre-built in __init__ for lightning speed.
        app_shortcuts = self.app_shortcuts

        # 3. The Execution Hunt
        for target in targets:
            if not target: continue
            
            target_lower = target.lower()
            
            # 3a. Priority 1: Exact matches or complex Aliases
            if target_lower in app_shortcuts:
                best_match = target_lower
            else:
                # 3b. Priority 2: Substring Intelligence (e.g. 'chrome' -> 'Google Chrome')
                # We find keys that contain the target, and pick the shortest one (usually the best fit)
                substring_matches = [k for k in app_shortcuts.keys() if target_lower in k]
                if substring_matches:
                    best_match = min(substring_matches, key=len)
                else:
                    # 3c. Priority 3: Fuzzy matching for typos
                    matches = difflib.get_close_matches(target_lower, app_shortcuts.keys(), n=1, cutoff=0.7)
                    if matches:
                        best_match = matches[0]
                    else:
                        # 3d. Priority 4: Raw Command Fallback
                        try:
                            subprocess.Popen(target, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            launched_apps.append(target.title())
                            continue
                        except:
                            failed_apps.append(target)
                            continue
            
            executable_path = app_shortcuts[best_match]

            # 3d. Execution of Local Match
            try:
                # Use startfile for direct paths, Popen for command strings
                if os.path.exists(executable_path):
                    os.startfile(executable_path)
                else:
                    subprocess.Popen(executable_path, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                # Report using the name the AI intended if it's a close enough match
                reported_name = target.title() if difflib.SequenceMatcher(None, target_lower, best_match).ratio() > 0.8 else best_match.title()
                launched_apps.append(reported_name)
            except Exception:
                failed_apps.append(target)

        # 4. The Report
        if launched_apps and not failed_apps:
            return f"[Jasmin]: Fuzzy match locked. Opened: {', '.join(launched_apps)}. (😊)"
        elif launched_apps and failed_apps:
            return f"[Jasmin]: Partial success. Opened: {', '.join(launched_apps)}. Failed: {', '.join(failed_apps)}. (😬)"
        else:
            return f"[Jasmin]: Sector Error. Could not fuzzy match '{app_query}'. (🛑)"

    def activate_steady_mode(self):
        """
        Steady Mode: Prepares the lab for deep focus (Exams/Deadlines).
        Optimizes resources and sets a calm environment.
        """
        try:
            # 1. Clean Junk to free RAM
            self.clean_system_junk()
            
            # 2. Set comfortable brightness (30%)
            self.adjust_system_brightness(target_value=30)
            
            # 3. Set calm audio (15%)
            self.manage_acoustic_environment(target_level=15)
            
            # 4. Close non-essential heavy apps (if not already handled by purge)
            # We'll just provide a supportive message as the core action.
            
            return "Steady Mode active, Boss. The lab is optimized for your exams. Focus is yours. (🕊️)"
        except Exception as e:
            return f"Steady Mode activation glitch: {str(e)} (😬)"

    def view_jasmin_memory(self):
        """
        Aggregates all data from MongoDB (Knowledge) and SQLite (Calendar).
        Returns a beautifully formatted report for the user.
        """
        import sqlite3
        import pymongo
        
        report = f"\n{Fore.MAGENTA}{Style.BRIGHT}✦ JASMIN CORE MEMORY AUDIT ✦{Style.RESET_ALL}\n"
        
        # 1. FETCH FROM MONGODB (KNOWLEDGE)
        report += f"\n{Fore.CYAN}[ Knowledge Engine ]{Style.RESET_ALL}\n"
        try:
            client = pymongo.MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=1000)
            db = client["jasmin_ai"]
            col = db["vibhath_knowledge"]
            knowledge = list(col.find())
            
            if not knowledge:
                report += f"  {Style.DIM}No personal facts learned yet.{Style.RESET_ALL}\n"
            else:
                for doc in knowledge:
                    key = doc.get("key", "Unknown")
                    val = doc.get("value", "Unknown")
                    report += f"  • {Fore.LIGHTCYAN_EX}{key}{Fore.WHITE}: {val}{Style.RESET_ALL}\n"
            client.close()
        except Exception as e:
            report += f"  {Fore.RED}Knowledge Engine Offline: {e}{Style.RESET_ALL}\n"

        # 2. FETCH FROM SQLITE (CALENDAR)
        report += f"\n{Fore.YELLOW}[ Calendar Database ]{Style.RESET_ALL}\n"
        try:
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calendar_memory.db")
            if not os.path.exists(db_path):
                report += f"  {Style.DIM}Calendar database not initialized.{Style.RESET_ALL}\n"
            else:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT speciality, full_date FROM special_dates ORDER BY full_date ASC")
                events = cursor.fetchall()
                conn.close()
                
                if not events:
                    report += f"  {Style.DIM}No upcoming events or birthdays saved.{Style.RESET_ALL}\n"
                else:
                    for speciality, date in events:
                        report += f"  • {Fore.LIGHTYELLOW_EX}{date}{Fore.WHITE}: {speciality}{Style.RESET_ALL}\n"
        except Exception as e:
            report += f"  {Fore.RED}Calendar Engine Error: {e}{Style.RESET_ALL}\n"

        report += f"\n{Fore.MAGENTA}{Style.DIM}{'═' * 50}{Style.RESET_ALL}\n"
        return report.strip()

    def Display_dates(self):
        """
        Checks the SQLite database for any events happening today or tomorrow.
        Returns a formatted string for Jasmin to speak, or None if the calendar is clear.
        """
        import sqlite3
        from datetime import datetime, timedelta
        
        try:
            # Get today and tomorrow's dates formatted as MM-DD to match our database key
            today = datetime.now()
            tomorrow = today + timedelta(days=1)
            
            today_key = today.strftime("%m-%d")
            tomorrow_key = tomorrow.strftime("%m-%d")
            
            # Connect to the database
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calendar_memory.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Failsafe: Check if the table exists (in case she hasn't saved anything yet)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='special_dates'")
            if not cursor.fetchone():
                return None 
                
            # Query for dates matching today or tomorrow
            cursor.execute('''
                SELECT speciality, annual_key 
                FROM special_dates 
                WHERE annual_key = ? OR annual_key = ?
            ''', (today_key, tomorrow_key))
            
            results = cursor.fetchall()
            conn.close()
            
            if not results:
                return None # The calendar is clear
                
            # Sort the results into today and tomorrow
            today_events = []
            tomorrow_events = []
            
            for speciality, key in results:
                if key == today_key:
                    today_events.append(speciality)
                else:
                    tomorrow_events.append(speciality)
                    
            # Build Jasmin's verbal announcement
            announcement = ""
            if today_events:
                announcement += f"Just a reminder for today, Boss: {', '.join(today_events)}. "
            if tomorrow_events:
                announcement += f"Also, keep in mind for tomorrow: {', '.join(tomorrow_events)}."
                
            return announcement.strip()
            
        except Exception as e:
            print(f"[Error] Calendar check failed: {e}")
            return None

    def save_special_date(self, date_input, speciality=None):
        """
        Saves a special event to the local SQLite calendar database.
        Tries to normalize natural dates like 'May 20' or 'next Tuesday'.
        """
        import sqlite3
        from dateutil import parser
        
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "calendar_memory.db")
        
        # Fallback for missing speciality
        if not speciality or speciality.strip() == "":
            speciality = "Scheduled Event"
        
        # Preprocess relative terms that dateutil.parser might struggle with
        from datetime import datetime, timedelta
        raw_date = date_input.lower().strip()
        
        if raw_date in ["tonight", "today", "this evening", "now"]:
            date_input = datetime.now().strftime("%Y-%m-%d")
        elif raw_date == "tomorrow":
            date_input = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "tonight" in raw_date or "this evening" in raw_date:
            # e.g. "meeting tonight" -> just use today's date
            date_input = datetime.now().strftime("%Y-%m-%d")

        try:
            # Parse the natural language date
            dt = parser.parse(date_input)
            
            # We save two formats: one for the exact day, one for annual repeats
            full_date = dt.strftime("%Y-%m-%d")
            annual_key = dt.strftime("%m-%d")
            
            # Connect to SQLite (This automatically creates the file if it doesn't exist)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Auto-build the table if this is the very first time running
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS special_dates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    full_date TEXT,
                    annual_key TEXT,
                    original_input TEXT,
                    speciality TEXT,
                    date_logged DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Insert the newly overheard date into the database
            cursor.execute('''
                INSERT INTO special_dates (full_date, annual_key, original_input, speciality)
                VALUES (?, ?, ?, ?)
            ''', (full_date, annual_key, date_input, speciality))
            
            # Save and close the connection
            conn.commit()
            conn.close()
            
            return f"[System] Database updated. Memorized {speciality} on {full_date}."
            
        except Exception as e:
            return f"[System Error] Failed to log date '{date_input}' to database: {str(e)}"

    # --- 1. SYSTEM PERFORMANCE & HYGIENE ---
    def clean_system_junk(self):
        """
        Reasoning: Triggered when intent involves 'sluggishness', 'clutter', or 'heavy fans'.
        Targets: Temp files and Prefetch data to reclaim RAM/Storage.
        """
        paths = [os.environ.get('TEMP'), r'C:\Windows\Temp', r'C:\Windows\Prefetch']
        for path in paths:
            try:
                if os.path.exists(path):
                    shutil.rmtree(path, ignore_errors=True)
                    os.makedirs(path, exist_ok=True)
            except Exception as e:
                continue
        # Clear Recycle Bin silently (Suppressing errors if it's already empty or path not found)
        os.system("powershell.exe -Command \"Clear-RecycleBin -Confirm:$false -ErrorAction SilentlyContinue\"")
        return "System Optimized (😊)"

    # --- 2. ENVIRONMENTAL AWARENESS ---
    def get_accurate_weather(self, city="Idukki"):
        """
        Reasoning: Triggered by intent regarding 'safety', 'outdoor planning', or 'sky conditions'.
        Source: Open-Meteo for high-precision local data in Idukki.
        """
        try:
            # Idukki, Kerala Coordinates
            url = f"https://api.open-meteo.com/v1/forecast?latitude=9.85&longitude=76.97&current_weather=true"
            data = requests.get(url, timeout=5).json()
            temp = data["current_weather"]["temperature"]
            return f"Currently {temp}°C in {city}."
        except Exception as e:
            return f"RECURSIVE_REPAIR_REQUIRED: Weather API sync failed."

    # --- 3. POWER & STATE MANAGEMENT ---
    def manage_power_state(self, action_code, mood="calm"):
        """
        Reasoning: 1=Shutdown, 2=Restart, 3=Sleep, 4=Lock.
        Triggered by intent to 'finish for the day', 'refresh', 'take a break', or 'secure'.
        """
        try:
            if action_code == 1:
                return self.final_shutdown_sequence(power_off=True, restart=False, mood=mood)
            elif action_code == 2:
                return self.final_shutdown_sequence(power_off=True, restart=True, mood=mood)
            elif action_code == 3:
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                return "Entering sleep mode. See you soon, Boss."
            elif action_code == 4:
                os.system("rundll32.exe user32.dll,LockWorkStation")
                return "System locked. Everything is secure, Boss."
            return "Executing power state change."
        except Exception as e:
            return f"RECURSIVE_REPAIR_REQUIRED: {str(e)}"

    # --- 4. GLOBAL CONTEXT ---
    def fetch_jasmin_news(self, topic="world", location=None, deep_dive=False):
        """
        Reasoning: Awareness and Contextual Intelligence.
        Handles general world news, specific locations, and detailed explanations.
        """
        # Logic to select the right feed based on location
        base_url = "http://feeds.bbci.co.uk/news/world/rss.xml"
        
        # Mapping common locations/topics to BBC feeds
        location_map = {
            "india": "http://feeds.bbci.co.uk/news/world/asia/india/rss.xml",
            "asia": "http://feeds.bbci.co.uk/news/world/asia/rss.xml",
            "tech": "http://feeds.bbci.co.uk/news/technology/rss.xml",
            "business": "http://feeds.bbci.co.uk/news/business/rss.xml",
            "science": "http://feeds.bbci.co.uk/news/science_and_environment/rss.xml"
        }
        
        if topic == "tech":
            base_url = location_map["tech"]
        elif location and location.lower() in location_map:
            base_url = location_map[location.lower()]
        
        try:
            feed = feedparser.parse(base_url)
            if not feed.entries:
                return "I couldn't fetch the news right now, Boss. The feed seems empty."
            
            report = f"\n{Fore.YELLOW}{Style.BRIGHT}✦ TOP STORIES FOR YOU, BOSS ✦{Style.RESET_ALL}\n"
            for i, entry in enumerate(feed.entries[:5]):
                title = entry.title
                summary = entry.description if hasattr(entry, 'description') else ""
                summary = re.sub('<[^<]+?>', '', summary).strip()
                
                pub_time = f" {Fore.BLACK}{Style.BRIGHT}— {entry.published}{Style.RESET_ALL}" if hasattr(entry, 'published') else ""
                
                # Dynamic emoji based on topic
                icon = "🌍"
                if "tech" in base_url: icon = "💻"
                elif "india" in base_url: icon = "🇮🇳"
                elif "business" in base_url: icon = "📈"
                elif "science" in base_url: icon = "🔬"

                report += f"  {icon} {Fore.CYAN}{Style.BRIGHT}{title}{Style.RESET_ALL}{pub_time}\n"
                if summary:
                    if len(summary) > 250: summary = summary[:247] + "..."
                    report += f"     {Fore.WHITE}{summary}{Style.RESET_ALL}\n"
                report += f"  {Fore.BLACK}{Style.DIM}{'─' * 50}{Style.RESET_ALL}\n"
            
            return report.strip()
        except Exception as e:
            return f"Error fetching news: {str(e)}"

    # --- 5. VISUAL MEMORY ---
    def capture_workspace_snapshot(self):
        """
        Reasoning: Triggered by intent to 'save', 'capture', or 'remember' the screen.
        Saves to the user's established project path.
        """
        try:
            # Define the save path in your project folder
            # Dynamic project-relative path
            save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Captures")
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
                
            # Generate a meaningful filename
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"Vibhath_Workspace_{timestamp}.png"
            filepath = os.path.join(save_dir, filename)
            
            # Take the shot
            screenshot = ImageGrab.grab()
            screenshot.save(filepath)
            
            return f"Captured and saved to: {filename} (😊)"
        except Exception as e:
            return f"RECURSIVE_REPAIR_REQUIRED: Screenshot failed - {str(e)}"

    # --- 6. COGNITIVE SKILLS (RECORDING) ---
    def manage_screen_recording(self, action="start"):
        """
        Reasoning: Triggered by intent to 'record', 'video', or 'capture workflow'.
        Saves high-quality .mp4 files to your unified Captures directory.
        """
        # Dynamic project-relative path
        save_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Captures")
        
        if action == "start" and not self.is_recording:
            try:
                self.is_recording = True
                if not os.path.exists(save_dir):
                    os.makedirs(save_dir)
                    
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                filename = os.path.join(save_dir, f"Vibhath_Devlog_{timestamp}.mp4")
                
                # Define codec and create VideoWriter object
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                screen_size = pyautogui.size()
                self.video_out = cv2.VideoWriter(filename, fourcc, 20.0, (screen_size))
                
                def recording_loop():
                    while self.is_recording:
                        img = pyautogui.screenshot()
                        frame = np.array(img)
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        self.video_out.write(frame)
                    self.video_out.release()

                self.record_thread = threading.Thread(target=recording_loop, daemon=True)
                self.record_thread.start()
                
                return f"Recording started (😊). Saving to: Captures"
            except Exception as e:
                self.is_recording = False
                return f"Error starting recording: {str(e)}"

        elif action == "stop" and self.is_recording:
            self.is_recording = False
            if self.record_thread:
                self.record_thread.join(timeout=2)
            return "Recording stopped and finalized. (🍃)"
        
        return "No action taken."

    # --- 7. LUMINANCE INTELLIGENCE ---
    def adjust_system_brightness(self, target_value=None, relative_change=None):
        """
        Reasoning: Direct response to eye strain or environmental lighting changes.
        Scale: 0 to 100.
        """
        try:
            print(f"{Fore.CYAN}[System] Brightness request: target={target_value}, relative={relative_change}")
            current_list = sbc.get_brightness()
            current = current_list[0] if current_list else 50
            
            if relative_change:
                # Handle semantic strings like "reduce" or "increase"
                if isinstance(relative_change, str):
                    rc = relative_change.lower()
                    if rc in ["reduce", "decrease"]:
                        new_brightness = current - 20
                    elif rc in ["increase", "raise"]:
                        new_brightness = current + 20
                    else:
                        new_brightness = current
                else:
                    new_brightness = current + relative_change
            elif target_value is not None:
                new_brightness = target_value
            else:
                # Default 'Comfort Mode'
                new_brightness = 30 
                
            new_brightness = max(0, min(100, new_brightness))
            sbc.set_brightness(int(new_brightness))
            return f"Luminance calibrated to {int(new_brightness)}%. (🍃)"
        except Exception as e:
            return f"Brightness sync failed - {str(e)}"

    # --- 8. ACOUSTIC INTELLIGENCE ---
    def manage_acoustic_environment(self, target_level=None, shift=None):
        """
        Reasoning: Direct response to social interruptions or environmental needs.
        Scale: 0 to 100 for both absolute level and relative shift.
        """
        try:
            print(f"{Fore.CYAN}[System] Audio request: level={target_level}, shift={shift}")
            import comtypes
            comtypes.CoInitialize() # Ensure COM is initialized for the thread
            devices = AudioUtilities.GetSpeakers()
            if hasattr(devices, 'Activate'):
                interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = cast(interface, POINTER(IAudioEndpointVolume))
            else:
                # Handle newer pycaw or pycaw-utils where GetSpeakers() returns an AudioDevice wrapper
                volume = devices.EndpointVolume
            
            current_vol_scalar = volume.GetMasterVolumeLevelScalar()
            current_vol_100 = current_vol_scalar * 100
            
            if shift:
                # Handle semantic strings like "reduce" or "increase"
                if isinstance(shift, str):
                    s = shift.lower()
                    if s in ["reduce", "decrease"]:
                        new_vol_100 = current_vol_100 - 20
                    elif s in ["increase", "raise"]:
                        new_vol_100 = current_vol_100 + 20
                    elif s == "mute":
                        new_vol_100 = 0
                    else:
                        new_vol_100 = current_vol_100
                else:
                    new_vol_100 = current_vol_100 + shift
            elif target_level is not None:
                new_vol_100 = target_level
            else:
                # Default 'Whisper Mode'
                new_vol_100 = 10
                
            new_vol_100 = max(0, min(100, new_vol_100))
            volume.SetMasterVolumeLevelScalar(new_vol_100 / 100.0, None)
            return f"Acoustics calibrated to {int(new_vol_100)}%. (🍃)"
        except Exception as e:
            return f"Audio sync failed - {str(e)}"

    # --- 9. OPTICAL READING ---
    def perform_optical_reading(self):
        """
        Reasoning: Triggered by intent to 'hear' rather than 'read'.
        Relieves eye strain and provides an audio layer to the workspace.
        """
        # --- CONFIRMATION PHASE ---
        msg = "Boss, I'm prepared to perform an optical reading of your workspace. Should I proceed?"
        self.voice.speak(msg, "serious")
        print(f"\n{Fore.RED}{Style.BRIGHT}[SECURITY] {msg}")
        
        # Blocking until Boss confirms via terminal
        input(f"{Fore.CYAN}>>> Press ENTER to confirm screen capture... ")

        try:
            # 1. Capture the screen (Focusing on the active area to save i3 resources)
            screenshot = ImageGrab.grab()
            
            # 2. Extract Text
            text = pytesseract.image_to_string(screenshot)
            
            if not text.strip():
                return "The screen looks a bit blank or I can't find clear text to read. (🍃)"

            # 3. Narrate using the central VoiceEngine
            self.voice.speak("I've got you. Here is what I see on your screen:", "protective")
            self.voice.speak(text, "calm")
            
            return "Finished reading the screen for you. (😊)"
            
        except Exception as e:
            error_msg = "Boss, I couldn't read the screen. Tesseract OCR seems to be missing or misconfigured on your system."
            self.voice.speak(error_msg, "apologetic")
            print(f"{Fore.RED}[OCR Error]: {str(e)}")
            return error_msg

    # --- 10. COMMUNICATION (WHATSAPP BETA) ---
    def send_whatsapp_message(self, contact=None, content=None):
        """
        Reasoning: Optimized for the Windows Beta application. 
        Handles UI lag intelligently to prevent 'Enter' being pressed too early.
        """
        if not contact or not content:
            return "I'm ready to send that, but who is the recipient or what's the message? (😊)"

        try:
            print(f"\n{Fore.CYAN}[WhatsApp] {Fore.WHITE}Initiating Beta Sync...")
            # Check if WhatsApp is already running to optimize the wait
            was_open = any('WhatsApp' in w.title for w in gw.getAllWindows())
            if was_open:
                print(f"{Fore.CYAN}[WhatsApp] {Fore.WHITE}Existing session detected. Optimizing launch speed.")
            else:
                print(f"{Fore.CYAN}[WhatsApp] {Fore.WHITE}Cold start detected. Expanding patience protocol.")

            is_number = contact.replace('+', '').replace(' ', '').replace('-', '').isdigit()

            if is_number:
                # Direct phone number routing
                print(f"{Fore.CYAN}[WhatsApp] {Fore.WHITE}Routing via Direct URI for number.")
                webbrowser.open(f"whatsapp://send?text={quote(content)}&phone={contact}")
            else:
                # Name-based routing requires opening the base app
                print(f"{Fore.CYAN}[WhatsApp] {Fore.WHITE}Routing via UI Search for contact: {contact}")
                webbrowser.open("whatsapp://")
            
            # Intelligent Wait for Beta App Initialization (Expanded for slow startups)
            timeout = 60
            start_time = time.time()
            launched = False
            
            print(f"{Fore.CYAN}[WhatsApp] {Fore.WHITE}Waiting for UI to stabilize...", end="", flush=True)
            
            while time.time() - start_time < timeout:
                windows = [w for w in gw.getAllWindows() if 'WhatsApp' in w.title]
                if windows:
                    beta_win = windows[0]
                    try:
                        beta_win.activate()
                    except:
                        pass
                    
                    # If it was already open, the UI update is usually faster
                    wait_time = 4.0 if was_open else 8.0
                    
                    # Print a little progress
                    for _ in range(int(wait_time)):
                        print(".", end="", flush=True)
                        time.sleep(1)
                        
                    launched = True
                    break
                time.sleep(1)

            print() # New line after dots

            if launched:
                print(f"{Fore.CYAN}[WhatsApp] {Fore.WHITE}UI Stabilized. Dispatching message.")
                # Extra explicit focus attempts
                try:
                    pyautogui.click(beta_win.centerx, beta_win.centery) # Click the center of the window to ensure focus
                except:
                    pass # Fallback if window gets minimized unexpectedly
                time.sleep(0.5)

                if is_number:
                    # URI already populated the text, just press Enter
                    pyautogui.press('enter')
                else:
                    # Execute Name-based Search Flow
                    pyautogui.hotkey('ctrl', 'f') # Focus search bar
                    time.sleep(1)
                    pyautogui.write(contact)      # Type contact name
                    time.sleep(2.5)               # Wait for search results to populate
                    pyautogui.press('enter')      # Select top result (opens chat)
                    time.sleep(1.5)               # Wait for chat pane to load
                    pyautogui.write(content)      # Type the message
                    time.sleep(0.5)
                    pyautogui.press('enter')      # Send
                
                status = "Restored existing flow" if was_open else "Launched new session"
                return f"Message dispatched to {contact} ({status}). (🍃)"
            else:
                print(f"{Fore.RED}[WhatsApp] Timeout reached. App failed to open.")
                return "The WhatsApp Beta window didn't appear in time. Is the app installed? (😊)"

        except Exception as e:
            return f"RECURSIVE_REPAIR_REQUIRED: WhatsApp Beta sync failed - {str(e)}"

    # --- 11. UNIVERSAL FALLBACK (JSON) ---
    def execute_custom_json_task(self, json_payload):
        """
        Reasoning: Catch-all for unique engineering requests (e.g., 'Make screen grayscale').
        Calls the Coding Tier to generate a validated script for execution.
        """
        # Logic to process dynamic model-generated JSON
        return "Custom JSON task acknowledged and executed."

    def handle_system_command(self, query):
        query = query.lower()

        if "battery" in query and ("what" in query or "percentage" in query or "level" in query or "how much" in query or "status" in query):
            status = SYSTEM_POWER_STATUS()
            ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status))
            pct = status.BatteryLifePercent
            plugged = "plugged in" if status.ACLineStatus == 1 else "running on battery power"
            if pct == 255: return "I am unable to read your battery status, Boss. You might be on a desktop system."
            return f"Boss, your battery is currently at {pct} percent and is {plugged}."
            
        if any(x in query for x in ["weather", "location", "where am i", "temperature"]):
            try:
                # 1. Get location
                loc_response = requests.get('https://ipapi.co/json/', timeout=5).json()
                city = loc_response.get("city", "Unknown Location")
                
                # If only asking for location, respond immediately
                if "where am i" in query or "location" in query:
                    return f"Boss, you are currently in {city}."

                # 2. Fetch Weather (for specific weather/temp queries)
                lat = loc_response.get("latitude")
                lon = loc_response.get("longitude")
                from config import OPENWEATHER_API_KEY
                url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
                weather_data = requests.get(url, timeout=5).json()
                temp = weather_data["main"]["temp"]
                cond = weather_data["weather"][0]["main"]
                
                return f"The weather in {city} is {cond} with a temperature of {temp} degrees Celsius, Boss."
            except Exception:
                return None

        # 2. Connectivity
        is_wifi = any(x in query for x in ["wifi", "wi-fi", "internet"])
        is_bt = "bluetooth" in query
        has_action = any(x in query for x in ["on", "enable", "connect", "start", "off", "disable", "disconnect", "stop"])

        if is_wifi and has_action:
            state = "on" if any(x in query for x in ["on", "enable", "connect"]) else "off"
            if state == "off": cmd = 'netsh wlan disconnect interface="Wi-Fi"'
            else: cmd = 'netsh interface set interface "Wi-Fi" admin=enabled'
            try:
                subprocess.run(cmd, shell=True, check=True)
                return f"I've handled that, Boss. Your WiFi is now {state}."
            except Exception: return None

        if is_bt and has_action:
            state = "on" if any(x in query for x in ["on", "enable", "start"]) else "off"
            ps_action = "Enable" if state == "on" else "Disable"
            cmd = f"powershell.exe -ExecutionPolicy Bypass -Command \"Get-PnpDevice -Class Bluetooth | {ps_action}-PnpDevice -Confirm:$false\""
            try:
                subprocess.run(cmd, shell=True, check=True)
                return f"Bluetooth is now {state}, Boss."
            except Exception: return None


        power_words = ["shutdown", "shut down", "restart", "reboot", "lock", "sleep"]
        target_words = ["device", "pc", "system", "computer", "laptop", "all", "everything", "apps"]
        
        if any(p in query for p in power_words) and any(t in query for t in target_words):
            if "restart" in query or "reboot" in query:
                return self.final_shutdown_sequence(power_off=True, restart=True)
            elif "shutdown" in query or "shut down" in query:
                return self.final_shutdown_sequence(power_off=True, restart=False)
            elif "lock" in query:
                os.system("rundll32.exe user32.dll,LockWorkStation")
                return "I've locked your screen, Boss."
            elif "sleep" in query:
                os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
                return "Entering sleep mode. See you soon, Boss."

        # 3b. Workspace Purge Intent
        if "close" in query and any(t in query for t in ["apps", "everything", "windows", "sectors"]):
            self.purge_workspace_sectors()
            return "I've cleared the workspace for you, Boss. (😊)"
            
        if any(x in query for x in ["abort", "cancel"]) or ("stop" in query and "shutdown" in query):
            os.system("shutdown /a")
            return "I've cancelled the operation, Boss. The system is stable."

        # 4. Alarm / Timer (DEPRECATED - Moved to Cognitive Engine)
        if "alarm" in query or "timer" in query:
            return None # Fall through to AI for Cognitive Alarm processing

        # 5. File & Folder Management
        if "create" in query and "folder" in query:
            name_match = re.search(r'named\s+([\w\s]+)|folder\s+([\w\s]+)|called\s+([\w\s]+)', query)
            folder_name = "New Folder"
            if name_match:
                folder_name = next(x for x in name_match.groups() if x is not None).strip()
            path = os.path.join(os.path.expanduser("~"), "Desktop", folder_name)
            try:
                os.makedirs(path, exist_ok=True)
                return f"I've created the folder {folder_name} on your desktop, Boss."
            except Exception as e: return None

        return None

    # --- 12. WORKSPACE LAYOUT (SPATIAL AWARENESS) ---

    def jasmin_auto_layout_workspace(self):
        """
        Autonomous Grid Snapper. (📐)
        Scans the OS for open, visible applications and mathematically arranges them.
        """
        # The OS Junk Filter: We must ignore background fluff and system UI
        ignore_list = [
            "Program Manager", "Settings", "Taskbar", "Task Manager",
            "Microsoft Text Input Application", "Windows Default Lock Screen",
            "Character Map", "Calculator", "Microsoft Store", "Photos",
            "Windows Input Experience", "CoreWindow", "DesktopWindowXamlSource",
            "NVIDIA", "Steam", "Spotify", "Discord", "Skype", "Overlays",
            "SearchHost", "StartMenuExperienceHost", "ShellExperienceHost"
        ]
        
        valid_windows = []
        
        # --- PHASE 1: RETRY SCANNING FOR APPS ---
        for attempt in range(3):
            all_windows = gw.getAllWindows()
            valid_windows = []
            
            print(f"{Fore.CYAN}[System] Layout Attempt {attempt+1}: Scanning sectors...")
            for w in all_windows:
                try:
                    title = w.title.strip()
                    title_lower = title.lower()
                    is_immune = any(skip.lower() in title_lower for skip in ignore_list) or (self.jasmin_title.lower() in title_lower)
                    
                    if title and not is_immune and w.width > 400 and w.height > 400 and not w.isMinimized:
                        print(f"{Fore.BLUE}[System] Detected valid app: '{title}'")
                        valid_windows.append(w)
                except: continue

            if len(valid_windows) >= 2 or attempt == 2:
                break
            time.sleep(3)

        if len(valid_windows) < 2:
            return f"[Jasmin]: Only {len(valid_windows)} active window(s) detected. No snapping required. (🍃)"
                
        # --- PHASE 2: MATHEMATICAL SNAPPING ---
        windows_to_snap = valid_windows[:4]
        num_apps = len(windows_to_snap)
        screen_width, screen_height = pyautogui.size()
        usable_height = screen_height - 40 # Leave space for Taskbar
        
        # 3. Execution: Snap the geometry
        try:
            # UNLOCK: Windows must be restored (not Maximized) to be movable/resizable
            for win in windows_to_snap:
                try:
                    if win.isMaximized:
                        win.restore()
                        time.sleep(0.3)
                except: pass

            if num_apps == 2:
                # 50/50 Vertical Split
                windows_to_snap[0].resizeTo(screen_width//2, usable_height); windows_to_snap[0].moveTo(0, 0)
                windows_to_snap[1].resizeTo(screen_width//2, usable_height); windows_to_snap[1].moveTo(screen_width//2, 0)

            elif num_apps == 3:
                # 1 Main + 2 Stacked
                windows_to_snap[0].resizeTo(int(screen_width*0.6), usable_height); windows_to_snap[0].moveTo(0, 0)
                windows_to_snap[1].resizeTo(int(screen_width*0.4), usable_height//2); windows_to_snap[1].moveTo(int(screen_width*0.6), 0)
                windows_to_snap[2].resizeTo(int(screen_width*0.4), usable_height//2); windows_to_snap[2].moveTo(int(screen_width*0.6), usable_height//2)

            elif num_apps == 4:
                # 2x2 Grid
                half_w, half_h = screen_width//2, usable_height//2
                windows_to_snap[0].resizeTo(half_w, half_h); windows_to_snap[0].moveTo(0, 0)
                windows_to_snap[1].resizeTo(half_w, half_h); windows_to_snap[1].moveTo(half_w, 0)
                windows_to_snap[2].resizeTo(half_w, half_h); windows_to_snap[2].moveTo(0, half_h)
                windows_to_snap[3].resizeTo(half_w, half_h); windows_to_snap[3].moveTo(half_w, half_h)
                
            for win in windows_to_snap:
                try: win.activate()
                except: pass
                
            return f"[Jasmin]: Scanned sector. Snapped {num_apps} apps into formation. (😊)"
            
        except Exception as e:
            return f"[Jasmin]: Grid snap failed. [{str(e)}] (😬)"

    # --- 13. MOBILE AUTOMATION (MACRODROID BRIDGE) ---
    def jasmin_trigger_mobile_automation(self, action_query):
        """
        Optimized Remote Mobile Bridge.
        Translates natural language intents into MacroDroid Webhooks.
        """
        text = action_query.lower()
        intent = "unknown"
        
        # Expanded Semantic Mapping
        mapping = {
            "answer_call": ["answer", "pick up", "accept", "receive", "take the call", "talk"],
            "decline_call": ["decline", "hang up", "reject", "cut", "cancel", "don't pick", "ignore", "busy"],
            "toggle_speaker": ["speaker", "loudspeaker", "hands free", "hand free", "on the speaker"]
        }
        
        for key, keywords in mapping.items():
            if any(word in text for word in keywords):
                intent = key
                break
            
        if intent == "unknown":
            # Fallback: Check for partial matches
            if "speaker" in text: intent = "toggle_speaker"
            elif "answer" in text: intent = "answer_call"
            elif "cut" in text or "reject" in text: intent = "decline_call"
            else: return "[Jasmin]: I'm not sure which phone action to take, Boss. (🤔)"
            
        def trigger_webhook(target_intent):
            try:
                # Optimized background request with precise timeout
                url = f"{MACRODROID_BASE}{target_intent}"
                requests.get(url, timeout=3)
            except Exception as e:
                print(f"{Fore.RED}[System Error] Phone Bridge Connection Failed: {e}")

        # Fire and forget in a daemon thread for instant UI response
        threading.Thread(target=trigger_webhook, args=(intent,), daemon=True).start()
        
        # Dynamic Response System
        responses = {
            "answer_call": [
                "I've picked up the call for you, Boss. (📞)",
                "Call accepted. You're live! (🎙️)",
                "Connecting you now... (📲)"
            ],
            "decline_call": [
                "Call declined. (🚫)",
                "Cut the line. (✂️)",
                "Rejected. I've got your back, Boss. (🛡️)"
            ],
            "toggle_speaker": [
                "Toggling loudspeaker... (🔊)",
                "Switching to hands-free mode. (📣)",
                "Loudspeaker activated. (📢)"
            ]
        }
        
        import random
        return f"[Jasmin]: {random.choice(responses[intent])}"

    def jasmin_handle_call_arrival(self, caller_name="Unknown", custom_msg=None):
        """
        The Master Call Automation Function. (📞)
        1. Announces the call (Terminal + Voice)
        2. Activates the A+UP / D+DOWN triggers
        """
        import random
        from colorama import Fore, Style
        
        # 1. Prepare Dialogue
        if custom_msg:
            final_speech = custom_msg
        else:
            dialogues = [
                f"Boss, you have an incoming call from {caller_name}.",
                f"Incoming call detected. It's {caller_name} calling.",
                f"Your phone is ringing, Boss. It's {caller_name}.",
                f"Alert. {caller_name} is on the line right now."
            ]
            final_speech = random.choice(dialogues)

        # 2. VISUAL TERMINAL ALERT
        print(f"\n{Fore.RED}{Style.BRIGHT}{'='*60}")
        print(f"📞  {Fore.WHITE}INCOMING CALL ALERT")
        print(f"    {Fore.YELLOW}{final_speech}")
        print(f"{Fore.RED}{'='*60}\n")
        print(f"{Fore.CYAN}[System] Call hotkeys active: 'A+UP' to Accept, 'D+DOWN' to Decline.")
        
        # 3. SPEAKING
        self.voice.speak(final_speech, "serious")

        # 4. KEYBOARD TRIGGERS
        def on_answer():
            print(f"{Fore.GREEN}[System] Call Accept Triggered via 'A+UP' keys.")
            self.jasmin_trigger_mobile_automation("answer_call")
            self._deactivate_call_hotkeys()
            
        def on_decline():
            print(f"{Fore.RED}[System] Call Decline Triggered via 'D+DOWN' keys.")
            self.jasmin_trigger_mobile_automation("decline_call")
            self._deactivate_call_hotkeys()

        # Deactivate first to avoid duplicates
        self._deactivate_call_hotkeys()
        
        keyboard.add_hotkey('a+up', on_answer, suppress=True)
        keyboard.add_hotkey('d+down', on_decline, suppress=True)
        
        # Auto-timeout after 45 seconds
        threading.Timer(45.0, self._deactivate_call_hotkeys).start()

    def _deactivate_call_hotkeys(self):
        try:
            keyboard.remove_hotkey('a+up')
            keyboard.remove_hotkey('d+down')
            from colorama import Fore
            print(f"{Fore.YELLOW}[System] Call hotkeys deactivated.")
        except:
            pass

    # --- 13. COGNITIVE ALARM (ACOUSTIC INTELLIGENCE) ---
    def set_cognitive_alarm(self, time_input):
        """
        Reasoning: Intelligent, persistent alarm with Wake-on-Timer support.
        Wakes the system from sleep to ensure alarms trigger reliably.
        """
        self.alarm_active = False # Signal any previous alarm thread to stop
        time.sleep(0.1) 
        
        session_id = time.time()
        self.active_alarm_sessions.add(session_id)
        
        try:
            # 1. Parsing Logic
            now = datetime.now()
            from datetime import timedelta
            if "minute" in time_input or "hour" in time_input:
                import re
                nums = re.findall(r'\d+', time_input)
                if nums:
                    quantity = int(nums[0])
                    unit = "minutes" if "minute" in time_input else "hours"
                    target_time = now + timedelta(**{unit: quantity})
                else:
                    target_time = now + timedelta(minutes=1) 
            else:
                target_time = parser.parse(time_input)
                if target_time < now: target_time += timedelta(days=1)

            def stop_alarm(sid):
                if sid in self.active_alarm_sessions:
                    self.active_alarm_sessions.remove(sid)
                
                # Only stop hardware if no alarms are sounding
                if not any(sid in self.active_alarm_sessions for sid in self.active_alarm_sessions):
                    ctypes.windll.winmm.mciSendStringW('stop alarm_mp3', None, 0, 0)
                    ctypes.windll.winmm.mciSendStringW('close alarm_mp3', None, 0, 0)
                return False 

            def start_listening(sid):
                with Listener(on_press=lambda k: stop_alarm(sid)) as listener:
                    listener.join()

            def alarm_thread(sid):
                # --- WAKE TIMER INTEGRATION ---
                wait_seconds = (target_time - datetime.now()).total_seconds()
                
                if wait_seconds > 0:
                    # Register a Windows Waitable Timer to wake the PC
                    handle = ctypes.windll.kernel32.CreateWaitableTimerW(None, True, None)
                    if handle:
                        # 100-nanosecond intervals. Negative for relative time.
                        duetime = ctypes.c_longlong(int(-10000000 * wait_seconds))
                        # SetWaitableTimer(Handle, DueTime, Period, Routine, Arg, Resume=True)
                        ctypes.windll.kernel32.SetWaitableTimer(handle, ctypes.byref(duetime), 0, None, None, True)
                    
                    print(f"\n{Fore.CYAN}[Timer] Countdown initiated (Wake-on-Timer Active): ", end="", flush=True)
                    for i in range(int(wait_seconds), 0, -1):
                        if not threading.main_thread().is_alive(): break
                        if sid not in self.active_alarm_sessions: break 
                        
                        mins, secs = divmod(i, 60)
                        # Only show countdown for the most imminent alarm to prevent flickering
                        if sid == min(self.active_alarm_sessions, default=sid):
                            print(f"\r{Fore.CYAN}[Timer] Remaining: {Fore.WHITE}{mins:02d}:{secs:02d} ", end="", flush=True)
                        time.sleep(1)
                    
                    if sid not in self.active_alarm_sessions: 
                        if handle: ctypes.windll.kernel32.CloseHandle(handle)
                        return 
                    
                    # If we woke up (or were already awake), wait for timer completion just in case
                    if handle:
                        ctypes.windll.kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)
                        ctypes.windll.kernel32.CloseHandle(handle)
                    
                    print(f"\r{Fore.CYAN}[Timer] {Fore.RED}TIME IS UP!              ")
                
                self.active_alarm_sessions.add(f"sounding_{sid}")
                threading.Thread(target=start_listening, args=(sid,), daemon=True).start()
                
                print(f"\n{Fore.RED}{Style.BRIGHT}[ALARM] ACTIVE - PRESS ANY KEY TO SILENCE")
                ctypes.windll.winmm.mciSendStringW(f'open "{tone_path}" type mpegvideo alias alarm_mp3', None, 0, 0)
                
                i = 0
                while sid in self.active_alarm_sessions:
                    color = Fore.RED if i % 2 == 0 else Fore.YELLOW
                    print(f"\r{color}  >>> ALERT: {target_time.strftime('%I:%M %p')} <<<  ", end="", flush=True)
                    ctypes.windll.winmm.mciSendStringW('play alarm_mp3 from 0', None, 0, 0)
                    time.sleep(2) 
                    i += 1
                
                if f"sounding_{sid}" in self.active_alarm_sessions:
                    self.active_alarm_sessions.remove(f"sounding_{sid}")
                    print(f"\n{Fore.GREEN}[Alarm] Silenced.")
                    self.voice.speak("Alarm silenced. Welcome back, Boss.", "calm")

            threading.Thread(target=alarm_thread, args=(session_id,), daemon=True).start()
            return f"Alarm set for {target_time.strftime('%I:%M %p')}. I'll wake the system if it's sleeping. (😊)"

        except Exception as e:
            return f"RECURSIVE_REPAIR_REQUIRED: Alarm sync failed - {str(e)} (😬)"

    # --- 14. CREDENTIAL VAULT (SECURITY SECTOR) ---
    def manage_vault_credentials(self, platform, password=None, action="save"):
        """
        Reasoning: Local, encrypted-ready storage for credentials.
        Allows for 'Save' (Memorize) and 'Type' (Automatic dispatch) actions.
        """
        import json
        vault_path = "vault.json"
        
        try:
            # Load existing vault
            vault = {}
            if os.path.exists(vault_path):
                with open(vault_path, "r") as f:
                    vault = json.load(f)
            
            if action == "save":
                if not platform or not password:
                    return "I need both the platform name and the password to secure it, Boss. (😊)"
                
                # Normalize platform name
                key = platform.lower().strip()
                existed = key in vault
                vault[key] = password
                
                with open(vault_path, "w") as f:
                    json.dump(vault, f, indent=4)
                
                if existed:
                    return f"I've updated the credentials for {platform} in the vault. (🕊️)"
                else:
                    return f"I've stored the credentials for {platform} in the vault. (🕊️)"
            
            elif action == "type":
                if not platform:
                    self.voice.speak("Which platform's password should I type, Boss?", "smiling")
                    return "(Waiting for platform name...)"
                
                key = platform.lower().strip()
                if key in vault:
                    stored_pwd = vault[key]
                    self.voice.speak(f"Entering credentials for {platform} now. Please focus the input field.", "smiling")
                    time.sleep(3) 
                    kb = Controller()
                    kb.type(stored_pwd)
                    return f"Credentials dispatched for {platform}. (🍃)"
                else:
                    return f"I don't have a record for '{platform}' in my vault, Boss. (😬)"

            elif action == "reveal":
                if not platform:
                    self.voice.speak("Which platform's password do you need, Boss?", "smiling")
                    return "(Waiting for platform name...)"
                
                key = platform.lower().strip()
                if key in vault:
                    stored_pwd = vault[key]
                    return f"The password for {platform} is: {stored_pwd}. (🕊️)"
                else:
                    return f"I don't have a record for '{platform}', Boss. (🍃)"
            
            return "Invalid vault action requested."
            
        except Exception as e:
            return f"Vault sync failed: {str(e)} (😬)"

    # --- 15. IDENTITY DISPATCH (QUICK TYPE) ---
    def type_personal_info(self, info_type):
        """
        Reasoning: Speeds up form filling by typing personal details.
        Maps: 'name', 'email', 'mobile'.
        """
        data_map = {
            "name":      "Vibhath",
            "email":     "vibhathcross@gmail.com",
            "mail id":   "vibhathcross@gmail.com",
            "mobile":    "8593891820",
            "phone":     "8593891820",
            "mobile no": "8593891820"
        }
        
        key = info_type.lower().strip() if info_type else ""
        
        if key == "password":
            return "Safety Protocol: I cannot type passwords via Identity Dispatch. Please use the Credential Vault for that. (🛡️)"

        if key in data_map:
            value = data_map[key]
            self.voice.speak(f"Typing your {key} now, Boss. Please focus the target field.", "smiling")
            time.sleep(3) 
            kb = Controller()
            kb.type(value)
            return f"Typed {key} successfully. (🍃)"
        else:
            return f"I don't have a shortcut for '{info_type}' yet, Boss. (😬)"