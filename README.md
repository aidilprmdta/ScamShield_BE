# ScamShield AI — Backend

FastAPI API untuk analisis chat, link (heuristik + URLhaus + Gemini), QR, auth Firebase, riwayat, dan edukasi.

## Prasyarat

- Python 3.11+
- `GEMINI_API_KEY` dari [Google AI Studio](https://aistudio.google.com/)
- (Opsional) Firebase service account untuk Auth / riwayat

## Install

```bash
cd ScamShield_BE
python -m venv venv
venv\Scripts\Activate.ps1          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env         # macOS/Linux: cp .env.example .env
```

Isi `.env` minimal: `GEMINI_API_KEY`. Untuk login/riwayat, isi juga `FIREBASE_*` (lihat `.env.example`).

## Jalankan

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- API: http://127.0.0.1:8000  
- Docs: http://127.0.0.1:8000/docs  

`--host 0.0.0.0` agar emulator/HP bisa akses (mis. `http://192.168.x.x:8000`).

```bash
# Docker (opsional)
docker build -t scamshield-backend .
docker run --env-file .env -p 8000:8000 scamshield-backend
```
