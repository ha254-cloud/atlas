import time

from app.db.database import SessionLocal
from app.imports.claim_import_service import ClaimImportService
from app.queue.redis_queue import RedisQueue


def process_queue_once(queue: RedisQueue):
    item = queue.dequeue()
    if item is None:
        return False

    # Each worker creates its own DB session
    db = SessionLocal()
    try:
        service = ClaimImportService(db, int(item["organization_id"]))
        service.import_claim(item)
    finally:
        db.close()

    return True


def run_worker_loop(queue: RedisQueue, poll_interval: float = 1.0):
    while True:
        processed = process_queue_once(queue)
        if not processed:
            time.sleep(poll_interval)
