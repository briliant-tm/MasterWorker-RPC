import argparse, os, threading, time
from concurrent import futures
import grpc
import komputasi_pb2 as pb
import komputasi_pb2_grpc as pbg

def prima(n):  # uji pembagian (sengaja CPU-bound agar speedup terlihat)
    if n < 4: return n > 1
    if n % 2 == 0 or n % 3 == 0: return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0: return False
        i += 6
    return True

class Worker(pbg.WorkerServicer):
    def __init__(self, wid):
        self.wid, self.lock = wid, threading.Lock()
        self.hasil = {}      # request_id -> Progres akhir (deduplikasi / at-most-once)
        self.batal, self.jalan, self.total = set(), 0, 0

    def Ping(self, req, ctx):
        return pb.InfoWorker(worker_id=self.wid, cpu=os.cpu_count() or 1)

    def Info(self, req, ctx):
        with self.lock:
            return pb.StatusWorker(selesai=len(self.hasil), sedang_jalan=self.jalan, total_bilangan=self.total)

    def Batal(self, req, ctx):
        with self.lock: self.batal.add(req.request_id)
        return pb.Balasan(sukses=True, pesan="Pembatalan dicatat")

    def HitungPrima(self, req, ctx):
        with self.lock:
            if req.request_id in self.hasil:       # permintaan duplikat (retry): kirim hasil lama
                yield self.hasil[req.request_id]; return
            self.jalan += 1
        t0, jumlah, terbesar = time.perf_counter(), 0, 0
        total = req.akhir - req.mulai
        langkah = max(1, total // 20)
        try:
            for awal in range(req.mulai, req.akhir, langkah):
                for n in range(awal, min(awal + langkah, req.akhir)):
                    if prima(n): jumlah, terbesar = jumlah + 1, n
                if req.request_id in self.batal or not ctx.is_active():
                    ctx.abort(grpc.StatusCode.CANCELLED, "Tugas dibatalkan")
                p = (min(awal + langkah, req.akhir) - req.mulai) / total
                if p < 1:
                    yield pb.Progres(persen=p * 100, jumlah_prima=jumlah, worker_id=self.wid)
            akhir = pb.Progres(persen=100, selesai=True, jumlah_prima=jumlah, prima_terbesar=terbesar,
                               durasi=time.perf_counter() - t0, worker_id=self.wid)
            with self.lock:
                self.hasil[req.request_id] = akhir
                self.total += total
            yield akhir
        finally:
            with self.lock: self.jalan -= 1

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--port", type=int, default=50051)
    ap.add_argument("--id"); a = ap.parse_args()
    s = grpc.server(futures.ThreadPoolExecutor(max_workers=32))
    pbg.add_WorkerServicer_to_server(Worker(a.id or f"worker-{a.port}"), s)
    s.add_insecure_port(f"0.0.0.0:{a.port}"); s.start()
    print(f"Worker berjalan di port {a.port}"); s.wait_for_termination()
