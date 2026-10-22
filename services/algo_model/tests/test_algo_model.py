import io
import json
import time
import zipfile

from conftest import H


def wait_test(am, tid, timeout=600):
    t0 = time.time()
    while time.time() - t0 < timeout:
        t = am.get(f"/tests/{tid}", headers=H("mathematician")).json()
        if t["status"] in ("passed", "failed"):
            return t
        time.sleep(0.5)
    raise AssertionError("тест не завершился")


def test_new_algorithm_flow(algo_stack):
    dm, da, aa, am, mod = algo_stack
    assert am.get("/algorithms", headers=H("ichthyologist")).status_code == 403
    r = am.post("/algorithms", headers=H("mathematician"), json={"code": "pdu_scaled", "title_ru": "ПДУ НПЦ × k"})
    assert r.status_code == 201, r.text
    did = r.json()["draft_id"]
    # ошибка синтаксиса находится проверкой
    am.put(f"/drafts/{did}/file", headers=H("mathematician"), json={"path": "algorithm.py", "text": "def run(ctx)\n  pass"})
    v = am.post(f"/drafts/{did}/validate", headers=H("mathematician")).json()
    assert not v["ok"] and "синтаксическая ошибка" in v["errors"][0]
    # без теста не публикуется
    from app.main import TEMPLATE_ALGO  # noqa
    am.put(f"/drafts/{did}/file", headers=H("mathematician"), json={"path": "algorithm.py", "text": TEMPLATE_ALGO.format(title="x")})
    assert am.post(f"/drafts/{did}/publish", headers=H("mathematician"), json={}).status_code == 400
    t = am.post(f"/drafts/{did}/test", headers=H("mathematician"), json={"water_body": "zhaysan", "params": {"k": 2}}).json()
    t = wait_test(am, t["id"])
    assert t["status"] == "passed", t.get("message")
    res = am.get(f"/tests/{t['id']}/result", headers=H("mathematician")).json()
    assert res["tables"]["result"]["rows"][0]["value"] == 2 * (3597 + 1076 + 145 + 160 + 260 + 471 + 58 + 1)
    p = am.post(f"/drafts/{did}/publish", headers=H("mathematician"), json={"comment": "первая версия"})
    assert p.status_code == 200, p.text
    cat = {a["code"]: a for a in aa.get("/catalog", headers=H()).json()}
    assert cat["pdu_scaled"]["latest"] == "0.1.0" and cat["pdu_scaled"]["versions"][0]["source"] == "algo_model"
    # новая версия должна иметь больший номер
    d2 = am.post("/algorithms/pdu_scaled/drafts", headers=H("mathematician"), json={}).json()
    m = json.loads(am.get(f"/drafts/{d2['id']}/file?path=manifest.json", headers=H("mathematician")).json()["text"])
    assert m["version"] == "0.1.1"


def test_change_builtin_and_compare(algo_stack):
    """Математик меняет неизменяемый параметр методики в новой версии — сверка показывает отличие."""
    dm, da, aa, am, mod = algo_stack
    d = am.post("/algorithms/pdu_by_age/drafts", headers=H("mathematician"), json={}).json()
    m = json.loads(am.get(f"/drafts/{d['id']}/file?path=manifest.json", headers=H("mathematician")).json()["text"])
    assert m["version"] == "2.0.1"
    for p in m["parameters"]:
        if p["code"] == "PDU_MAX_ITER":
            p["default"] = 1          # одна итерация и не больше 1 % остатка возраста —
        if p["code"] == "PDU_CAP":    # квота распределяется не полностью
            p["default"] = 0.01
    am.put(f"/drafts/{d['id']}/file", headers=H("mathematician"),
           json={"path": "manifest.json", "text": json.dumps(m, ensure_ascii=False)})
    t = am.post(f"/drafts/{d['id']}/test", headers=H("mathematician"), json={"compare_with": "2.0.0"}).json()
    t = wait_test(am, t["id"])
    assert t["status"] == "passed", t.get("message")
    by = {x["table"]: x for x in t["comparison"]["tables"]}
    assert by["pdu_by_age"]["status"] == "отличается"
    # архив: выгрузить и загрузить обратно
    z = am.get(f"/drafts/{d['id']}/download.zip", headers=H("mathematician")).content
    assert "fishcore/pdu_npc.py" in zipfile.ZipFile(io.BytesIO(z)).namelist()
    r = am.post(f"/drafts/{d['id']}/upload", headers=H("mathematician"), files={"file": ("x.zip", z)})
    assert r.status_code == 200
