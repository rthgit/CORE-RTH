from __future__ import annotations


def test_telegram_whatsapp_mail_replay_endpoints(client):
    r = client.post("/api/v1/jarvis/telegram/replay", json={"text": "/status", "chat_id": "999000111", "username": "owner_test", "auto_reply": True})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["mode"] == "replay"
    assert data["result"]["reply"]["type"] == "status"
    assert data["result"]["send_result"]["mode"] == "replay"

    r = client.post("/api/v1/jarvis/whatsapp/replay", json={"text": "/route prova routing", "from_number": "15550001111", "auto_reply": True})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["mode"] == "replay"
    assert data["result"]["count"] >= 1
    ev = data["result"]["events"][0]
    assert ev["action"] == "parsed"
    assert ev["send_result"]["mode"] == "replay"

    r = client.post(
        "/api/v1/jarvis/mail/replay",
        json={
            "payload": {"cmd": "status", "secret": "rth-replay-secret"},
            "from_addr": "owner@example.local",
            "shared_secret": "rth-replay-secret",
            "allow_remote_approve": False,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["mode"] == "replay"
    assert data["result"]["status"] == "handled"
    assert data["result"]["result"]["status"] == "ok"


def test_secret_store_rotate_export_import_audit(client):
    # set + rotate
    r = client.post("/api/v1/secrets/set", json={"name": "tests/demo", "value": "alpha-1", "confirm_owner": True, "decided_by": "owner"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r = client.post("/api/v1/secrets/rotate", json={"name": "tests/demo", "new_value": "alpha-2", "keep_previous": True, "confirm_owner": True, "decided_by": "owner"})
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "ok"
    assert out["result"]["rotated"] is True

    # export encrypted values
    r = client.post("/api/v1/secrets/export", json={"include_values": True, "confirm_owner": True, "decided_by": "owner"})
    assert r.status_code == 200
    out = r.json()
    assert out["status"] == "ok"
    bundle = out["result"]["bundle"]
    assert bundle["format"] == "rth.secret.export.v1"
    assert bundle["include_values"] is True
    assert "checksum_sha256" in bundle
    assert any(e["name"] == "tests/demo" for e in bundle["entries"])

    # import same bundle under isolated env should succeed/partial (overwrite)
    r = client.post(
        "/api/v1/secrets/import",
        json={"bundle": bundle, "import_values": True, "on_conflict": "overwrite", "confirm_owner": True, "decided_by": "owner"},
    )
    assert r.status_code == 200
    assert r.json()["status"] in {"ok", "partial"}

    # audit exists and contains actions
    r = client.get("/api/v1/secrets/audit?limit=50")
    assert r.status_code == 200
    audit = r.json()
    assert audit["status"] == "ok"
    actions = [e.get("action") for e in audit.get("events", [])]
    for expected in ("set", "rotate", "export", "import"):
        assert expected in actions

    # cleanup
    r = client.post("/api/v1/secrets/delete", json={"name": "tests/demo", "confirm_owner": True, "decided_by": "owner"})
    assert r.status_code == 200
    assert r.json()["status"] in {"ok", "not_found"}

