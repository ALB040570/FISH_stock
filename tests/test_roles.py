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
