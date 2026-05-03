import speech_recognition as sr
import pyttsx3
import audioop
import threading
import pyaudio
import time
import queue
import pythoncom
from colorama import Fore, Style

class VoiceEngine:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        # Optimization: Lower pause threshold for reduced latency
        self.recognizer.pause_threshold = 0.6
        self.lock = threading.Lock()
        self.speech_queue = queue.Queue()
        self.stop_speech = threading.Event()
        
        self.worker_thread = threading.Thread(target=self._speech_worker, daemon=True)
        self.worker_thread.start()
        
        # Pre-initialize PyAudio to eliminate startup latency when listening starts
        self.p = pyaudio.PyAudio()
        
    def _speech_worker(self):
        """Persistent worker thread for sequential, stable speech."""
        try:
            # Initialize COM for this thread (required for SAPI5)
            pythoncom.CoInitialize()
            
            # Use direct SAPI5 COM object to bypass pyttsx3 event loop bugs
            import comtypes.client
            self.speaker = comtypes.client.CreateObject("SAPI.SpVoice")
            
            voices = self.speaker.GetVoices()
            if voices.Count > 2:
                self.speaker.Voice = voices.Item(2)
            elif voices.Count > 1:
                self.speaker.Voice = voices.Item(1)
            
            while not self.stop_speech.is_set():
                try:
                    # Wait for speech tasks
                    item = self.speech_queue.get(timeout=0.1)
                    if item is None: break
                    
                    text, mood = item
                    
                    # Clean non-ASCII for speech engine only (keep emojis in terminal)
                    import re
                    # Remove all non-ASCII characters and also explicit (emoji) markers
                    clean_text = re.sub(r'[^\x00-\x7F]+', ' ', text)
                    clean_text = re.sub(r'\(.*?\)', '', clean_text)
                    clean_text = ' '.join(clean_text.split()).strip()

                    # --- PHONETIC CORRECTIONS ---
                    corrections = {
                        "vib hat": "vbhaath",
                        "v bat": "vbhaath",
                        "vibhath": "vbhaath",
                        "adil" : "aadh-ill",
                        "sanmaya" : "Sanmayaa"
                    }
                    for word, correction in corrections.items():
                        # Case-insensitive replacement
                        pattern = re.compile(re.escape(word), re.IGNORECASE)
                        clean_text = pattern.sub(correction, clean_text)

                    # --- NATURAL EMOTIONAL RENDERING ---
                    # Each mood maps to: (rate, pitch_shift, terminal_emoji, terminal_color)
                    MOOD_MAP = {
                        "smiling":    ( 1,  3, "😊", Fore.LIGHTCYAN_EX),
                        "motivated":  ( 2,  4, "⚡", Fore.LIGHTCYAN_EX),
                        "laughing":   ( 2,  6, "😄", Fore.LIGHTYELLOW_EX),
                        "witty":      ( 2,  5, "😏", Fore.LIGHTYELLOW_EX),
                        "crying":     (-3, -5, "😢", Fore.LIGHTBLUE_EX),
                        "protective": (-2, -4, "🛡️", Fore.LIGHTBLUE_EX),
                        "serious":    ( 0, -2, "😬", Fore.LIGHTRED_EX),
                        "realist":    ( 0, -1, "😬", Fore.LIGHTRED_EX),
                        "apologetic": (-1, -3, "😔", Fore.LIGHTRED_EX),
                        "calm":       ( 0,  0, "🍃", Fore.LIGHTWHITE_EX),
                        "sparkling":  ( 1,  4, "✨", Fore.LIGHTMAGENTA_EX),
                        "victory":    ( 2,  5, "🏆", Fore.LIGHTGREEN_EX),
                        "funny":      ( 2,  5, "😂", Fore.LIGHTYELLOW_EX),
                        "roasting":   ( 1, -1, "🔥", Fore.LIGHTRED_EX),
                    }

                    rate, pitch, emoji, color = MOOD_MAP.get(
                        mood, (0, 0, "🍃", Fore.LIGHTWHITE_EX)
                    )

                    self.speaker.Rate = rate

                    # Build SAPI5 prosody markup only if there's a pitch shift
                    if pitch != 0:
                        speech_text = f'<pitch absmiddle="{pitch}">{clean_text}</pitch>'
                    else:
                        speech_text = clean_text

                    # Terminal: emoji + name + message (clean, no [Jasmin] label clutter)
                    print(f"\n{emoji}  {color}{Style.BRIGHT}{text}{Style.RESET_ALL}")

                    # Speak asynchronously (1) so we can interrupt it from other threads
                    self.speaker.Speak(speech_text, 1)
                    
                    # Wait for speech to finish or queue to be cleared
                    while self.speaker.Status.RunningState != 1: # 1 = SRSEDone (Finished)
                        if self.speech_queue.empty() and self.speaker.Status.RunningState == 1:
                            break
                        time.sleep(0.05)
                        
                    self.speech_queue.task_done()
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    print(f"{Fore.RED}[Speech Error]: {e}")
        except Exception as e:
            print(f"{Fore.RED}[Engine Init Error]: {e}")

    def interrupt(self):
        """Immediately clears the queue and forcefully stops ongoing SAPI5 speech."""
        while not self.speech_queue.empty():
            try:
                self.speech_queue.get_nowait()
                self.speech_queue.task_done()
            except:
                break
                
        # Instantly kill ongoing speech by sending an empty string with SVSFPurgeBeforeSpeak (2) | SVSFlagsAsync (1)
        if hasattr(self, 'speaker') and self.speaker:
            try:
                # 3 = SVSFlagsAsync | SVSFPurgeBeforeSpeak
                self.speaker.Speak("", 3)
                # Forcefully stop any pending pyttsx3 events if active
                if hasattr(self, 'engine'):
                    self.engine.stop()
            except:
                pass
        
        # Log interruption visually
        print(f"{Fore.YELLOW}[System] Speech Interrupted.")
        # but clearing the queue prevents subsequent lines.

    def speak(self, text, mood="calm"):
        """Queues a speech task for the worker thread."""
        self.speech_queue.put((text, mood))

    def wait_until_done(self):
        """Blocks until the speech queue is empty and the speaker has finished."""
        self.speech_queue.join()

    def wait_until_done(self):
        """Blocks until the speech queue is empty and the speaker has finished."""
        self.speech_queue.join()

    def listen_manual(self, stop_event):
        """Captures audio until the stop_event is set, with live volume monitoring"""
        # Use pre-initialized PyAudio instance for zero delay
        p = self.p
        
        # Audio Settings
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                        input=True, frames_per_buffer=CHUNK)
        
        frames = []
        print(f"\n{Fore.CYAN}{Style.BRIGHT}[Status]: Listening to you, Boss... ", end="", flush=True)
        
        while not stop_event.is_set():
            data = stream.read(CHUNK, exception_on_overflow=False)
            frames.append(data)
            
            # CALCULATE VOLUME FOR DEBUGGING
            rms = audioop.rms(data, 2)
            level = int(rms / 100) # Adjusted scale
            bar = "█" * min(level, 25)
            print(f"\r{Fore.CYAN}[Status]: Listening to you, Boss... {Fore.WHITE}[{bar:<25}]", end="", flush=True)

        print(f"\n{Fore.YELLOW}[Mic] Captured. Processing...")
        
        stream.stop_stream()
        stream.close()
        # Do not terminate self.p here as we reuse it
        
        # Convert to AudioData
        raw_audio = b"".join(frames)
        
        # Apply Digital Gain Boost
        raw_audio = audioop.mul(raw_audio, 2, 4) # 400% boost for clarity
        
        audio_data = sr.AudioData(raw_audio, RATE, 2)
        
        try:
            print(f"{Fore.CYAN}[System] Converting speech to text...")
            return self.recognizer.recognize_google(audio_data)
        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            return "NETWORK_ERROR"

    def dictate(self):
        """Speech-to-text dictation with visual feedback and direct typing."""
        import keyboard
        import sys
        
        # Consistent styling with the rest of the app
        print(f"\r{Fore.LIGHTWHITE_EX}🕊️  {Style.BRIGHT}[Jasmin]: Mic Hot. Speak your logic...{Style.RESET_ALL}   ", end="", flush=True)
        
        with sr.Microphone() as source:
            # Quick calibration
            self.recognizer.adjust_for_ambient_noise(source, duration=0.2)
            try:
                # timeout=3: If you don't speak within 3 seconds, it cancels to save resources.
                # phrase_time_limit=10: Max 10 seconds of speaking before it forces a translation block.
                audio = self.recognizer.listen(source, timeout=3, phrase_time_limit=10)
                
                print(f"\r{Fore.LIGHTYELLOW_EX}😬  {Style.BRIGHT}[Jasmin]: Catching phrase to cloud...{Style.RESET_ALL} ", end="", flush=True)
                
                # Cloud Bridge
                text = self.recognizer.recognize_google(audio)
                
                # Instantly type the result wherever your cursor is active
                keyboard.write(text + " ")
                
                print(f"\r{Fore.LIGHTCYAN_EX}😊  {Style.BRIGHT}[Jasmin]: Typed -> '{text}'{Style.RESET_ALL}           \n")
                return text
                
            except sr.WaitTimeoutError:
                print(f"\r{Fore.LIGHTWHITE_EX}🍃  {Style.BRIGHT}[Jasmin]: Sector Clear. No voice detected.{Style.RESET_ALL}       ")
            except sr.UnknownValueError:
                print(f"\r{Fore.LIGHTRED_EX}😬  {Style.BRIGHT}[Jasmin]: Audio garbled. Couldn't catch that, Boss.{Style.RESET_ALL}")
            except sr.RequestError:
                print(f"\r{Fore.LIGHTRED_EX}😬  {Style.BRIGHT}[Jasmin]: Network bridge dropped. Check connection.{Style.RESET_ALL}")
            except Exception as e:
                print(f"\r{Fore.RED}[Dictation Error]: {e}")
        return None
