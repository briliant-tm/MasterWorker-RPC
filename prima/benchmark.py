"""Uji kinerja lewat HTTP. Pakai: python benchmark.py http://IP_MASTER:5000"""
import json, statistics, sys, time, urllib.request as u
from concurrent.futures import ThreadPoolExecutor
B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5000"
AKHIR_KECIL, PRIMA_KECIL = 200_000, 17984   # pi(200000) = 17984 (cek kebenaran hasil)

def req(path, body=None):
    r = u.Request(B + path, data=None if body is None else json.dumps(body).encode(),
                  headers={"Content-Type": "application/json"})
    return json.load(u.urlopen(r, timeout=120))

def klien(_):
    lat = []
    for _ in range(3):
        t = time.perf_counter()
        jid = req("/api/jobs", {"mulai": 1, "akhir": AKHIR_KECIL, "tugas": 6})["id"]
        while (s := req("/api/jobs/" + jid))["status"] == "berjalan": time.sleep(0.1)
        assert s["prima"] == PRIMA_KECIL, f"DATA RUSAK: {s['prima']}"
        lat.append(time.perf_counter() - t)
    return lat

print("## Latensi & throughput (3 job/klien)\n| Klien | Latensi rata-rata (s) | Throughput (job/s) |\n|---|---|---|")
for n in (1, 5, 20):
    t = time.perf_counter()
    with ThreadPoolExecutor(n) as ex: lat = [x for l in ex.map(klien, range(n)) for x in l]
    print(f"| {n} | {statistics.mean(lat):.2f} | {len(lat) / (time.perf_counter() - t):.2f} |")

print("\n## Speedup (rentang 1..N dari UI, default 2.000.000)")
req("/api/speedup", {"mulai": 1, "akhir": 2_000_000})
while (r := req("/api/speedup"))["berjalan"] or not r["hasil"]: time.sleep(2)
print("| Worker | Waktu (s) | Speedup | Efisiensi |\n|---|---|---|---|")
for x in r["hasil"]: print(f"| {x['worker']} | {x['waktu']} | {x['speedup']}x | {x['efisiensi']}% |")
