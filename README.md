# ScamShield AI — Backend (FastAPI)

Backend REST API untuk **ScamShield AI**, mengorkestrasi AI Analysis (Gemini API),
pengecekan tautan (Google Safe Browsing + heuristik custom), penyimpanan riwayat
(Firestore), pelaporan komunitas, dan konten edukasi literasi digital.

Dibangun mengikuti struktur folder & alur pada PRD ScamShield AI §13–§18.

## 1. Fitur / Endpoint

| Method | Endpoint | Fungsi |
|---|---|---|
| POST | `/api/v1/analyze/chat` | Analisis teks chat/SMS (input langsung atau hasil OCR screenshot) |
| POST | `/api/v1/analyze/link` | Cek keamanan URL: Safe Browsing + heuristik domain/shortlink + LLM |
| POST | `/api/v1/analyze/qr` | Analisis hasil decode QR code (otomatis dialihkan ke pipeline link bila berupa URL) |
| GET | `/api/v1/history` | Riwayat analisis milik pengguna login (butuh Firebase ID token) |
| DELETE | `/api/v1/history/{id}` | Hapus satu riwayat |
| POST | `/api/v1/report` | Kirim laporan komunitas atas modus baru |
| GET | `/api/v1/education` | Daftar artikel/kuis literasi digital (filter `?category=`) |
| GET | `/api/v1/education/{id}` | Detail satu artikel/simulasi |
| GET | `/health` | Health check |

Dokumentasi interaktif otomatis tersedia di `/docs` (Swagger UI) dan `/redoc` setelah server berjalan.

## 2. Menjalankan Secara Lokal

```bash
# 1. Buat virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Salin & isi environment variables
cp .env.example .env
# isi GEMINI_API_KEY, GOOGLE_SAFE_BROWSING_API_KEY, FIREBASE_SERVICE_ACCOUNT_JSON

# 4. Jalankan server (auto-reload untuk development)
# --host 0.0.0.0 agar bisa diakses dari device di jaringan yang sama
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Server berjalan di http://192.168.1.8:8000 (ganti IP sesuai mesin Anda)
# Swagger docs: http://192.168.1.8:8000/docs
```

## 3. Environment Variables

Lihat `.env.example`. Ringkasan:

- `GEMINI_API_KEY` — API key dari Google AI Studio.
- `GEMINI_MODEL` — default `gemini-flash-latest`; cek model terbaru di
  https://ai.google.dev/gemini-api/docs/models (Gemini 1.5 sudah deprecated per 2026).
- `GOOGLE_SAFE_BROWSING_API_KEY` — API key Safe Browsing v4 dari Google Cloud Console.
- `FIREBASE_SERVICE_ACCOUNT_JSON` — path ke file service-account JSON, **atau** isi JSON
  itu sendiri sebagai string.
- Tanpa `GOOGLE_SAFE_BROWSING_API_KEY`, endpoint link/QR tetap berjalan (fallback "tidak
  dapat diperiksa") — LLM tetap menganalisis berdasarkan heuristik domain.
- Tanpa `FIREBASE_SERVICE_ACCOUNT_JSON`, endpoint `analyze/*` tetap berjalan tapi riwayat
  tidak tersimpan; endpoint `history`, `report`, `education` akan mengembalikan error 503/401.

## 4. Menjalankan dengan Docker

```bash
docker build -t scamshield-backend .
docker run --env-file .env -p 8000:8000 scamshield-backend
```

## 5. Testing

```bash
pytest -v
```

Test mencakup: validasi input, penggabungan skor risiko (risk_scorer), cache hasil
analisis, serta endpoint `analyze/chat` dan `analyze/link` (dengan Gemini & Safe Browsing
di-mock, sehingga tidak memerlukan API key sungguhan untuk lulus).

## 6. Autentikasi

Autentikasi menggunakan **Firebase ID Token** (didapat dari Firebase Auth SDK di sisi
Android). Kirim di header:

```
Authorization: Bearer <firebase_id_token>
```

- Endpoint `analyze/*` dan `report`: login **opsional** — bisa dipakai tanpa akun (tamu),
  riwayat hanya tersimpan dengan `userId` bila login.
- Endpoint `history`: login **wajib**.

## 7. Struktur Proyek

```
app/
├── main.py                 # entry point FastAPI
├── core/                   # config, security (verifikasi Firebase token), logging
├── api/v1/                 # router & endpoint per fitur
├── services/
│   ├── ai_engine/           # wrapper Gemini API + prompt templates
│   ├── link_check/          # Safe Browsing client + heuristik custom
│   └── risk_engine/         # penggabung skor risiko akhir
├── models/                  # Pydantic request/response schemas
├── repositories/            # akses Firestore
└── utils/                   # exceptions & validators
tests/                       # unit & endpoint tests (pytest)
```

## 8. Cache Hasil Analisis

Untuk mitigasi rate-limit dan biaya Gemini API yang membengkak (PRD §11), backend
menyimpan cache in-memory (TTL, default 1 jam — atur via `ANALYSIS_CACHE_TTL_SECONDS`)
untuk prompt yang identik. Cache ini per-proses; untuk deployment multi-instance,
ganti `app/core/cache.py` dengan Redis (interface `cache_get`/`cache_set` sudah didesain
agar mudah diswap).

## 9. Firestore: Rules, Indexes & Seed Data

- `firestore.rules` — aturan akses (pemilik data untuk `scan_history` &
  `user_education_progress`, publik read-only untuk `education_content`, dst).
- `firestore.indexes.json` — composite index yang dibutuhkan query `history`
  (`userId ==` + `order by created_at`) dan filter kategori edukasi.
- Deploy keduanya (butuh Firebase CLI):
  ```bash
  firebase deploy --only firestore:rules,firestore:indexes
  ```
- Isi awal konten edukasi (artikel & kuis) tersedia di `data/education_seed.json`.
  Jalankan sekali untuk mengisi Firestore:
  ```bash
  python scripts/seed_education_content.py
  ```

## 10. Catatan Keamanan & Privasi

- OCR screenshot dilakukan **on-device** di aplikasi Android (ML Kit) — backend hanya
  menerima teks hasil OCR, bukan gambar mentah, sehingga privasi pengguna lebih terjaga
  (lihat PRD §16 catatan privasi).
- Jangan commit `.env`, `firebase-service-account*.json`, atau `google-services.json` ke
  repository publik — sudah dimasukkan ke `.gitignore`.
