import subprocess, sys
n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
ps = [subprocess.Popen([sys.executable, "worker.py", "--port", str(50051 + i)]) for i in range(n)]
try:
    for p in ps: p.wait()
except KeyboardInterrupt:
    for p in ps: p.terminate()
