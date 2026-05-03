# Jasmin AI

A high-performance, low-RAM background assistant for Windows.

## 🚀 Features
- **Hardware Control**: Voice commands for WiFi and Bluetooth.
- **File Management**: Auto-organize your desktop.
- **Communication**: Send WhatsApp messages hands-free.
- **Cloud Brain**: Integrated with **Gemini 1.5 Flash** for lightning-fast knowledge queries.
- **Offline TTS**: Uses `pyttsx3` to keep memory usage low.

## 🛠️ Setup
1. **API Key**: 
   - Go to [Google AI Studio](https://aistudio.google.com/).
   - Generate an API Key.
   - Paste it into `config.py` in the `GEMINI_API_KEY` field.

2. **Run the Assistant**:
   ```powershell
   # From the project directory
   .\venv\Scripts\python main.py
   ```

3. **Wake Word**: 
   - Say "Hey Assistant" to trigger the listener.

## 🎙️ Sample Commands
- "Hey Assistant... Turn off WiFi"
- "Hey Assistant... Open notepad"
- "Hey Assistant... Organize my desktop"
- "Hey Assistant... What is the capital of France?"

## ⚠️ Important Note
- **WiFi/Bluetooth control** requires the terminal to be run as **Administrator**.
- **WhatsApp automation** uses your default browser; ensure you are logged into WhatsApp Web.
