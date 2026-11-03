import copy, queue, threading, time, uuid
import grpc
import komputasi_pb2 as pb
import komputasi_pb2_grpc as pbg

class Master:
    def __init__(self, alamat):
        self.alamat = alamat
        self.stubs = {a: pbg.WorkerStub(grpc.insecure_channel(a)) for a in alamat}
        self.jobs, self.lock = {}, threading.Lock()   # lock melindungi state job bersama
        self.bench = {"berjalan": False, "hasil": []}

    def status_worker(self):
        out = []
        for a, s in self.stubs.items():
            try:
                i, st = s.Ping(pb.Kosong(), timeout=1), s.Info(pb.Kosong(), timeout=1)
                out.append(dict(alamat=a, hidup=True, cpu=i.cpu, selesai=st.selesai))
            except grpc.RpcError:
                out.append(dict(alamat=a, hidup=False))
        return out

    def mulai_job(self, mulai, akhir, alamat, jumlah_tugas=60):
        akhir += 1                                    # [mulai, akhir] -> setengah terbuka
        langkah = max(1, -(-(akhir - mulai) // jumlah_tugas))
        antrian = queue.Queue()
        for i, a in enumerate(range(mulai, akhir, langkah)):
            antrian.put((i, a, min(a + langkah, akhir)))
        jid = uuid.uuid4().hex[:8]
        job = dict(id=jid, status="berjalan", total_tugas=antrian.qsize(), selesai=0, prima=0, terbesar=0,
                   retry=0, durasi=None, t0=time.perf_counter(),
                   worker={a: dict(tugas=0, hidup=True) for a in alamat})
        self.jobs[jid] = job
        threading.Thread(target=self._jalankan, args=(job, antrian, alamat), daemon=True).start()
        return jid

    def _jalankan(self, job, antrian, alamat):
        ts = [threading.Thread(target=self._loop, args=(job, antrian, a)) for a in alamat]
        for t in ts: t.start()          # worker dipanggil PARALEL
        for t in ts: t.join()
        with self.lock:
            job["durasi"] = time.perf_counter() - job["t0"]
            job["status"] = "selesai" if job["selesai"] == job["total_tugas"] else "gagal"

    def _loop(self, job, antrian, alamat):    # load balancing dinamis: worker cepat ambil lebih banyak tugas
        w = job["worker"][alamat]
        while True:
            try: t = antrian.get_nowait()
            except queue.Empty:
                if job["selesai"] >= job["total_tugas"]: return
                time.sleep(0.2); continue     # tunggu: mungkin ada tugas dikembalikan worker yang mati
            h = self._panggil(alamat, job, t)
            if h is None:                     # failover: kembalikan tugas, tandai worker mati
                antrian.put(t); w["hidup"] = False; return
            with self.lock:
                job["selesai"] += 1; job["prima"] += h.jumlah_prima
                job["terbesar"] = max(job["terbesar"], h.prima_terbesar); w["tugas"] += 1

    def _panggil(self, alamat, job, t, maks=3):
        rid = f"{job['id']}-{t[0]}"           # ID sama di setiap percobaan -> dedup di worker
        for p in range(1, maks + 1):
            try:
                akhir = None
                for pr in self.stubs[alamat].HitungPrima(pb.Tugas(request_id=rid, mulai=t[1], akhir=t[2]), timeout=300):
                    akhir = pr
                if akhir and akhir.selesai: return akhir
            except grpc.RpcError as e:
                if e.code() not in (grpc.StatusCode.UNAVAILABLE, grpc.StatusCode.DEADLINE_EXCEEDED): return None
            with self.lock: job["retry"] += 1
            if p < maks: time.sleep(0.5 * 2 ** (p - 1))   # exponential backoff
        return None

    def lihat(self, jid):
        with self.lock:
            j = self.jobs.get(jid)
            if not j: return None
            d = copy.deepcopy(j)
        d["waktu"] = d["durasi"] if d["durasi"] is not None else time.perf_counter() - d["t0"]
        return d

    def tunggu(self, jid):
        while (d := self.lihat(jid))["status"] == "berjalan": time.sleep(0.2)
        return d

    def speedup(self, mulai, akhir):
        self.bench = {"berjalan": True, "hasil": []}
        hidup = [w["alamat"] for w in self.status_worker() if w["hidup"]]
        base = None
        for n in range(1, len(hidup) + 1):
            d = self.tunggu(self.mulai_job(mulai, akhir, hidup[:n]))
            base = base or d["waktu"]
            sp = base / d["waktu"]
            self.bench["hasil"].append(dict(worker=n, waktu=round(d["waktu"], 2), speedup=round(sp, 2),
                                            efisiensi=round(sp / n * 100), prima=d["prima"]))
        self.bench["berjalan"] = False
