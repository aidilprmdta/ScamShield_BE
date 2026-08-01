"""
Skrip untuk mengisi (seed) koleksi `education_content` di Firestore
dari data/education_seed.json — sekali jalan saat setup awal proyek.

Cara pakai:
    python scripts/seed_education_content.py

Membutuhkan FIREBASE_SERVICE_ACCOUNT_JSON sudah dikonfigurasi di .env
(lihat app/core/config.py).
"""
import json
import sys
from pathlib import Path

# Agar bisa import "app.*" saat dijalankan langsung sebagai skrip
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.logging import get_logger, setup_logging  # noqa: E402
from app.repositories.firestore_repository import (  # noqa: E402
    EDUCATION_CONTENT_COLLECTION,
    _get_db,
    init_firebase,
)

setup_logging()
logger = get_logger("seed_education_content")

SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "education_seed.json"


def main() -> None:
    init_firebase()
    db = _get_db()

    items = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    logger.info("Menyiapkan %d dokumen education_content...", len(items))

    batch = db.batch()
    for item in items:
        doc_id = item.pop("id")
        ref = db.collection(EDUCATION_CONTENT_COLLECTION).document(doc_id)
        batch.set(ref, item, merge=True)

    batch.commit()
    logger.info("Selesai. %d dokumen ditulis ke koleksi '%s'.", len(items), EDUCATION_CONTENT_COLLECTION)


if __name__ == "__main__":
    main()
