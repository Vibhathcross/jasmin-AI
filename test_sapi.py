import pythoncom
import comtypes.client

pythoncom.CoInitialize()
speaker = comtypes.client.CreateObject("SAPI.SpVoice")
speaker.Rate = 2
speaker.Speak("Testing direct sapi5.")
