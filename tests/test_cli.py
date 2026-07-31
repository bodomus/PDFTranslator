from unittest.mock import patch

from typer.testing import CliRunner

from pdftranslate.cli import app

runner = CliRunner()


def test_version_exits_successfully() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert "PDFTranslate" in result.stdout
    assert "0.1.0" in result.stdout


def test_doctor_exits_successfully() -> None:
    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "PDFTranslate doctor" in result.stdout
    assert "Application" in result.stdout
    assert "Status" in result.stdout


def test_doctor_works_without_cuda_tools() -> None:
    with (
        patch("pdftranslate.cli.importlib.util.find_spec", return_value=None),
        patch("pdftranslate.cli.shutil.which", return_value=None),
    ):
        result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "PyTorch is not installed" in result.stdout
    assert "nvidia-smi is unavailable" in result.stdout


def test_unsupported_command_exits_predictably() -> None:
    result = runner.invoke(app, ["does-not-exist"])

    assert result.exit_code == 2
    assert "No such command" in result.output
