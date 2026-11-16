
import json

import pytest

from src.storage import events as storage


def test_load_events_when_file_does_not_exist(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "EVENTS_FILE", tmp_path / "events.json")

    assert storage.load_events() == []


def test_save_and_load_events(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "EVENTS_FILE", tmp_path / "events.json")

    sample = [{"id": "event-1", "city": "Hyderabad"}]

    storage.save_events(sample)

    assert storage.load_events() == sample


def test_add_event(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "EVENTS_FILE", tmp_path / "events.json")

    event = {"id": "event-1", "city": "Hyderabad"}

    assert storage.add_event(event) is True
    assert storage.add_event(event) is False
    assert len(storage.load_events()) == 1


def test_add_event_requires_id(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_DIR", tmp_path)
    monkeypatch.setattr(storage, "EVENTS_FILE", tmp_path / "events.json")

    with pytest.raises(ValueError):
        storage.add_event({"city": "Hyderabad"})


def test_corrupted_storage_raises_error(tmp_path, monkeypatch):
    events_file = tmp_path / "events.json"
    events_file.write_text("{invalid json", encoding="utf-8")

    monkeypatch.setattr(storage, "EVENTS_FILE", events_file)

    with pytest.raises(RuntimeError):
        storage.load_events()
