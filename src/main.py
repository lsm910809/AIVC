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
import glob

CONFIG_FILE = "settings.json"

class MultiChatGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AIVC コメントビューア（秋希Bot + RVC/SAPI5対応）")

        # 内部変数
        self.chat_running = False
        self.log_seen = set()
        self.client = None
        self.tts_rvc = None
        self.get_ai_reply_override = True  # これが True のときだけ should_respond() が有効

        # 各種 GUI 値
        self.log_folder_path = tk.StringVar()
        self.api_key = tk.StringVar()
        self.use_sapi = tk.BooleanVar()
        self.use_rvc = tk.BooleanVar()
        self.selected_voice = tk.StringVar()
        self.selected_output_device = tk.StringVar()
        self.voicevox_path = tk.StringVar()
        self.rvc_model_path = tk.StringVar()
        self.index_file_path = tk.StringVar()
        self.prompt_file_path = tk.StringVar()
        self.character_name = tk.StringVar()
        self.keyword_filter = tk.StringVar()
        self.pitch_value = tk.IntVar(value=0)
        self.manual_input = tk.StringVar()
        self.keyword_filter = tk.StringVar()

        # 音声エンジン
        self.engine = pyttsx3.init()
        self.populate_voice_list()
        self.populate_output_devices()

        # UI描画
        self.build_ui()
        self.load_config()

    def build_ui(self):
        tk.Label(self.root, text="コメントログのフォルダ").pack()
        f1 = tk.Frame(self.root); f1.pack()
        tk.Entry(f1, textvariable=self.log_folder_path, width=60).pack(side=tk.LEFT)
        tk.Button(f1, text="参照", command=self.select_log_folder).pack(side=tk.LEFT)

        tk.Label(self.root, text="OpenAI APIキー").pack()
        f2 = tk.Frame(self.root); f2.pack()
        tk.Entry(f2, textvariable=self.api_key, width=60, show="*").pack(side=tk.LEFT)
        tk.Button(f2, text="保存", command=self.save_config).pack(side=tk.LEFT)

        tk.Label(self.root, text="キャラ名").pack()
        tk.Entry(self.root, textvariable=self.character_name, width=30).pack()

        tk.Label(self.root, text="呼びかけキーワード（カンマ区切り）").pack()
        tk.Entry(self.root, textvariable=self.keyword_filter, width=60).pack()

        tk.Label(self.root, text="プロンプトファイル（.txt）").pack()
        f_prompt = tk.Frame(self.root); f_prompt.pack()
        tk.Entry(f_prompt, textvariable=self.prompt_file_path, width=60).pack(side=tk.LEFT)
        tk.Button(f_prompt, text="参照", command=self.select_prompt_file).pack(side=tk.LEFT)

        tk.Checkbutton(self.root, text="SAPI5で読み上げ", variable=self.use_sapi).pack()
        tk.Label(self.root, text="SAPI5 音声選択").pack()
        ttk.Combobox(self.root, textvariable=self.selected_voice, values=self.voice_list, width=60).pack()

        tk.Checkbutton(self.root, text="RVCで読み上げ（tts-with-rvc）", variable=self.use_rvc).pack()
        tk.Label(self.root, text="VOICEVOXエンジンのパス").pack()
        f3 = tk.Frame(self.root); f3.pack()
        tk.Entry(f3, textvariable=self.voicevox_path, width=60).pack(side=tk.LEFT)
        tk.Button(f3, text="参照", command=self.select_voicevox_path).pack(side=tk.LEFT)

        tk.Label(self.root, text="RVCモデル（.pth）").pack()
        f4 = tk.Frame(self.root); f4.pack()
        tk.Entry(f4, textvariable=self.rvc_model_path, width=60).pack(side=tk.LEFT)
        tk.Button(f4, text="参照", command=self.select_rvc_model).pack(side=tk.LEFT)

        tk.Label(self.root, text="Indexファイル（.index、任意）").pack()
        f5 = tk.Frame(self.root); f5.pack()
        tk.Entry(f5, textvariable=self.index_file_path, width=60).pack(side=tk.LEFT)
        tk.Button(f5, text="参照", command=self.select_index_file).pack(side=tk.LEFT)

        tk.Label(self.root, text="出力先デバイス").pack()
        ttk.Combobox(self.root, textvariable=self.selected_output_device, values=self.output_device_list, width=60).pack()

        tk.Label(self.root, text="RVC ピッチ調整（-24〜+24）").pack()
        tk.Scale(self.root, from_=-24, to=24, orient=tk.HORIZONTAL, variable=self.pitch_value, length=400).pack()

        # 手動コメント入力欄
        tk.Label(self.root, text="手動コメント入力（自分で話しかけたい時）").pack()
        f_input = tk.Frame(self.root); f_input.pack()
        tk.Entry(f_input, textvariable=self.manual_input, width=60).pack(side=tk.LEFT)
        tk.Button(f_input, text="送信", command=self.send_manual_input).pack(side=tk.LEFT)

        # ボタン群
        self.start_button = tk.Button(self.root, text="コメント取得を開始", command=self.start_chat)
        self.start_button.pack(pady=5)

        self.stop_button = tk.Button(self.root, text="停止", command=self.stop_chat, state=tk.DISABLED)
        self.stop_button.pack(pady=5)

        self.status_label = tk.Label(self.root, text="状態: 待機中", fg="gray")
        self.status_label.pack(pady=5)

        self.text = tk.Text(self.root, height=20, width=80)
        self.text.pack(pady=5)
        self.text.tag_config("manual", foreground="blue")
        self.text.tag_config("ai", foreground="red")

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
            "index_file_path": self.index_file_path.get().strip(),
            "prompt_file_path": self.prompt_file_path.get().strip(),
            "character_name": self.character_name.get().strip(),
            "pitch_value": self.pitch_value.get(),
            "keyword_filter": self.keyword_filter.get().strip()
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self.text.insert(tk.END, "✅ 設定を保存しました。\n")
        except Exception as e:
            self.text.insert(tk.END, f"❌ 設定保存エラー: {e}\n")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
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
                    self.prompt_file_path.set(config.get("prompt_file_path", ""))
                    self.character_name.set(config.get("character_name", ""))
                    self.pitch_value.set(config.get("pitch_value", 0))
                    self.keyword_filter.set(config.get("keyword_filter", ""))
            except Exception as e:
                self.text.insert(tk.END, f"❌ 設定読み込みエラー: {e}\n")

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

    def select_prompt_file(self):
        path = filedialog.askopenfilename(filetypes=[("プロンプトファイル", "*.txt")])
        if path:
            self.prompt_file_path.set(path)

    def populate_voice_list(self):
        voices = self.engine.getProperty('voices')
        self.voice_list = [v.name for v in voices]
        if voices:
            self.selected_voice.set(voices[0].name)

    def populate_output_devices(self):
        devices = sd.query_devices()
        self.output_device_list = [d['name'] for d in devices if d['max_output_channels'] > 0]
        if self.output_device_list:
            self.selected_output_device.set(self.output_device_list[0])

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
        self.status_label.config(text="停止中", fg="gray")

    def send_manual_input(self):
        text = self.manual_input.get().strip()
        if text:
            self.manual_input.set("")
            sender = "しきさん"
            self.text.insert(tk.END, f"[manual] {sender}: {text}\n")
            reply = self.get_ai_reply(sender, text)
            self.text.insert(tk.END, f"{self.character_name.get()}: {reply}\n")
            threading.Thread(target=self.process_audio, args=(reply,), daemon=True).start()

    def process_audio(self, text):
        if self.use_sapi.get():
            threading.Thread(target=self.speak_text, args=(text,), daemon=True).start()
        if self.use_rvc.get():
            threading.Thread(target=self.run_rvc_tts, args=(text,), daemon=True).start()

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
            sd.default.device = self.selected_output_device.get()
            data, samplerate = sf.read(filepath, dtype='float32')
            sd.play(data, samplerate)
        except Exception as e:
            self.text.insert(tk.END, f"🔇 音声再生エラー: {str(e)}\n")

    def run_rvc_tts(self, text):
        try:
            if not self.tts_rvc:
                self.init_rvc()
            output_path = self.tts_rvc(text=text, pitch=self.pitch_value.get())
            self.text.insert(tk.END, f"🔊 音声出力: {output_path}\n")
            threading.Thread(target=self.play_audio_file, args=(output_path,), daemon=True).start()
        except Exception as e:
            self.text.insert(tk.END, f"RVCエラー: {str(e)}\n")

    def init_rvc(self):
        if not self.voicevox_path.get() or not self.rvc_model_path.get():
            return
        try:
            subprocess.Popen([self.voicevox_path.get()])
            time.sleep(2)
        except Exception as e:
            self.text.insert(tk.END, f"VOICEVOX起動失敗: {e}\n")
        self.tts_rvc = TTS_RVC(
            model_path=self.rvc_model_path.get(),
            index_path=self.index_file_path.get() or "",
            voice="ja-JP-NanamiNeural",
            f0_method="rmvpe",
            output_directory="."
        )

    def read_log_chat(self):
        folder = self.log_folder_path.get().strip()
        if not os.path.isdir(folder):
            self.text.insert(tk.END, "❌ ログフォルダが無効です。\n")
            return

        log_file = self.find_or_create_today_log_file(folder)
        if not log_file:
            self.text.insert(tk.END, "❌ ログファイルが見つかりません。\n")
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

                            if self.should_respond(comment):
                                reply = self.get_ai_reply(sender, comment)
                                self.text.insert(tk.END, f"{self.character_name.get()}: {reply}\n")
                                self.text.see(tk.END)
                                threading.Thread(target=self.process_audio, args=(reply,), daemon=True).start()

                    except Exception as e:
                        self.text.insert(tk.END, f"読み取りエラー: {str(e)}\n")
        except Exception as e:
            self.text.insert(tk.END, f"ファイルオープン失敗: {str(e)}\n")

    def should_respond(self, message):
        if not self.keyword_filter.get().strip():
            return True
        keywords = [k.strip().lower() for k in self.keyword_filter.get().split(",") if k.strip()]
        return any(k in message.lower() for k in keywords)

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

    def get_ai_reply(self, sender, message):
        try:
            with open(self.prompt_file_path.get(), "r", encoding="utf-8") as f:
                prompt = f.read()
        except Exception:
            prompt = (
                "あなたは12歳の元気な少女です。コメントには明るくタメ口で返答してください。\n"
                "・リスナーを傷つけない\n・過激な話題は避けてやんわり断る\n"
                f"\nこれは「{sender}」さんからのコメントだよ。\n"
                "さあ、おしゃべりしてね。"
            )

        if self.get_ai_reply_override:
            if not self.should_respond(message):
                return ""
            # ここで不適切ワード検出なども実装可能
        prompt += f"\nこれは「{sender}」さんからのコメントだよ。\n"

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

# 起動時に同じディレクトリの *.wav を削除
for wav_file in glob.glob("*.wav"):
    try:
        os.remove(wav_file)
    except Exception as e:
        print(f"⚠️ WAV削除失敗: {wav_file} - {e}")

# GUIを起動
if __name__ == "__main__":
    root = tk.Tk()
    app = MultiChatGUI(root)
    root.mainloop()
