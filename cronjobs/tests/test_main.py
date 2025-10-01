from unittest import mock

import main
import pytest


def test_help(capsys):
    return_code = main.main("help")
    assert not return_code
    captured = capsys.readouterr()
    assert "Available commands:" in captured.out
    assert not captured.err


def test_unknown_command(capsys):
    return_code = main.main("neverheardof")
    assert return_code
    captured = capsys.readouterr()
    assert "Available commands:" in captured.out
    assert "neverheardof" in captured.err


def test_force_fail(monkeypatch):
    monkeypatch.setenv("FORCE_FAIL", "1")

    with pytest.raises(Exception, match="forced failure"):
        main.run("git_export")


def test_run_git_export(capsys):
    with mock.patch("main.importlib.import_module") as importlib_mock:
        entrypoint = mock.MagicMock()
        importlib_mock.return_value.git_export = entrypoint

        main.main("git_export")
        importlib_mock.assert_called_with("commands.git_export")
        entrypoint.assert_called_with(
            {"server": main.SERVER_URL}, {"sentry_sdk": main.sentry_sdk}
        )
