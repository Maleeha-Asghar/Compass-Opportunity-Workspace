from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.graph import CompassGraph

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def dispatch_search_job(job_id: str) -> subprocess.Popen:
    command = [sys.executable, "-m", "jobs.search_job_worker", "--job-id", job_id]
    return subprocess.Popen(
        command,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def run_job(job_id: str) -> None:
    graph = CompassGraph()
    job = graph.repository.get_search_job_by_id(job_id)
    if not job:
        raise RuntimeError(f"Search job not found: {job_id}")
    if job.get("status") in {"completed", "failed"}:
        return
    if job.get("status") == "queued":
        claimed = graph.repository.claim_search_job_by_id(job_id)
        if not claimed:
            return
        job = claimed
    profile = job.get("profile") or {}
    graph.run_search_job(
        job_id=job["id"],
        user_id=job["user_id"],
        query=job["query"],
        profile=profile,
        max_results_per_query=int(profile.get("_max_results_per_query") or 3),
    )


def reclaim_stale_jobs(graph: CompassGraph) -> None:
    cutoff_seconds = graph.settings.search_job_timeout_seconds
    now = datetime.now(timezone.utc)
    for job in graph.repository.list_running_search_jobs():
        updated_at = job.get("updated_at")
        if not updated_at:
            continue
        try:
            updated = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if (now - updated).total_seconds() > cutoff_seconds:
            graph.repository.fail_search_job(
                job["id"],
                f"Search job timed out after {cutoff_seconds} seconds.",
                progress_message="Search timed out",
            )


def run_worker(poll_interval_seconds: float = 5.0, once: bool = False) -> None:
    graph = CompassGraph()
    while True:
        reclaim_stale_jobs(graph)
        job = graph.repository.claim_next_search_job()
        if job:
            command = [sys.executable, "-m", "jobs.search_job_worker", "--job-id", job["id"]]
            try:
                subprocess.run(command, check=True, timeout=graph.settings.search_job_timeout_seconds)
            except subprocess.TimeoutExpired:
                graph.repository.fail_search_job(
                    job["id"],
                    f"Search job timed out after {graph.settings.search_job_timeout_seconds} seconds.",
                    progress_message="Search timed out",
                )
            except subprocess.CalledProcessError as exc:
                graph.repository.fail_search_job(
                    job["id"],
                    f"Search worker exited with code {exc.returncode}.",
                    progress_message="Search failed",
                )
            if once:
                return
            continue
        if once:
            return
        time.sleep(poll_interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Compass search worker.")
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--job-id", type=str, default=None)
    args = parser.parse_args()
    if args.job_id:
        run_job(args.job_id)
        return
    run_worker(poll_interval_seconds=args.poll_interval, once=args.once)


if __name__ == "__main__":
    main()