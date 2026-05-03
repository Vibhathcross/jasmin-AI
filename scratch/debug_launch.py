import sys
import os

# Add parent dir to path to import system_handler
sys.path.append(os.getcwd())

from system_handler import SystemHandler

class MockVoice:
    def speak(self, t, m="calm"): pass
    def wait_until_done(self): pass

handler = SystemHandler(MockVoice())
print(f"Cache size: {len(handler.app_shortcuts)}")

import difflib
target = "chrome"
matches = difflib.get_close_matches(target, handler.app_shortcuts.keys(), n=1, cutoff=0.7)
print(f"Matches for 'chrome': {matches}")

if matches:
    print(f"Path: {handler.app_shortcuts[matches[0]]}")
else:
    print("No matches for 'chrome'")
