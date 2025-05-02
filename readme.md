# AIVC コメントリアクター（Ver 0.1）

AIVC コメントリアクターは、YouTubeやツイキャスの配信コメントをリアルタイムで読み取り、ChatGPTを通じてAIキャラクターが返答＆音声読み上げするツールです。  
特にVTuber向けに設計されており、「相沢秋希」のようなAIキャラと一緒に配信に参加することができます。

---

## 🧑‍💻 対象ユーザー

- VTuber・配信者
- コメント読み上げ＋リアクションをAIに任せたい方
- 音声合成（VOICEVOX + RVC）を利用した読み上げに興味がある方

---

## 🪟 動作環境

- Windows 10 以降（VOICEVOXがWindows専用のため）
- Python 3.10〜3.12 推奨
- NVIDIA GPU（RVC使用時に推奨、ただしCPUでも動作可）

---

## 🧱 必要なツール・依存環境

### 1. Python 仮想環境を作成・依存関係をインストール

```powershell
git clone https://github.com/lsm910809/AIVC.git
cd aivc-comment-reactor
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python src/main.py
```

### 2. VOICEVOX エンジンをインストール（Windows専用）

- ウンロードページ：https://voicevox.hiroshiba.jp/
- インストール後、VOICEVOXの実行ファイルのパスをGUIで指定してください。

### 3. OneComme（わんコメ）をインストールし、ログ出力を有効化

- ダウンロードページ：https://onecomme.com/
- コメントログを .log ファイルに出力する設定が必要です

    - https://onecomme.com/docs/feature/comment-log

    - わんコメ起動後、右上メニューから「設定」を開く
「高度な設定」→「コメント保存」
保存先フォルダを指定（このフォルダをGUIで読み込み対象にする）
- 設定後、GUI画面で、ログファイルのパスを指定してください。

## 📁 必須ファイル

- prompt_aki.txt
    - サンプルプロンプト。任意のキャラクターに合わせて修正・追加できます。
- settings.json
    - GUIで自動保存されます。このファイルは公開しないでください（.gitignore 推奨）

## 🗣 特徴

- GUIで簡単にAPIキーや音声設定を入力
- コメントから AI が自動返信（GPT-4対応）
- VOICEVOXやRVCによる自然な音声出力
- 呼びかけキーワードに応じて反応（例：「秋希」「aki」「아키」など）
- ピッチ変更スライダー付き
- 手動入力欄から任意のメッセージを送信可能
- WAVファイルは起動時に自動削除されます

## ❗ 注意事項

- 本ツールは日本語環境での使用を前提としています。This tool is for Japanese language users only.
- OpenAIのAPIキーが必要です（有料）。
- VOICEVOXはWindows専用です。
- settings.json に含まれる情報（APIキーなど）は絶対にGitで公開しないでください。

## ライセンス
- このプロジェクトは [MITライセンス](https://opensource.org/licenses/MIT) のもとで公開されています。

## 📄 クレジット

- ChatGPT (OpenAI)
- VOICEVOX（©ヒロシバ）
- tts-with-rvc
- OneComme（©Andy氏）

## 🤖 制作・設計

- このツールは、VTuber「相川志希」プロジェクトの一環として制作されました。
- キャラクター「相沢秋希」との連携をベースに設計されていますが、任意のキャラクター用にプロンプトを自由に作成・設定できます。