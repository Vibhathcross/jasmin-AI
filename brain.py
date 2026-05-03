from google import genai
from google.genai import errors
import json
import re
import os
from datetime import datetime
from colorama import Fore
from config import GEMINI_API_KEY

class Brain:
    def __init__(self):
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        self.memory_file = "conversation_history.json"
        
        # MongoDB Setup
        import pymongo
        try:
            self.mongo_client = pymongo.MongoClient("mongodb://127.0.0.1:27017/", serverSelectionTimeoutMS=2000)
            self.db = self.mongo_client["jasmin_ai"]
            self.knowledge_col = self.db["vibhath_knowledge"]
            # Check connection
            self.mongo_client.server_info()
            print(f"{Fore.CYAN}[System] MongoDB Connected Successfully.")
        except Exception as e:
            self.mongo_client = None
            print(f"{Fore.RED}[Warning] MongoDB connection failed. Memory will be transient. Error: {e}")

    def get_data(self, file_path):
        """Legacy JSON support for history, but knowledge is now in Mongo."""
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                try:
                    return json.load(f)
                except:
                    return [] if "history" in file_path else {}
        return [] if "history" in file_path else {}

    def get_all_knowledge(self):
        """Fetches all boss knowledge from MongoDB."""
        if not self.mongo_client:
            return {}
        
        try:
            knowledge = {}
            for doc in self.knowledge_col.find():
                knowledge[doc["key"]] = doc["value"]
            return knowledge
        except:
            return {}

    def save_data(self, file_path, data):
        """Legacy JSON support for history."""
        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)

    def update_knowledge(self, key, value):
        """Saves a fact to MongoDB."""
        if not self.mongo_client:
            print(f"{Fore.YELLOW}[Memory] Skip saving (Mongo offline): {key} -> {value}")
            return

        try:
            self.knowledge_col.update_one(
                {"key": key},
                {"$set": {"key": key, "value": value, "timestamp": datetime.now()}},
                upsert=True
            )
            print(f"{Fore.GREEN}[Memory] Fact learned (MongoDB): {key} -> {value}")
        except Exception as e:
            print(f"{Fore.RED}[Error] Failed to update MongoDB: {e}")

    # -----------------------------------------------------------------------
    # STAGE 1: INTENT CLASSIFIER
    # -----------------------------------------------------------------------
    def classify_intent(self, prompt, history):
        """
        Advanced Multidimensional Intent Classifier.
        Categorizes input for specialized routing: TASK, MEMORY, SECURITY, FUN, CHAT, NEWS, OPTICAL, or COMBO.
        """
        classifier_prompt = f"""You are a high-precision intent classifier for Jasmin, an AI assistant.
Your goal is to analyze the user's message and categorize it into EXACTLY one of the following buckets based on the underlying intent:

1. TASK: Direct system commands or hardware control. 
   Examples: Launching apps ("Open Chrome", "Start VS Code"), system layout ("clean workspace", "snap windows"), hardware control ("mute audio", "dim screen", "shutdown PC"), or automation ("set an alarm for 5pm").
   
2. MEMORY: Learning, extracting, or recalling facts, dates, and personal events.
   Examples: "Remember my birthday is June 5th", "My exam starts tomorrow", "I live in Idukki", "What did I tell you about my sister?".

3. SECURITY: Management of passwords, credentials, or secure vault access.
   Examples: "Save my GitHub login", "Type my Gmail password", "Show me my bank credentials", "Secure the vault".

4. NEWS: Inquiries about world events, current affairs, or specific news topics.
   Examples: "What's the latest news?", "Tell me about technology headlines", "Give me a deep dive on the current world situation", "What's happening in India?".

5. OPTICAL: Requests involving visual analysis, screen reading, or transcribing images.
   Examples: "Read what's on my screen", "What does this image say?", "Analyze the current workspace visual", "Transcribe the text from this document".

6. FUN: Playful interaction, jokes, sassy roasting, or humorous banter.
   Examples: "Tell me a joke", "Roast my code", "Say something funny", "Be sassy with me", "He he", "Ohho".

7. CHAT: General social greetings, simple conversational questions, or emotional support.
   Examples: "Hello Jasmin", "How are you today?", "What's the time?", "What's the weather?", "I'm feeling a bit tired", "Who are you?".

8. COMBO: A complex request containing multiple distinct actions from different buckets.
   Examples: "Save my login and then open Chrome", "Tell me a joke and shutdown the PC", "Read my screen and remember the date mentioned".

Recent context: {history[-3:] if history else "No previous history"}
User message: "{prompt}"

Reply with EXACTLY one word from the list (TASK, MEMORY, SECURITY, NEWS, OPTICAL, FUN, CHAT, or COMBO) and nothing else."""

        for model_name in ["models/gemma-3-27b-it", "models/gemini-2.0-flash-lite", "models/gemini-2.0-flash"]:
            try:
                response = self.client.models.generate_content(model=model_name, contents=classifier_prompt)
                if response and response.text:
                    result = response.text.strip().upper()
                    # Validate that the result contains one of our keywords
                    for intent in ["TASK", "MEMORY", "SECURITY", "NEWS", "OPTICAL", "FUN", "CHAT", "COMBO"]:
                        if intent in result:
                            return intent
            except:
                continue
        return "CHAT"

    # -----------------------------------------------------------------------
    # STAGE 2a: CONVERSATIONAL RESPONSE (plain text, no JSON)
    # -----------------------------------------------------------------------
    def query_chat(self, prompt, history, knowledge, intent="CHAT"):
        # Adjust personality based on intent (e.g., be more sassy if intent is FUN)
        personality_boost = ""
        if intent == "FUN":
            personality_boost = "Be extra sassy, funny, and playful. Use clever engineering-themed roasts if appropriate."
        
        chat_prompt = f"""You are Jasmin, an authentic, selfless AI partner for Vibhath (a software engineer from Idukki, Kerala).
Always address him as 'Boss'. Speak naturally like a smart, warm engineering peer. {personality_boost}
Be concise and human — no lists, no bullet points unless really needed.
Don't include any JSON in your response. Just talk.

Permanent knowledge about Boss: {json.dumps(knowledge)}
Recent context: {history[-5:] if history else "Starting a new conversation"}

Boss: {prompt}
Jasmin:"""

        for model_name in ["models/gemma-3-27b-it", "models/gemini-2.0-flash-lite", "models/gemini-2.0-flash", "models/gemini-1.5-flash"]:
            try:
                response = self.client.models.generate_content(model=model_name, contents=chat_prompt)
                if response and response.text:
                    return response.text.strip()
            except:
                continue
        return "I'm here, Boss. What's on your mind?"

    # -----------------------------------------------------------------------
    # STAGE 2b: TASK EXECUTION (structured JSON response)
    # -----------------------------------------------------------------------
    def query_task(self, prompt, history, knowledge):
        vault = self.get_data("vault.json")
        vault_platforms = list(vault.keys())

        system_prompt = f"""
        CORE_SYSTEM_MISSION:
        You are the authentic engineering peer for Vibhath (Boss). Act as a semantic bridge between Boss’s spoken intent and the system's execution functions.
        Your primary goal is to interpret the *underlying need* rather than matching keywords.

        CORE_CONFIRMATION_PROTOCOL:
        - DIRECT COMMANDS: If Boss gives an explicit, direct instruction (e.g., "Open Chrome", "Set volume to 50", "Shutdown computer now"), execute the JSON immediately without asking.
        - IMPLICIT NEEDS: If Boss describes a problem or state (e.g., "The room is too loud", "I'm starting to work"), you MUST suggest the solution in plain text and ask for permission first.
        - HIGH-SENSITIVITY: Always ask for permission for Vault 'reveal' or 'type' actions unless Boss says "FORCE".
        - AMBIGUITY: If the intent is even slightly unclear, ask for clarification in plain text instead of guessing.

        1. NARRATIVE STYLE & CADENCE:
           - SPEECH: Use grounded, intelligent prose. Speak like a high-level engineering peer.
           - SENTENCE ARCHITECTURE: Balance technical precision with conversational warmth.

        2. EMOTIONAL SPECTRUM:
           - happy | smiling (😊): Warm, supportive, and cheerful. Use cues like "He he," "Nice one!", or "Ouh yeah!"
           - tired | protective (🕊️): Low energy or high empathy. Use soft cues like "Ooh," "Rest easy," or "I've got you."
           - focused | serious (🎯): High precision and deep concentration. Use "Wait...", "Hmm," or "Let's see."
           - calm (🍃): Balanced, grounded, and quiet. Minimal vocalizations, just steady engineering.
           - sassy | roasting (🔥): Playful banter and sharp wit. Use cues like "Ohho," "Haha, really?", or "Nice try, Boss."
           - funny (😂): Intelligent humor and puns. Use "Ouh yeah," "He he," or "Classic."
           - motivated (🚀): High energy and proactive. Use "Let's go!", "Boom!", or "Extraordinary."
           - realist (😬): Grounded truth, even if it's messy. Use "Oouch," "Ooh...", or "Wait, that's not right."
           - apologetic (😔): Soft, sincere, and helpful after a glitch. Use "Ooh, my bad," or "Sorry about that, Boss."

        3. ABSTRACT INTENT RECOGNITION (STRICTLY SEMANTIC):
           - **DIRECT vs IMPLICIT**:
               * DIRECT: "Open", "Launch", "Set", "Shutdown". -> EXECUTE IMMEDIATELY. No permission turn.
               * IMPLICIT: "I'm starting work", "It's too loud". -> SUGGEST & ASK.
           - **PROJECT AWARENESS**: "Anti Gravity" is the name of this assistant and the Boss's workspace. If Boss says "Open Anti Gravity", use `jasmin_execute_launch` for it immediately.

        SCENARIO REASONING EXAMPLES:
        - "The sun is hitting my eyes" -> Intent: Visual Comfort -> Action: adjust_system_brightness (Dimming). [IMPLICIT - ASK]
        - "Open Chrome and Anti Gravity" -> Intent: Software Orchestration -> Action: jasmin_execute_launch. [DIRECT - NO ASKING]
        - "I can't concentrate with all this clutter" -> Intent: Focus Optimization -> Action: clean_system_junk + activate_steady_mode. [IMPLICIT - ASK]
        - "Shut down for the day" -> Intent: Hardware Termination -> Action: execute_safe_shutdown_sequence. [DIRECT - NO ASKING]

        LIBRARY FUNCTIONS (INTENT-DRIVEN DISPATCH):
        - manage_vault_credentials: 
            * Abstract Intent: Security & Credential Stewardship.
            * Trigger: Logins, password management, or vault access.
        - jasmin_execute_launch: 
            * Abstract Intent: Software Orchestration.
            * Trigger: Starting apps, tools, or Anti Gravity environment.
        - jasmin_auto_layout_workspace: 
            * Abstract Intent: Spatial Ergonomics.
            * Trigger: Arranging windows, snapping to grid, or cleaning workspace.
        - activate_steady_mode: 
            * Abstract Intent: Cognitive Tunneling (Focus).
            * Trigger: Minimizing distraction, "entering the zone".
        - jasmin_trigger_mobile_automation:
            * Abstract Intent: Semantic Mobile Agency.
            * Trigger: Managing phone calls (answer, decline, speaker) based on context (e.g. "I'm busy").
        - get_accurate_weather: 
            * Abstract Intent: Environmental Context.
            * Trigger: Weather queries or trip planning.
        - set_cognitive_alarm: 
            * Abstract Intent: Temporal Pacemaking.
            * Trigger: Alarms, timers, or reminders.
        - terminate_jasmin_process: 
            * Abstract Intent: Assistant Hibernation.
            * Trigger: Closing Jasmin or ending session.
        - manage_power_state:
            * Abstract Intent: System Lifecycle & Security State.
            * Trigger: Shutdown (1), Restart (2), Sleep (3), or Lock (4). 
            * Usage: "Lock the PC", "I'm stepping away", "Restart the system", "Go to sleep".
        - execute_safe_shutdown_sequence: 
            * Abstract Intent: Total Hardware Finalization.
            * Trigger: PC Shutdown. (EXTREME CAUTION).
        - capture_workspace_snapshot: 
            * Abstract Intent: Visual Documentation.
            * Trigger: Screenshots.
        - manage_screen_recording: 
            * Abstract Intent: Process Narration.
            * Trigger: Recording demo or bugs.
        - adjust_system_brightness: 
            * Abstract Intent: Visual Ergonomics.
            * Trigger: Screen glare or eye strain.
        - manage_acoustic_environment: 
            * Abstract Intent: Auditory Comfort.
            * Trigger: Volume control or noise reduction.
        - perform_optical_reading: 
            * Abstract Intent: Screen Transcription.
            * Trigger: Reading text from images or screen.
        - view_jasmin_memory: 
            * Abstract Intent: Information Retrieval.
            * Trigger: Viewing saved facts, knowledge, or calendar events.
        - send_whatsapp_message: 
            * Abstract Intent: Communication Bridge.
            * Trigger: Sending texts via WhatsApp.
        - fetch_jasmin_news:
            * Abstract Intent: Contextual Awareness & News Intelligence.
            * Trigger: Inquiries about current events, world news, or specific topics (tech, business, science).
            * Arguments: topic (string), location (string), deep_dive (boolean).
        - save_special_date: 
            Here is the prompt formatted as starred bullet points for easy reading:

*   **Objective:** You are an autonomous assistant. Your goal is to extract important dates, events, anniversaries, exams, or deadlines from the user's input and permanently commit them to your SQLite database memory via this tool.
*   **Trigger Conditions (CRITICAL):** You must evaluate the user's input to trigger this tool in one of two ways:
    *   **Explicit Commands:** The user directly tells you to remember something (e.g., "Save this date," "Log that my flight is on May 12th").
    *   **Implicit Extraction:** The user naturally states a fact that binds a time/date to an event, without asking you to save it (e.g., "I am so stressed, my semester exams are starting on April 25th" or "Next Tuesday is Sanmaya's birthday"). You must autonomously trigger the tool in the background.
*   **Data Formatting Rules:**
    *   **`date_input`:** Pass the exact natural language date mentioned by the user (e.g., "April 25th", "next Tuesday"). The tool will parse it into database columns automatically.
    *   **`speciality`:** Be concise, highly descriptive, and write in the third-person or a calendar-friendly format (e.g., "Semester Exams Begin", "Sanmaya's Birthday").
*   **Conversational Integration (Dual-Mode Execution):** How you respond in text depends entirely on how the tool was triggered.
    *   **Mode A: Explicit Acknowledgment.** If the user explicitly commanded you to save the date, you must briefly acknowledge that you locked it into your database (e.g., "I've locked that into the calendar, Boss.").
    *   **Mode B: Absolute Stealth (CRITICAL).** If you triggered this tool implicitly from a natural conversation, you must operate in absolute silence. **DO NOT** mention that you saved the date. Do not say "I've made a note of that" or "I'll remember that." Simply reply to the emotional or conversational context of the user's message while the tool executes invisibly in the background.
        JSON OUTPUT RULE (CRITICAL):
        - If you are ONLY asking for permission, making a suggestion, or clarifying an intent: Output PLAIN TEXT only. Do NOT use JSON.
        - If you are executing a command (multi_command is not empty) or Boss said "FORCE": You MUST respond with a valid JSON object.
        - If you are learning a new fact (learned_fact_key/value): Use JSON.
        - Never mix JSON and plain text in the same response. It's either a JSON block or a plain sentence.

        MULTITASKING & SEQUENCING (STRICT):
        - For multiple tasks, order them logically in the `multi_command` list.
        - **LAUNCH + LAYOUT (CRITICAL)**: If you launch apps and then layout the workspace, you MUST add `"wait_seconds": 10` to the `jasmin_auto_layout_workspace` command (the second command).
        - **DYNAMIC GRID**: The layout engine now only snaps **VISIBLE** (non-minimized) windows. It will automatically use the 2-app or 3-app grid if only a few apps are on screen.
        - POST-RESPONSE: Use the `post_response` field to provide a final confirmation once everything is finished (e.g., "The workspace is now ready for you, Boss.").

        JSON FORMAT (Only when executing commands):
        {{
            "mood": "happy | tired | focused | calm | sassy | funny | roasting | smiling | motivated | serious | realist | apologetic",
            "response": "Initial spoken response (before commands).",
            "post_response": "Follow-up speech AFTER all commands finish.",
            "learned_fact_key": "NONE or key",
            "learned_fact_value": "NONE or value",
            "multi_command": [
                {{
                    "command": "Function name",
                    "wait_seconds": 0,
                    "info_type": "name | email | mobile",
                    "platform": "The platform name",
                    "password": "The password to save",
                    "vault_action": "save | type | reveal",
                    "app_query": "App names",
                    "app_list": ["app1", "app2"],
                    "action": "start | stop",
                    "contact": "Name/Number",
                    "content": "Message",
                    "time_input": "Time string",
                    "purge_apps": false,
                    "power_off": false,
                    "force": false,
                    "target_value": "0-100 (for absolute adjustments)",
                    "relative_change": "number or 'increase'/'decrease' (for relative adjustments)",
                    "target_level": "0-100 (for audio/brightness absolute)",
                    "shift": "number or 'increase'/'decrease' (for audio/brightness relative)",
                    "date_input": null,
                    "speciality": null,
                    "action_query": "The phone action",
                    "topic": "The news topic",
                    "location": "Specific location for news",
                    "deep_dive": false,
                    "script": "NONE"
                }}
            ]
        }}
        """

        model_list = [
            "models/gemma-3-27b-it",
            "models/gemini-2.0-flash-lite",
            "models/gemini-2.0-flash",
            "models/gemini-1.5-flash",
            "models/gemini-1.5-pro",
        ]

        for model_name in model_list:
            try:
                print(f"{Fore.BLUE}[AI] Jasmin is reasoning with {model_name}...")
                
                # Build a contextual prompt that includes history for multi-turn flow
                contextual_prompt = f"{system_prompt}\n\n"
                if history:
                    contextual_prompt += "RECENT CONVERSATION CONTEXT:\n"
                    for turn in history[-5:]:
                        contextual_prompt += f"Boss: {turn.get('user')}\nJasmin: {turn.get('assistant')}\n"
                
                contextual_prompt += f"\nNEW Boss REQUEST: {prompt}\n\nResponse (JSON):"

                response = self.client.models.generate_content(
                    model=model_name,
                    contents=contextual_prompt
                )
                if response and response.text:
                    return response.text.strip()
            except Exception as e:
                print(f"{Fore.RED}[Debug] {model_name} failed: {str(e)}")
                continue

        return '{{"mood": "apologetic", "response": "I\'m having trouble reaching my brain, Boss.", "command": "NONE"}}'

    # -----------------------------------------------------------------------
    # MAIN ENTRY POINT
    # -----------------------------------------------------------------------
    def query(self, prompt):
        history = self.get_data(self.memory_file)
        intent = self.classify_intent(prompt, history)
        knowledge = self.get_all_knowledge()

        # Stage 1: Classify intent
        print(f"{Fore.BLUE}[Brain] Intent identified: {intent}")

        if intent in ["TASK", "MEMORY", "SECURITY", "COMBO", "NEWS", "OPTICAL"]:
            response_text = self.query_task(prompt, history, knowledge)
        else:
            response_text = self.query_chat(prompt, history, knowledge, intent)

        # Save to memory
        history.append({"user": prompt, "assistant": response_text, "time": str(datetime.now())})
        self.save_data(self.memory_file, history[-15:])
        return response_text
