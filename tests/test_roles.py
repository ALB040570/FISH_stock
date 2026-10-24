"""Права ролей: оператор ввода данных (docs/decisions.md, № 54)."""
from fishcommon.auth import PERMISSIONS, ROLE_TITLES, ROLES, User


def can(role, perm):
    return User(id="u", login="u", name="u", role=role).can(perm)


def test_operator_role_exists():
    assert "operator" in ROLES
    assert ROLE_TITLES["operator"] == "Оператор ввода данных"


def test_operator_permissions():
    # вводит и правит данные, остальное — только просмотр
    assert can("operator", "data.edit") and can("operator", "data.view")
    for perm in ("dict.view", "run.view", "dashboard.view", "help.view", "catalog.view", "profile.view"):
        assert can("operator", perm), perm
    for perm in ("dict.edit", "profile.edit", "run.execute", "dashboard.edit", "dashboard.template", "algo.develop",
                 "catalog.manage", "users.manage", "audit.view", "help.edit"):
        assert not can("operator", perm), perm


def test_other_roles_unchanged():
    assert not can("viewer", "data.edit")
    for role in ("admin", "ichthyologist", "mathematician"):
        assert can(role, "data.edit") and can(role, "run.execute")
    assert set(PERMISSIONS["users.manage"]) == {"admin"}


def test_results_only_for_staff():
    """Результаты модели (уловистость, запасы, ПДУ приложения) — администратор, математик, ихтиолог (№ 62)."""
    for role in ("admin", "ichthyologist", "mathematician"):
        assert can(role, "results.view") and can(role, "results.summary") and can(role, "help.full")
    for role in ("operator", "viewer", "presenter"):
        assert not can(role, "results.view"), role
        assert can(role, "dashboard.view") and can(role, "run.view") and can(role, "data.view"), role


def test_presenter_role():
    """«Презентация» (№ 62): только показ — ничего не меняет, без параметров водоёмов, кода алгоритмов и формул."""
    assert "presenter" in ROLES and ROLE_TITLES["presenter"] == "Презентация"
    for perm in ("dict.view", "data.view", "catalog.view", "run.view", "dashboard.view", "help.view", "results.summary"):
        assert can("presenter", perm), perm
    for perm in ("data.edit", "dict.edit", "profile.view", "profile.edit", "run.execute", "dashboard.edit", "dashboard.template",
                 "algo.develop", "catalog.manage", "catalog.files", "users.manage", "audit.view", "help.edit", "help.full",
                 "results.view"):
        assert not can("presenter", perm), perm
    # наблюдатель и оператор сохраняют прежние права просмотра
    for role in ("viewer", "operator"):
        assert can(role, "profile.view") and can(role, "catalog.files") and can(role, "help.full")


def test_frontend_permissions_mirror():
    """Зеркало прав во фронтенде (store/auth.js) совпадает с fishcommon для перечисленных там прав."""
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "store" / "auth.js").read_text(encoding="utf-8")
    block = src[src.index("const PERMS = {"):src.index("}", src.index("const PERMS = {"))]
    pairs = re.findall(r"'([\w.]+)':\s*\[([^\]]*)\]", block)
    assert len(pairs) >= 15
    for perm, roles in pairs:
        assert set(re.findall(r"'(\w+)'", roles)) == PERMISSIONS[perm], perm
