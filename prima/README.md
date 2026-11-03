# Master–Worker Bilangan Prima (gRPC + Web)

Menghitung jumlah bilangan prima 1–10.000.000. Master membagi rentang menjadi banyak tugas dan memanggil 3+ worker **secara paralel** via gRPC. Antarmuka web dapat dibuka dari laptop/HP mana pun.

## Arsitektur (2 komputer)
```
 Komputer A (server)                       Komputer B
 ┌───────────────────────┐   gRPC     ┌──────────────────────┐
 │ app.py = Master + Web │ ─────────▶ │ worker :50051        │
 │ (Flask :5000)         │ ─────────▶ │ worker :50052        │
 └───────────▲───────────┘ ─────────▶ │ worker :50053        │
             │ HTTP                    └──────────────────────┘
   Browser (komputer B / HP / laptop lain)
```
Opsional: tambahkan worker ke-4 di Komputer A (`python worker.py --port 50054`).

## Instalasi (kedua komputer, Python 3.10+)
```
python3 -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. komputasi.proto
```

## Menjalankan
1. **Komputer B** (worker): `python start_workers.py 3` (port 50051–50053). Cek IP-nya, mis. `192.168.1.20`.
2. **Komputer A** (master + web): `python app.py --workers 192.168.1.20:50051,192.168.1.20:50052,192.168.1.20:50053`
3. Buka `http://IP_KOMPUTER_A:5000` dari browser perangkat apa pun di jaringan yang sama.
4. Izinkan port 50051–50053 (B) dan 5000 (A) di firewall. Satu komputer saja untuk uji awal: pakai `localhost`.

## Uji kinerja (untuk laporan)
`python benchmark.py http://IP_KOMPUTER_A:5000` → tabel latensi/throughput untuk 1, 5, 20 klien dan tabel speedup (waktu 1 worker ÷ waktu N worker). Setiap job diverifikasi: π(200.000) harus 17.984, sehingga data rusak akibat race condition akan terdeteksi. Hasil akhir 1–10.000.000 harus **664.579**.

## Pemetaan ke rubrik
| Aspek | Implementasi |
|---|---|
| Desain .proto | 4 RPC: `Ping`, `Info`, `Batal` (unary), `HitungPrima` (server streaming: progres lalu hasil) |
| Fungsionalitas | Master paralel ke 3+ worker, penggabungan hasil, speedup, UI web, jalan di 2 mesin |
| Concurrency | `Master.lock` melindungi state job; `Worker.lock` melindungi cache/statistik; worker memakai thread pool 32; antrian tugas `queue.Queue` thread-safe; diuji `benchmark.py` |
| Toleransi kegagalan | Timeout 300 s, retry 3× dengan exponential backoff, `request_id` (`job-tugas`) + cache hasil di worker (deduplikasi/at-most-once), failover: tugas worker mati dikembalikan ke antrian dan diambil worker lain |
| Analisis kinerja | `benchmark.py` + tombol speedup di UI |

Demo failover: mulai job besar, matikan satu worker (Ctrl+C), job tetap selesai dan UI menandai worker "mati".

## Catatan analisis
- Pembagian dinamis (60 tugas kecil, bukan 3 potongan besar) karena bilangan besar lebih mahal diuji; potongan statis membuat worker terakhir jadi bottleneck.
- Speedup dibatasi jumlah core fisik, overhead gRPC, dan bagian sekuensial (pembagian tugas, penggabungan). Cek efisiensi = speedup ÷ N.
- Cache dedup ada di memori: jika worker restart, jaminan at-most-once hilang (sebutkan di laporan; perbaikan: simpan ke disk/DB).
- Gunakan komputer A, B dengan jaringan yang sama. Alamat worker dapat berupa IP atau hostname.
