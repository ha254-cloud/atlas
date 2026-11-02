from types import SimpleNamespace

import pytest


class FakeSession:
    def __init__(self, organization_ids: list[int] | None = None):
        self.organization_ids = organization_ids or []
        self.closed = False
        self.rollbacks = 0

    def query(self, _column):
        return self

    def all(self):
        return [(organization_id,) for organization_id in self.organization_ids]

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def test_every_beat_task_is_registered():
    from app.workers.celery_app import celery

    celery.loader.import_default_modules()

    scheduled_tasks = {
        entry["task"] for entry in celery.conf.beat_schedule.values()
    }
    assert scheduled_tasks <= set(celery.tasks)


def test_process_workflow_event_uses_tenant_scope_and_closes_session(monkeypatch):
    from app.workers.tasks import process_workflow_event

    session = FakeSession()

    class FakeEngine:
        def __init__(self, db, organization_id):
            assert db is session
            assert organization_id == 42

        async def process(self, workflow_event_id):
            assert workflow_event_id == 7
            return [101, 102]

    monkeypatch.setattr("app.db.database.get_db", lambda: iter([session]))
    monkeypatch.setattr("app.workflows.engine.WorkflowEventEngine", FakeEngine)

    assert process_workflow_event.run(7, 42) == {"executions": 2}
    assert session.closed is True


def test_process_workflow_event_dead_letters_after_final_retry(monkeypatch):
    from app.workers.tasks import process_workflow_event

    session = FakeSession()
    dead_letters = []

    class FakeEngine:
        def __init__(self, db, organization_id):
            assert db is session
            assert organization_id == 42

        async def process(self, workflow_event_id):
            raise RuntimeError("unsafe workflow definition")

        def dead_letter(self, workflow_event_id, error):
            dead_letters.append((workflow_event_id, error))

    monkeypatch.setattr("app.db.database.get_db", lambda: iter([session]))
    monkeypatch.setattr("app.workflows.engine.WorkflowEventEngine", FakeEngine)

    process_workflow_event.push_request(retries=3)
    try:
        with pytest.raises(RuntimeError, match="unsafe workflow definition"):
            process_workflow_event.run(7, 42)
    finally:
        process_workflow_event.pop_request()

    assert dead_letters == [(7, "unsafe workflow definition")]
    assert session.closed is True


def test_requeue_pending_workflow_events_is_tenant_scoped_and_closes_session(
    monkeypatch,
):
    from app.workers.tasks import requeue_pending_workflow_events

    session = FakeSession([11, 22])
    queued = []

    class FakeRepository:
        def __init__(self, db, organization_id):
            assert db is session
            self.organization_id = organization_id

        def pending_events(self):
            return [SimpleNamespace(id=self.organization_id * 10)]

    monkeypatch.setattr("app.db.database.get_db", lambda: iter([session]))
    monkeypatch.setattr("app.workflows.repository.WorkflowRepository", FakeRepository)
    monkeypatch.setattr(
        "app.workers.tasks.process_workflow_event.delay",
        lambda event_id, organization_id: queued.append(
            (event_id, organization_id)
        ),
    )

    assert requeue_pending_workflow_events.run() == {
        "queued": 2,
        "organizations": 2,
    }
    assert queued == [(110, 11), (220, 22)]
    assert session.closed is True


def test_task_sla_sweep_is_tenant_scoped_and_isolates_failures(monkeypatch):
    from app.workers.tasks import check_task_slas

    session = FakeSession([11, 22])
    calls = []

    def fake_sweep(db, organization_id):
        assert db is session
        calls.append(organization_id)
        if organization_id == 11:
            raise RuntimeError("tenant settings invalid")
        return [1, 2]

    monkeypatch.setattr("app.db.database.get_db", lambda: iter([session]))
    monkeypatch.setattr("app.tasks.scheduler.run_task_sla_sweep", fake_sweep)

    assert check_task_slas.run() == {
        "escalated": 2,
        "organizations": 2,
    }
    assert calls == [11, 22]
    assert session.rollbacks == 1
    assert session.closed is True


def test_workflow_trigger_dispatch_includes_persisted_organization(monkeypatch):
    from app.events.handlers.workflows import WorkflowTriggerHandler

    queued = []
    monkeypatch.setattr(
        "app.workers.tasks.process_workflow_event.delay",
        lambda event_id, organization_id: queued.append(
            (event_id, organization_id)
        ),
    )

    WorkflowTriggerHandler._dispatch(7, 42)

    assert queued == [(7, 42)]
