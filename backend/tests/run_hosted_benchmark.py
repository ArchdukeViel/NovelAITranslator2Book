import ssl
import statistics
import time
import urllib.request

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

base = "https://laptop-akmalpellu.tail0b4e3e.ts.net"

endpoints = [
    ("Catalog (GET /api/public/catalog)", f"{base}/api/public/catalog", 500, 250 * 1024),
    ("Novel Detail (GET /api/public/novels/n2056dn)", f"{base}/api/public/novels/n2056dn", 300, 100 * 1024),
    (
        "Chapter (GET /api/public/novels/n2056dn/chapters/1)",
        f"{base}/api/public/novels/n2056dn/chapters/1",
        750,
        1024 * 1024,
    ),
]

print("Starting warmup...", flush=True)
for _name, url, _, _ in endpoints:
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, context=ctx) as resp:
        resp.read()
print("Warmup complete. Running 20 samples per endpoint...", flush=True)

# 20 samples per endpoint
results = {}
for name, url, budget_p95, budget_size in endpoints:
    durations = []
    sizes = []
    for i in range(20):
        t0 = time.perf_counter()
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, context=ctx) as resp:
            data = resp.read()
            durations.append((time.perf_counter() - t0) * 1000.0)
            sizes.append(len(data))
        print(f"  {name} sample {i + 1}: {durations[-1]:.1f} ms", flush=True)

    durations.sort()
    p50 = statistics.median(durations)
    p95_idx = int(len(durations) * 0.95)
    p95 = durations[p95_idx]
    avg_size = statistics.mean(sizes)
    results[name] = {
        "p50": p50,
        "p95": p95,
        "min": durations[0],
        "max": durations[-1],
        "budget_p95": budget_p95,
        "avg_size_kb": avg_size / 1024.0,
        "budget_size_kb": budget_size / 1024.0,
        "pass": p95 <= budget_p95 and avg_size <= budget_size,
    }

print("\n=== HOSTED ENDPOINT BENCHMARK RESULTS ===", flush=True)
for name, r in results.items():
    status = "PASS" if r["pass"] else "FAIL"
    print(f"{name}:", flush=True)
    print(f"  Status: {status}", flush=True)
    print(
        f"  Latency p50: {r['p50']:.1f} ms | p95: {r['p95']:.1f} ms (Budget: <= {r['budget_p95']} ms) | range: [{r['min']:.1f} ms, {r['max']:.1f} ms]",
        flush=True,
    )
    print(f"  Payload: {r['avg_size_kb']:.2f} KiB (Budget: <= {r['budget_size_kb']:.2f} KiB)", flush=True)
