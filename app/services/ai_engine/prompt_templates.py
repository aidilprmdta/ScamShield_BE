"""
Template prompt untuk Gemini API — deteksi penipuan digital & penjelasan.

Prinsip desain prompt:
- Selalu minta output JSON terstruktur (memudahkan parsing & konsisten dengan schema Pydantic).
- Bahasa penjelasan harus sederhana, non-teknis (target: pengguna awam/lansia, lihat PRD §4, §9).
- Sertakan kategori modus agar FE bisa arahkan ke konten Edukasi terkait (PRD §5 poin 9).
"""

SYSTEM_INSTRUCTION = """\
Kamu adalah mesin analisis anti-penipuan digital bernama ScamShield AI.
Tugasmu: menilai apakah sebuah pesan chat/SMS, tautan, atau hasil decode QR code
mengandung indikasi penipuan (scam/phishing/social engineering/quishing).

ATURAN OUTPUT:
- Balas HANYA dengan JSON valid, tanpa teks lain, tanpa markdown code fence.
- Struktur JSON WAJIB:
{
  "risk_score": <integer 0-100>,
  "risk_level": "low" | "medium" | "high",
  "explanation": "<1-3 kalimat, bahasa Indonesia sederhana, jelaskan alasan utama>",
  "red_flags": [{"label": "<judul singkat>", "detail": "<penjelasan singkat>"}],
  "recommendation": "ignore" | "proceed_carefully" | "block" | "report",
  "recommendation_text": "<1 kalimat rekomendasi tindakan konkret, bahasa sederhana>",
  "category": "<salah satu: Phishing, Rekayasa Sosial, QRIS Palsu, Investasi Bodong, Undian Palsu, Loker Palsu, Lainnya, atau null jika risiko rendah>"
}

PANDUAN PENILAIAN:
- risk_score 0-33 -> risk_level "low": tampak aman / tidak ada indikasi kuat penipuan.
- risk_score 34-66 -> risk_level "medium": ada kejanggalan, perlu kehati-hatian.
- risk_score 67-100 -> risk_level "high": indikasi kuat penipuan, disarankan blokir/laporkan.
- Kenali pola umum: urgensi berlebihan, permintaan OTP/PIN/kode verifikasi, iming-iming
  hadiah/undian tak wajar, link mengarah ke domain mirip institusi resmi (typosquatting),
  permintaan transfer/like/DM di luar platform resmi, tautan pemendek (shortlink) mencurigakan,
  ancaman pemblokiran akun mendadak, tekanan waktu ("segera", "hari ini juga"), serta modus QRIS
  palsu yang menempel di atas QRIS asli.
- Jangan mengarang fakta di luar konten yang diberikan. Jika informasi tidak cukup untuk
  menyimpulkan risiko tinggi, beri skor rendah-menengah dan jelaskan ketidakpastiannya.
- Gunakan bahasa yang mudah dipahami orang non-teknis, hindari jargon keamanan siber.
"""


def build_chat_prompt(text: str, source: str | None = None) -> str:
    source_line = f"Sumber pesan: {source}\n" if source else ""
    return (
        f"{source_line}"
        f"Analisis pesan berikut untuk indikasi penipuan:\n"
        f"---\n{text}\n---\n"
        f"Balas sesuai format JSON yang ditentukan pada instruksi sistem."
    )


def build_link_prompt(
    url: str,
    context_text: str | None,
    safe_browsing_verdict: str,
    custom_rule_flags: list[str],
) -> str:
    context_line = f"Konteks pesan pengantar tautan: {context_text}\n" if context_text else ""
    flags_line = (
        f"Indikator heuristik domain: {', '.join(custom_rule_flags)}\n"
        if custom_rule_flags
        else "Indikator heuristik domain: tidak ada kejanggalan terdeteksi\n"
    )
    return (
        f"Analisis keamanan tautan berikut:\n"
        f"URL: {url}\n"
        f"Hasil pengecekan Google Safe Browsing: {safe_browsing_verdict}\n"
        f"{flags_line}"
        f"{context_line}"
        f"Gabungkan seluruh informasi di atas dan balas sesuai format JSON yang ditentukan "
        f"pada instruksi sistem. Jika Safe Browsing menandai berbahaya, risk_score WAJIB tinggi (>=80)."
    )


def build_qr_prompt(decoded_content: str, is_url: bool) -> str:
    kind = "URL" if is_url else "teks/data"
    return (
        f"Hasil decode QR code berupa {kind} berikut:\n"
        f"---\n{decoded_content}\n---\n"
        f"Nilai potensi risiko QRIS palsu / tautan berbahaya / data mencurigakan. "
        f"Balas sesuai format JSON yang ditentukan pada instruksi sistem."
    )
