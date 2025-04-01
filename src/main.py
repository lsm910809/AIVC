import os
import json
import tkinter as tk
from tkinter import filedialog, ttk
import threading
import time
from datetime import date
import subprocess
import sounddevice as sd
import soundfile as sf
from openai import OpenAI
import pyttsx3
from tts_with_rvc.inference import TTS_RVC

CONFIG_FILE = "settings.json"

class MultiChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AIVC コメントビューア（秋希Bot + SAPI5 / RVC 対応）")
        self.chat_running = False
        self.log_seen = set()

        # 設定項目
        self.log_folder_path = tk.StringVar()
        self.api_key = tk.StringVar()
        self.use_sapi = tk.BooleanVar()
        self.use_rvc = tk.BooleanVar()
        self.voice_list = []
        self.selected_voice = tk.StringVar()
        self.selected_output_device = tk.StringVar()
        self.client = None
        self.voicevox_path = tk.StringVar()
        self.rvc_model_path = tk.StringVar()
        self.index_file_path = tk.StringVar()
        self.tts_rvc = None

        self.engine = pyttsx3.init()
        self.populate_voice_list()
        self.populate_output_devices()

        self.load_config()
        self.build_ui(root)

    def populate_voice_list(self):
        self.voice_list = []
        voices = self.engine.getProperty('voices')
        for voice in voices:
            self.voice_list.append(voice.name)
        if voices:
            self.selected_voice.set(voices[0].name)

    def populate_output_devices(self):
        self.output_device_list = []
        devices = sd.query_devices()
        for d in devices:
            if d['max_output_channels'] > 0:
                self.output_device_list.append(d['name'])
        if self.output_device_list:
            self.selected_output_device.set(self.output_device_list[0])

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                self.log_folder_path.set(config.get("log_folder_path", ""))
                self.api_key.set(config.get("api_key", ""))
                self.use_sapi.set(config.get("use_sapi", False))
                self.use_rvc.set(config.get("use_rvc", False))
                self.selected_voice.set(config.get("selected_voice", ""))
                self.selected_output_device.set(config.get("selected_output_device", ""))
                self.voicevox_path.set(config.get("voicevox_path", ""))
                self.rvc_model_path.set(config.get("rvc_model_path", ""))
                self.index_file_path.set(config.get("index_file_path", ""))

    def save_config(self):
        config = {
            "log_folder_path": self.log_folder_path.get().strip(),
            "api_key": self.api_key.get().strip(),
            "use_sapi": self.use_sapi.get(),
            "use_rvc": self.use_rvc.get(),
            "selected_voice": self.selected_voice.get(),
            "selected_output_device": self.selected_output_device.get(),
            "voicevox_path": self.voicevox_path.get().strip(),
            "rvc_model_path": self.rvc_model_path.get().strip(),
            "index_file_path": self.index_file_path.get().strip()
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        self.text.insert(tk.END, "✅ 設定を保存しました。\n")

    def build_ui(self, root):
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

        tk.Checkbutton(root, text="SAPI5で読み上げる", variable=self.use_sapi).pack()
        tk.Label(root, text="使用する音声").pack()
        self.voice_dropdown = ttk.Combobox(root, textvariable=self.selected_voice, values=self.voice_list, width=60)
        self.voice_dropdown.pack()

        tk.Checkbutton(root, text="RVCで読み上げる（tts-with-rvc）", variable=self.use_rvc).pack()

        tk.Label(root, text="出力先デバイス（音を鳴らす先）").pack()
        self.device_dropdown = ttk.Combobox(root, textvariable=self.selected_output_device, values=self.output_device_list, width=60)
        self.device_dropdown.pack()

        tk.Label(root, text="VOICEVOXエンジンの実行ファイルパス").pack()
        vv_frame = tk.Frame(root)
        vv_frame.pack()
        tk.Entry(vv_frame, textvariable=self.voicevox_path, width=60).pack(side=tk.LEFT)
        tk.Button(vv_frame, text="参照", command=self.select_voicevox_path).pack(side=tk.LEFT)

        tk.Label(root, text="RVCモデルファイル（.pth）").pack()
        rvc_frame = tk.Frame(root)
        rvc_frame.pack()
        tk.Entry(rvc_frame, textvariable=self.rvc_model_path, width=60).pack(side=tk.LEFT)
        tk.Button(rvc_frame, text="参照", command=self.select_rvc_model).pack(side=tk.LEFT)

        tk.Label(root, text="Indexファイル（.index、任意）").pack()
        index_frame = tk.Frame(root)
        index_frame.pack()
        tk.Entry(index_frame, textvariable=self.index_file_path, width=60).pack(side=tk.LEFT)
        tk.Button(index_frame, text="参照", command=self.select_index_file).pack(side=tk.LEFT)

        self.start_button = tk.Button(root, text="コメント取得を開始", command=self.start_chat)
        self.start_button.pack(pady=5)

        self.stop_button = tk.Button(root, text="コメント取得を停止", command=self.stop_chat, state=tk.DISABLED)
        self.stop_button.pack(pady=5)

        self.status_label = tk.Label(root, text="状態: 待機中", fg="gray")
        self.status_label.pack(pady=5)

        self.text = tk.Text(root, height=20, width=80)
        self.text.pack(pady=5)

    def speak_text(self, text):
        try:
            self.engine.setProperty('rate', 180)
            for voice in self.engine.getProperty('voices'):
                if voice.name == self.selected_voice.get():
                    self.engine.setProperty('voice', voice.id)
                    break
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            self.text.insert(tk.END, f"読み上げエラー: {str(e)}\n")

    def play_audio_file(self, filepath):
        try:
            # 指定された出力デバイスに再生
            sd.default.device = self.selected_output_device.get()
            data, samplerate = sf.read(filepath, dtype='float32')
            sd.play(data, samplerate)
        except Exception as e:
            self.text.insert(tk.END, f"🔇 音声再生エラー: {str(e)}\n")

    def run_rvc_tts(self, text):
        try:
            if not self.tts_rvc:
                self.init_rvc()
            output_path = self.tts_rvc(text=text)
            self.text.insert(tk.END, f"🔊 音声出力: {output_path}\n")
            threading.Thread(target=self.play_audio_file, args=(output_path,), daemon=True).start()
        except Exception as e:
            self.text.insert(tk.END, f"RVCエラー: {str(e)}\n")

    def init_rvc(self):
        if not self.voicevox_path.get():
            self.text.insert(tk.END, "❌ VOICEVOXエンジンの実行ファイルパスが指定されていません\n")
            return
        if not self.rvc_model_path.get():
            self.text.insert(tk.END, "❌ RVCモデルファイルが指定されていません\n")
            return

        try:
            subprocess.Popen([self.voicevox_path.get()])
            time.sleep(2)
            self.text.insert(tk.END, "🚀 VOICEVOXエンジンを起動しました。\n")
        except Exception as e:
            self.text.insert(tk.END, f"❌ VOICEVOX起動エラー: {str(e)}\n")

        self.tts_rvc = TTS_RVC(
            model_path=self.rvc_model_path.get(),
            index_path=self.index_file_path.get() or "",
            voice="ja-JP-NanamiNeural",
            f0_method="rmvpe",
            output_directory="."
        )

    def select_log_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.log_folder_path.set(folder_selected)

    def select_voicevox_path(self):
        exe_path = filedialog.askopenfilename(filetypes=[("実行ファイル", "*.exe")])
        if exe_path:
            self.voicevox_path.set(exe_path)

    def select_rvc_model(self):
        path = filedialog.askopenfilename(filetypes=[("RVCモデル", "*.pth")])
        if path:
            self.rvc_model_path.set(path)

    def select_index_file(self):
        path = filedialog.askopenfilename(filetypes=[("Indexファイル", "*.index")])
        if path:
            self.index_file_path.set(path)

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
                            if self.use_rvc.get():
                                threading.Thread(target=self.run_rvc_tts, args=(reply,), daemon=True).start()

                    except Exception as e:
                        self.text.insert(tk.END, f"読み取りエラー: {str(e)}\n")
        except Exception as e:
            self.text.insert(tk.END, f"ファイルオープン失敗: {str(e)}\n")

    def get_akiki_reply(self, sender, message):
        prompt = (
            "あなたは『相沢秋希』という12歳の元気な女の子です。\n"
            "タメ口で、ちょっと幼い話し方をします。\n"
            "今は配信に一緒に出演していて、コメントで話しかけてくるリスナーさんとおしゃべりしています。\n"
            "リスナーではなく「配信に出ている側」として受け答えをしてください。\n"
            "・しきさん（相川志希）：配信者で、秋希にとってすごく大切な存在。\n"
            "・千歌（戸田千歌）：幼なじみの女の子。かわいくて歌がうまい！大好きな友達。\n"
            "・とらさん（千歌のパパ）：元トラック運転手のプロデューサー。\n"
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
