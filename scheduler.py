"""
Features 48, 53, 54: Cron scheduler, webhook trigger, queue/batch manager.
"""
import json
import time
import threading
from datetime import datetime
from pathlib import Path


class BatchManager:
    """Feature 54: Handle large lists in controlled batches."""

    def __init__(self, batch_size: int = 10, delay_between_batches: float = 5.0):
        self.batch_size = batch_size
        self.delay = delay_between_batches

    def create_batches(self, items: list) -> list[list]:
        return [items[i:i + self.batch_size] for i in range(0, len(items), self.batch_size)]

    def process_batches(self, items: list, processor_fn, progress_fn=None) -> list:
        """Process items in batches with delays between them."""
        batches = self.create_batches(items)
        all_results = []

        for batch_idx, batch in enumerate(batches):
            if progress_fn:
                progress_fn(batch_idx + 1, len(batches), len(all_results), len(items))

            results = []
            for item in batch:
                try:
                    result = processor_fn(item)
                    results.append(result)
                except Exception as e:
                    results.append({"error": str(e), "item": item})

            all_results.extend(results)

            # Delay between batches (not after the last one)
            if batch_idx < len(batches) - 1:
                time.sleep(self.delay)

        return all_results


class CronScheduler:
    """Feature 48: Schedule re-runs on a cron-like basis."""

    def __init__(self):
        self._schedules = {}
        self._running = False
        self._thread = None

    def add_schedule(self, name: str, interval_hours: float, callback, args=None):
        """Add a scheduled task. Simple interval-based (not full cron)."""
        self._schedules[name] = {
            "interval": interval_hours * 3600,
            "callback": callback,
            "args": args or [],
            "last_run": None,
            "next_run": time.time(),
        }

    def remove_schedule(self, name: str):
        self._schedules.pop(name, None)

    def list_schedules(self) -> list[dict]:
        return [
            {
                "name": name,
                "interval_hours": s["interval"] / 3600,
                "last_run": datetime.fromtimestamp(s["last_run"]).isoformat() if s["last_run"] else None,
                "next_run": datetime.fromtimestamp(s["next_run"]).isoformat(),
            }
            for name, s in self._schedules.items()
        ]

    def start(self):
        """Start the scheduler in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print("[SCHEDULER] Started")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[SCHEDULER] Stopped")

    def _run_loop(self):
        while self._running:
            now = time.time()
            for name, schedule in self._schedules.items():
                if now >= schedule["next_run"]:
                    try:
                        print(f"[SCHEDULER] Running: {name}")
                        schedule["callback"](*schedule["args"])
                        schedule["last_run"] = now
                    except Exception as e:
                        print(f"[SCHEDULER] Error in {name}: {e}")
                    schedule["next_run"] = now + schedule["interval"]
            time.sleep(30)  # Check every 30 seconds


class WebhookHandler:
    """Feature 53: Process webhook-triggered runs."""

    def __init__(self, pipeline_fn):
        self.pipeline_fn = pipeline_fn
        self.pending = []

    def receive(self, payload: dict) -> dict:
        """Accept a webhook payload and queue it for processing."""
        # Validate payload
        leads = payload.get("leads", [])
        if not leads:
            return {"status": "error", "message": "No leads in payload"}

        job = {
            "id": len(self.pending) + 1,
            "received_at": datetime.now().isoformat(),
            "lead_count": len(leads),
            "status": "queued",
            "leads": leads,
        }
        self.pending.append(job)
        return {"status": "queued", "job_id": job["id"], "lead_count": len(leads)}

    def process_pending(self) -> list[dict]:
        """Process all pending webhook jobs."""
        results = []
        while self.pending:
            job = self.pending.pop(0)
            job["status"] = "processing"
            try:
                result = self.pipeline_fn(job["leads"])
                job["status"] = "completed"
                job["result"] = result
            except Exception as e:
                job["status"] = "failed"
                job["error"] = str(e)
            results.append(job)
        return results


# Singleton instances
batch_manager = BatchManager()
scheduler = CronScheduler()
