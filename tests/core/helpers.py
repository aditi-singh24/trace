API = "/api/v1"


def new_participant(client, H, site="SITE-01", age=50, sex="F"):
    r = client.post(f"{API}/participants", json={"site_id": site, "age": age, "sex": sex}, headers=H.coord)
    assert r.status_code == 201, r.text
    return r.json()["participant_id"]


def to_eligible(client, H, pid, hba1c=9.0):
    assert client.post(f"{API}/participants/{pid}/consent", json={}, headers=H.coord).status_code == 200
    r = client.post(f"{API}/participants/{pid}/screening",
                    json={"t2dm_confirmed": True, "hba1c": hba1c, "therapy": "STABLE"}, headers=H.coord)
    assert r.status_code == 200, r.text
    return r.json()


def baseline(client, H, pid, hba1c=9.0):
    r = client.post(f"{API}/participants/{pid}/measurements",
                    json={"visit_week": 0, "hba1c": hba1c, "fasting_glucose": 160, "weight_kg": 80,
                          "systolic": 128, "diastolic": 80}, headers=H.coord)
    assert r.status_code == 201, r.text
    return r.json()


def randomize(client, H, pid):
    return client.post(f"{API}/randomization", json={"participant_id": pid}, headers=H.coord)


def baselined(client, H, hba1c=9.0, **kw):
    pid = new_participant(client, H, **kw)
    to_eligible(client, H, pid, hba1c)
    baseline(client, H, pid, hba1c)
    return pid


def enrolled(client, H, hba1c=9.0, **kw):
    """Baseline complete AND randomized (Module 5), ready for follow-up visits."""
    pid = baselined(client, H, hba1c, **kw)
    assert randomize(client, H, pid).status_code == 201
    return pid
