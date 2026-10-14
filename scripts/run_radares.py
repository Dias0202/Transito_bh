"""Process every radar month not yet in data/processed/radares (resumable).

    python scripts/run_radares.py data/interim/radar_zip > radares.log 2>&1
"""
import sys
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bhtraffic.ingest import radares  # noqa: E402

work = Path(sys.argv[1])
work.mkdir(parents=True, exist_ok=True)
archives = radares.list_archives()
for name in archives:
    if radares.is_done(name):
        print("skip", name, flush=True)
        continue
    t = time.time()
    try:
        out = radares.build_month(name, work)
        print(f"ok {name} {time.time()-t:.0f}s -> {out.name}", flush=True)
    except Exception:
        print(f"FAILED {name}", flush=True)
        traceback.print_exc()
missing = [n for n in archives if not radares.is_done(n)]
print("DONE", len(archives) - len(missing), "of", len(archives), "missing:", missing, flush=True)
