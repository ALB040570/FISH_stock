import json
import subprocess
import sys

from conftest import REPO


def test_backup_restore(tmp_path):
    data = tmp_path / "data"
    (data / "users" / "users" / "u1").mkdir(parents=True)
    (data / "users" / "users" / "u1" / "meta.json").write_text(json.dumps({"login": "ivan"}), encoding="utf-8")
    (data / "algo_admin" / "x.lock").parent.mkdir(parents=True)
    (data / "algo_admin" / "x.lock").write_text("")
    run = lambda *a: subprocess.run([sys.executable, str(REPO / "tools" / "backup.py"), *a], capture_output=True, text=True)
    r = run("create", "--data", str(data), "--out", str(tmp_path / "b"))
    assert r.returncode == 0, r.stderr
    arc = next((tmp_path / "b").glob("*.tar.gz"))
    assert run("verify", str(arc)).returncode == 0
    target = tmp_path / "restored"
    r = run("restore", str(arc), "--data", str(target))
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads((target / "users/users/u1/meta.json").read_text())["login"] == "ivan"
    assert not (target / "algo_admin" / "x.lock").exists()
    assert run("restore", str(arc), "--data", str(target)).returncode != 0      # непустой каталог без --force
    assert run("restore", str(arc), "--data", str(target), "--force").returncode == 0
