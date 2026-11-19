# Contributor instructions

- Inspect the repository and `git status` before editing; preserve unrelated user files.
- Use the existing `uv` workflow and Python 3.12. Do not introduce another environment manager.
- Run `.\scripts\check.ps1` before completing a change.
- Do not add dependencies without a concrete, documented need.
- Keep domain and translation code independent from Typer.
- Preserve Windows 11 and PowerShell compatibility.
- Never commit user-specific absolute paths.
- Add or update tests with every behavior change.
- Update README and CHANGELOG for user-visible behavior changes.
- Never download large models during unit tests or CI.
- Never commit generated PDFs, model weights, virtual environments, caches, or logs.
- Create all temporary files and directories under the repository-local `./temp/` directory.
  Do not use system temporary directories for project work unless an external tool cannot be
  configured otherwise.
