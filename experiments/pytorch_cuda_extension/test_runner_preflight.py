from types import SimpleNamespace

from . import runner_preflight as preflight_module


def test_current_runner_preflight_is_actionable() -> None:
    report = preflight_module.runner_preflight()

    assert isinstance(report["ready"], bool)
    assert report["minimum_free_gib"] == 20
    if not report["ready"]:
        assert report["reasons"]


def test_ready_linux_cuda_runner_passes(monkeypatch) -> None:
    monkeypatch.setattr(preflight_module.platform, "system", lambda: "Linux")
    monkeypatch.setattr(preflight_module.platform, "machine", lambda: "x86_64")
    monkeypatch.setattr(
        preflight_module.shutil,
        "which",
        lambda name: f"/usr/bin/{name}",
    )
    monkeypatch.setattr(
        preflight_module.shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=30 * 1024**3),
    )
    monkeypatch.setattr(preflight_module, "_tool_version", lambda executable: "test-version")
    monkeypatch.setattr(
        preflight_module,
        "cuda_environment",
        lambda: {"ready": True, "reasons": []},
    )

    report = preflight_module.runner_preflight()

    assert report["ready"] is True
    assert report["reasons"] == []
    assert set(report["tools"]) == {"git", "c++", "ninja"}
