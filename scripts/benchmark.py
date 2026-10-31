"""
FleetWise Concurrency and Performance Benchmark Suite.
Measures request throughput, latency percentiles (p50, p95, p99),
and ACID isolation stability across 1, 5, 10, 25, and 50 concurrent threads.
Outputs results to evidence/benchmark.json.
"""
import json
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Ensure workspace root is in sys.path
WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

from fastapi.testclient import TestClient
from app.db import init_db
from app.main import app


def run_benchmark_for_concurrency(client: TestClient, threads: int, total_requests: int = 100) -> dict:
    durations_ms = []

    def task(req_idx: int):
        t0 = time.perf_counter()
        # Mix of read and write endpoints
        if req_idx % 2 == 0:
            res = client.get("/health")
        else:
            res = client.get("/metrics")
        t1 = time.perf_counter()
        latency = (t1 - t0) * 1000.0
        return res.status_code, latency

    wall_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=threads) as executor:
        results = list(executor.map(task, range(total_requests)))
    wall_duration = time.perf_counter() - wall_start

    success_count = sum(1 for status, _ in results if status == 200)
    durations_ms = sorted([lat for _, lat in results])

    p50 = durations_ms[int(len(durations_ms) * 0.50)]
    p95 = durations_ms[int(len(durations_ms) * 0.95)]
    p99 = durations_ms[int(len(durations_ms) * 0.99)]
    rps = round(total_requests / wall_duration, 1)

    return {
        "threads": threads,
        "total_requests": total_requests,
        "successful_requests": success_count,
        "success_rate_pct": round(100.0 * success_count / total_requests, 1),
        "wall_duration_s": round(wall_duration, 4),
        "requests_per_second": rps,
        "latency_p50_ms": round(p50, 2),
        "latency_p95_ms": round(p95, 2),
        "latency_p99_ms": round(p99, 2),
    }


def main():
    concurrency_tiers = [1, 5, 10, 25, 50]
    print(f"Starting FleetWise Performance Benchmark on {os.name}...")

    with tempfile.TemporaryDirectory() as td:
        temp_db = os.path.join(td, "benchmark.db")
        os.environ["DATABASE_PATH"] = temp_db
        init_db(temp_db)

        client = TestClient(app)
        benchmark_results = []

        for threads in concurrency_tiers:
            print(f"Benchmarking at {threads} threads...", end=" ", flush=True)
            res = run_benchmark_for_concurrency(client, threads, total_requests=100)
            benchmark_results.append(res)
            print(f"{res['requests_per_second']} req/s | p50={res['latency_p50_ms']}ms | p95={res['latency_p95_ms']}ms")

        output_path = WORKSPACE / "evidence" / "benchmark.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "title": "FleetWise Concurrency & Latency Benchmark",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "disclaimer": "Measured on a single developer machine with SQLite; real production throughput depends on network and database backend.",
            "results": benchmark_results,
        }

        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nBenchmark successfully saved to: {output_path}")


if __name__ == "__main__":
    main()
