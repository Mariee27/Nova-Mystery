"""After a deploy, Streamlit Cloud may run the new app.py with old copies of the other modules
in memory (live on 23 Nov: 'Search a place' crashed with a TypeError for campus_map(busy=...)).
app.py loads outdated modules again; these tests check that with a small module of their own."""
import importlib
import os
import sys

from test_app_smoke import app_functions

APP = app_functions()


def write_module(folder, name, body, mtime):
    path = folder / f"{name}.py"
    path.write_text(body)
    os.utime(path, (mtime, mtime))
    return path


def test_a_module_whose_file_changed_after_loading_is_outdated_and_gets_loaded_again(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    path = write_module(tmp_path, "deploy_demo", "def campus_map(searched):\n    return 'old'\n", 1_700_000_000)
    module = importlib.import_module("deploy_demo")
    try:
        assert not APP["outdated"](module)                       # just loaded: current
        assert APP["reload_outdated_modules"](["deploy_demo"]) == []
        write_module(tmp_path, "deploy_demo",
                     "def campus_map(searched, busy=()):\n    return 'new'\n", 1_700_000_100)   # the deploy
        assert APP["outdated"](module)
        assert APP["reload_outdated_modules"](["deploy_demo"]) == ["deploy_demo"]
        assert module.campus_map([], busy={"Library"}) == "new"  # the same module object, now current
        assert not APP["outdated"](module)
        assert APP["reload_outdated_modules"](["deploy_demo"]) == []    # only once per deploy
    finally:
        sys.modules.pop("deploy_demo", None)
        assert path.exists()


def test_when_python_writes_no_pyc_files_an_old_pyc_on_disk_says_nothing(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    write_module(tmp_path, "deploy_demo2", "X = 1\n", 1_700_000_000)
    module = importlib.import_module("deploy_demo2")
    try:
        write_module(tmp_path, "deploy_demo2", "X = 2\n", 1_700_000_100)
        monkeypatch.setattr(sys, "dont_write_bytecode", True)
        assert not APP["outdated"](module)
        assert APP["reload_outdated_modules"](["deploy_demo2"]) == []
    finally:
        sys.modules.pop("deploy_demo2", None)


def test_without_a_pyc_file_a_module_counts_as_current():
    class NoCache:
        __cached__ = None
        __file__ = "nowhere.py"
    assert not APP["outdated"](NoCache())
    assert not APP["outdated"](sys)                              # built-in module: no file at all


def test_the_game_modules_are_current_in_a_normal_run_and_nothing_is_reloaded():
    assert APP["reload_outdated_modules"]() == []
    assert set(APP["OWN_MODULES"]) == {name[:-3] for name in os.listdir(os.path.dirname(APP["__file__"]))
                                       if name.endswith(".py") and name != "app.py"}
