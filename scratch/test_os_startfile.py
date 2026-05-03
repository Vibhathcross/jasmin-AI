import os
import time

try:
    print("Attempting to launch notepad.exe using os.startfile...")
    os.startfile("notepad.exe")
    print("Success! (Wait, did it actually open?)")
except Exception as e:
    print(f"Failed: {e}")
