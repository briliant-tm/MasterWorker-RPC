import argparse, threading
from flask import Flask, jsonify, request
from master import Master

ap = argparse.ArgumentParser()
ap.add_argument("--workers", required=True, help="host:port,host:port,...")
ap.add_argument("--port", type=int, default=5000)
a = ap.parse_args()
M = Master(a.workers.split(","))
app = Flask(__name__)
HTML = open("index.html", encoding="utf-8").read()

def rentang(d):
    mulai, akhir = max(1, int(d.get("mulai", 1))), min(10_000_000, int(d.get("akhir", 1_000_000)))
    return mulai, akhir

@app.get("/")
def index(): return HTML

@app.get("/api/workers")
def workers(): return jsonify(M.status_worker())

@app.post("/api/jobs")
def buat():
    d = request.get_json(force=True)
    hidup = [w["alamat"] for w in M.status_worker() if w["hidup"]]
    if not hidup: return jsonify(error="Tidak ada worker aktif"), 503
    mulai, akhir = rentang(d)
    if mulai > akhir: return jsonify(error="Rentang tidak valid"), 400
    n = max(1, min(int(d.get("worker", len(hidup))), len(hidup)))
    return jsonify(id=M.mulai_job(mulai, akhir, hidup[:n], max(1, int(d.get("tugas", 60)))))

@app.get("/api/jobs/<jid>")
def lihat(jid):
    d = M.lihat(jid)
    return (jsonify(d), 200) if d else (jsonify(error="Job tidak ada"), 404)

@app.post("/api/speedup")
def speedup():
    if M.bench["berjalan"]: return jsonify(error="Sedang berjalan"), 409
    mulai, akhir = rentang(request.get_json(force=True))
    threading.Thread(target=M.speedup, args=(mulai, akhir), daemon=True).start()
    return jsonify(ok=True)

@app.get("/api/speedup")
def hasil_speedup(): return jsonify(M.bench)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=a.port, threaded=True)
