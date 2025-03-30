import pyttsx3

engine = pyttsx3.init()
voices = engine.getProperty('voices')
for i, voice in enumerate(voices):
    print(f"[{i}] ID: {voice.id} / Name: {voice.name}")