import pythoncom
import comtypes.client
import threading
import time

pythoncom.CoInitialize()
speaker = comtypes.client.CreateObject('SAPI.SpVoice')

def speak_long():
    pythoncom.CoInitialize()
    speaker.Speak('This is a very long sentence that will take a few seconds to complete.', 0)
    print('Speak finished')

threading.Thread(target=speak_long).start()
time.sleep(1)
print('Interrupting...')
speaker.Speak('', 3)
print('Interrupted')
time.sleep(2)
