# Google Meet Voice Bot with Recall.ai and Pipecat

リアルタイム音声会話ボットシステム - Google Meet にボットが入室し、参加者とリアルタイム会話を行います。

## システム構成

- **Recall.ai**: Google Meet への入室とメディア入出力
- **Pipecat**: STT/LLM/TTS パイプライン
- **WebSocket**: リアルタイム音声データ通信 (PCM 16kHz/16bit/mono)

## ディレクトリ構造

```
├── server/          # Python FastAPI WebSocketサーバー + Pipecatパイプライン
├── client/          # Recall.ai用Webページ (音声キャプチャ・再生)
├── scripts/         # Recall.ai Bot管理スクリプト
├── configs/         # 環境設定・ペルソナ設定
└── README.md
```

## セットアップ

### 必要な環境
- Python 3.10+
- Node.js 18+
- 各種APIキー (.env設定)

### インストール

```bash
# サーバー環境セットアップ
cd server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# クライアント環境セットアップ
cd ../client
npm install
```

### 実行

```bash
# サーバー起動
cd server
python main.py

# クライアント開発サーバー起動
cd client
npm run dev
```

## 音声仕様

- **フォーマット**: PCM 16,000 Hz / 16-bit / mono / little-endian
- **送受信単位**: 20ms (320サンプル)
- **WebSocket**: バイナリ=PCM, テキスト=制御JSON

## 対応プロバイダ

- **STT**: Deepgram / Google STT / Whisper
- **LLM**: OpenAI / Anthropic
- **TTS**: Cartesia / ElevenLabs

## 受入基準

- Google Meet URL指定でRecall.ai Bot入室 (30秒以内)
- 参加者発話に2秒以内で応答
- 5分連続対話で安定動作
- Windows & Ubuntu 両対応
