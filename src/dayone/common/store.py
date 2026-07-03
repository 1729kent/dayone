import time
from typing import Protocol

from dayone.common.models import Event, Run


class Store(Protocol):
    def create_run(self, run: Run) -> None: ...
    def update_run(self, run_id: str, **fields) -> None: ...
    def get_run(self, run_id: str) -> Run | None: ...
    def list_runs(self, limit: int = 20) -> list[Run]: ...
    def append_event(self, run_id: str, type: str, payload: dict) -> int: ...
    def get_events(self, run_id: str, after_seq: int = -1) -> list[Event]: ...
    def try_acquire_cooldown(self, seconds: int, now: float) -> bool: ...


class MemoryStore:
    def __init__(self):
        self._runs: dict[str, Run] = {}
        self._events: dict[str, list[Event]] = {}
        self._cooldown_until = 0.0

    def create_run(self, run: Run) -> None:
        self._runs[run.id] = run
        self._events[run.id] = []

    def update_run(self, run_id: str, **fields) -> None:
        self._runs[run_id] = self._runs[run_id].model_copy(update=fields)

    def get_run(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def list_runs(self, limit: int = 20) -> list[Run]:
        return sorted(self._runs.values(), key=lambda r: -r.started_at)[:limit]

    def append_event(self, run_id: str, type: str, payload: dict) -> int:
        seq = len(self._events[run_id])
        self._events[run_id].append(Event(seq=seq, ts=time.time(), type=type, payload=payload))
        return seq

    def get_events(self, run_id: str, after_seq: int = -1) -> list[Event]:
        return [e for e in self._events.get(run_id, []) if e.seq > after_seq]

    def try_acquire_cooldown(self, seconds: int, now: float) -> bool:
        if now < self._cooldown_until:
            return False
        self._cooldown_until = now + seconds
        return True


class FirestoreStore:
    """runs/{id}, runs/{id}/events/{seq:06d}, locks/trigger"""

    def __init__(self, project_id: str, client=None):
        if client is None:
            from google.cloud import firestore

            client = firestore.Client(project=project_id)
        self.db = client

    def create_run(self, run: Run) -> None:
        doc = run.model_dump()
        doc["event_count"] = 0
        self.db.collection("runs").document(run.id).set(doc)

    def update_run(self, run_id: str, **fields) -> None:
        self.db.collection("runs").document(run_id).update(fields)

    def get_run(self, run_id: str) -> Run | None:
        snap = self.db.collection("runs").document(run_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict()
        data.pop("event_count", None)
        return Run.model_validate(data)

    def list_runs(self, limit: int = 20) -> list[Run]:
        q = self.db.collection("runs").order_by("started_at", direction="DESCENDING").limit(limit)
        out = []
        for snap in q.stream():
            data = snap.to_dict()
            data.pop("event_count", None)
            out.append(Run.model_validate(data))
        return out

    def append_event(self, run_id: str, type: str, payload: dict) -> int:
        from google.cloud import firestore

        run_ref = self.db.collection("runs").document(run_id)

        @firestore.transactional
        def txn(transaction):
            snap = run_ref.get(transaction=transaction)
            seq = (snap.to_dict() or {}).get("event_count", 0)
            transaction.update(run_ref, {"event_count": seq + 1})
            ev_ref = run_ref.collection("events").document(f"{seq:06d}")
            transaction.set(ev_ref, {"seq": seq, "ts": time.time(), "type": type, "payload": payload})
            return seq

        return txn(self.db.transaction())

    def get_events(self, run_id: str, after_seq: int = -1) -> list[Event]:
        q = (self.db.collection("runs").document(run_id).collection("events")
             .where("seq", ">", after_seq).order_by("seq"))
        return [Event.model_validate(s.to_dict()) for s in q.stream()]

    def try_acquire_cooldown(self, seconds: int, now: float) -> bool:
        from google.cloud import firestore

        lock_ref = self.db.collection("locks").document("trigger")

        @firestore.transactional
        def txn(transaction):
            snap = lock_ref.get(transaction=transaction)
            until = (snap.to_dict() or {}).get("until", 0.0) if snap.exists else 0.0
            if now < until:
                return False
            transaction.set(lock_ref, {"until": now + seconds})
            return True

        return txn(self.db.transaction())
