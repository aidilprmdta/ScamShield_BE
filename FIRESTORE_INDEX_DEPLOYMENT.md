# Firestore Index Deployment Guide

## Problem
Aplikasi tidak bisa menampilkan laporan di admin panel karena missing Firestore composite indexes untuk query `community_reports` collection.

## Required Indexes
File `firestore.indexes.json` sudah diupdate dengan 2 indexes:
1. **Admin Reports Query**: `verifiedStatus` + `createdAt DESC` - untuk filter laporan by status
2. **User Reports Query**: `reportedBy` + `createdAt DESC` - untuk filter laporan by user

## Deployment Steps

### Option 1: Firebase Console (Manual)
1. Buka [Firebase Console](https://console.firebase.google.com/)
2. Pilih project **scamshieldai-9de2170b**
3. Navigasi ke **Firestore Database** → **Indexes** tab
4. Klik **Create Index**
5. Buat 2 indexes berikut:

**Index 1: Admin Reports**
- Collection: `community_reports`
- Fields:
  - `verifiedStatus` - Ascending
  - `createdAt` - Descending
- Query scope: Collection

**Index 2: User Reports**
- Collection: `community_reports`
- Fields:
  - `reportedBy` - Ascending
  - `createdAt` - Descending
- Query scope: Collection

6. Tunggu 5-10 menit sampai status index menjadi "Enabled"

### Option 2: Firebase CLI (Automated)
1. Install Firebase CLI jika belum:
   ```bash
   npm install -g firebase-tools
   ```

2. Login ke Firebase:
   ```bash
   firebase login
   ```

3. Deploy indexes dari `firestore.indexes.json`:
   ```bash
   cd ScamShield_BE
   firebase deploy --only firestore:indexes --project scamshieldai-9de2170b
   ```

4. Verifikasi deployment:
   ```bash
   firebase firestore:indexes --project scamshieldai-9de2170b
   ```

### Verification
Setelah indexes deployed, test dengan:

1. **Test Admin Reports API**:
   ```bash
   curl -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
        http://localhost:8000/api/v1/admin/reports?status=pending
   ```

2. **Test User Reports API**:
   ```bash
   curl -H "Authorization: Bearer YOUR_USER_TOKEN" \
        http://localhost:8000/api/v1/reports/mine
   ```

Jika tidak ada error "The query requires an index", berarti indexes sudah berhasil!

## Troubleshooting

### Error: "The query requires an index"
- Index belum selesai building (tunggu 5-10 menit)
- Atau Firebase CLI deployment gagal, coba manual via console

### Error: "Permission denied"
- Pastikan Firestore rules allow admin/user read access
- Check `firestore.rules` untuk rules configuration

### Index tidak muncul di Console
- Refresh halaman Firebase Console
- Check project ID benar: `scamshieldai-9de2170b`
