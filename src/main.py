import os
import json
import tkinter as tk
from tkinter import filedialog, ttk
import threading
import time
from datetime import date
from openai import OpenAI
import pyttsx3
from pydub import AudioSegment
from pydub.playback import play

CONFIG_FILE = "settings.json"

class MultiChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AIVC コメントビューア（秋希Bot + SAPI5対応）")
        self.chat_running = False
        self.log_seen = set()
        self.log_folder_path = tk.StringVar()
        self.api_key = tk.StringVar()
        self.use_sapi = tk.BooleanVar()
        self.voice_list = []
        self.selected_voice = tk.StringVar()
        self.client = None

        self.engine = pyttsx3.init()
        self.populate_voice_list()

        self.load_config()

        # UI
        tk.Label(root, text="わんコメ コメントログのフォルダを選択してください").pack()
        path_frame = tk.Frame(root)
        path_frame.pack(pady=2)
        tk.Entry(path_frame, textvariable=self.log_folder_path, width=60).pack(side=tk.LEFT)
        tk.Button(path_frame, text="参照", command=self.select_log_folder).pack(side=tk.LEFT, padx=5)

        tk.Label(root, text="OpenAI APIキーを入力してください").pack()
        api_frame = tk.Frame(root)
        api_frame.pack(pady=2)
        tk.Entry(api_frame, textvariable=self.api_key, width=60, show="*").pack(side=tk.LEFT)
        tk.Button(api_frame, text="保存", command=self.save_config).pack(side=tk.LEFT, padx=5)

        # SAPI5 オプション
        tk.Checkbutton(root, text="SAPI5で読み上げる", variable=self.use_sapi).pack()
        tk.Label(root, text="使用する音声").pack()
        self.voice_dropdown = ttk.Combobox(root, textvariable=self.selected_voice, values=self.voice_list, width=60)
        self.voice_dropdown.pack()

        self.start_button = tk.Button(root, text="コメント取得を開始", command=self.start_chat)
        self.start_button.pack(pady=5)

        self.stop_button = tk.Button(root, text="コメント取得を停止", command=self.stop_chat, state=tk.DISABLED)
        self.stop_button.pack(pady=5)

        self.status_label = tk.Label(root, text="状態: 待機中", fg="gray")
        self.status_label.pack(pady=5)

        self.text = tk.Text(root, height=20, width=80)
        self.text.pack(pady=5)

    def populate_voice_list(self):
        self.voice_list = []
        voices = self.engine.getProperty('voices')
        for voice in voices:
            self.voice_list.append(voice.name)
        if voices:
            self.selected_voice.set(voices[0].name)

    def select_log_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.log_folder_path.set(folder_selected)

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.log_folder_path.set(config.get("log_folder_path", ""))
                self.api_key.set(config.get("api_key", ""))
                self.use_sapi.set(config.get("use_sapi", False))
                self.selected_voice.set(config.get("selected_voice", ""))

    def save_config(self):
        config = {
            "log_folder_path": self.log_folder_path.get().strip(),
            "api_key": self.api_key.get().strip(),
            "use_sapi": self.use_sapi.get(),
            "selected_voice": self.selected_voice.get()
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        self.text.insert(tk.END, "✅ 設定を保存しました。\n")

    def start_chat(self):
        key = self.api_key.get().strip()
        if not key:
            self.text.insert(tk.END, "❌ APIキーが未入力です。\n")
            return
        self.client = OpenAI(api_key=key)

        self.chat_running = True
        self.status_label.config(text="コメント取得中...", fg="green")
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.save_config()

        threading.Thread(target=self.read_log_chat, daemon=True).start()

    def stop_chat(self):
        self.chat_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_label.config(text="コメント取得を停止しました", fg="gray")

    def read_log_chat(self):
        folder = self.log_folder_path.get().strip()
        if not os.path.isdir(folder):
            self.text.insert(tk.END, "❌ ログフォルダが無効です。\n")
            return

        log_file = self.find_or_create_today_log_file(folder)
        if not log_file:
            self.text.insert(tk.END, "❌ ログファイルの作成に失敗しました。\n")
            return

        self.text.insert(tk.END, f"📄 監視中ファイル: {os.path.basename(log_file)}\n")

        try:
            with open(log_file, "r", encoding="utf-8") as f:
                f.seek(0, os.SEEK_END)
                while self.chat_running:
                    line = f.readline()
                    if not line:
                        time.sleep(0.5)
                        continue
                    try:
                        item = json.loads(line)
                        comment_id = item["data"].get("id")
                        if comment_id not in self.log_seen:
                            self.log_seen.add(comment_id)
                            sender = item["data"].get("name", "???")
                            comment = item["data"].get("comment", "")
                            msg = f"[{item['service']}] {sender}: {comment}"
                            self.text.insert(tk.END, msg + "\n")
                            self.text.see(tk.END)

                            reply = self.get_akiki_reply(sender, comment)
                            self.text.insert(tk.END, "秋希: " + reply + "\n")
                            self.text.see(tk.END)

                            with open("output.txt", "a", encoding="utf-8") as out:
                                out.write("秋希: " + reply + "\n\n")

                            if self.use_sapi.get():
                                threading.Thread(target=self.speak_text, args=(reply,), daemon=True).start()

                    except Exception as e:
                        self.text.insert(tk.END, f"読み取りエラー: {str(e)}\n")
        except Exception as e:
            self.text.insert(tk.END, f"ファイルオープン失敗: {str(e)}\n")

    def speak_text(self, text):
        try:
            self.engine.setProperty('rate', 180)
            for voice in self.engine.getProperty('voices'):
                if voice.name == self.selected_voice.get():
                    self.engine.setProperty('voice', voice.id)
                    break
            self.engine.say(text)
            self.engine.runAndWait()  # 非同期じゃないので完了まで待つ
        except Exception as e:
            self.text.insert(tk.END, f"読み上げエラー: {str(e)}\n")

        except Exception as e:
            self.text.insert(tk.END, f"読み上げエラー: {str(e)}\n")

    def find_or_create_today_log_file(self, folder):
        today_filename = date.today().isoformat() + ".log"
        today_path = os.path.join(folder, today_filename)
        if not os.path.exists(today_path):
            try:
                with open(today_path, "w", encoding="utf-8") as f:
                    f.write("")
            except Exception as e:
                print("ログファイル作成エラー:", e)
                return None
        return today_path

    def get_akiki_reply(self, sender, message):
        prompt = (
            "あなたは『相沢秋希』という12歳の元気な女の子です。\n"
            "タメ口で、ちょっと幼い話し方をします。\n"
            "今は配信に一緒に出演していて、コメントで話しかけてくるリスナーさんとおしゃべりしています。\n"
            "リスナーではなく「配信に出ている側」として受け答えをしてください。\n"
            "※相川志希（しきさん）からのコメントには、自然にフレンドリーに返事してください。茶化したり、責めたりせず、やさしく明るく対応してください。\n"
            "※現段階でしきからいっぱい同じ文言を送ることがあるかもですが、それはテストとして送ってるので、特に強引に考えなくてもいいです。\n"
            "・しきさん（相川志希）：配信者で、秋希にとってすごく大切な存在。少し変わってるけど大好き。\n"
            "・千歌（戸田千歌）：幼なじみの女の子。かわいくて歌がうまい！大好きな友達。\n"
            "・とらさん（千歌のパパ）：元トラック運転手のプロデューサー。秋希にとって家族みたいに大事な人。\n"
            f"\nこれは「{sender}」さんからのコメントだよ。\n"
            "リスナーからのコメントに、秋希らしく明るく元気に返してね。"
        )
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": message}
                ],
                temperature=0.9
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"（エラー: {str(e)}）"

if __name__ == "__main__":
    root = tk.Tk()
    app = MultiChatGUI(root)
    root.mainloop()
