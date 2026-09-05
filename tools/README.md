# Tools

Local scripts that always run inside the project virtualenv
(``.venv``). Use these instead of bare ``python`` / ``pytest`` / ``ruff`` /
``pyright`` so PATH-precedence mistakes cannot poison results.

- ``tools/pytest.ps1 [args]`` -- run the test suite through
  ``.venv/Scripts/python.exe -m pytest``.
- ``tools/pyright.ps1 [args]`` -- run pyright through
  ``.venv/Scripts/python.exe -m pyright``.
- ``tools/ruff.ps1 [args]`` -- run ruff through
  ``.venv/Scripts/python.exe -m ruff``.
- ``tools/docs-check.ps1`` -- validate repository canonical documentation contracts.
- ``tools/audit_dead_code.py`` -- audit repository for unreferenced, dead, or legacy artifacts.
- ``tools/database/export_seed.py`` -- export curated database seed with dynamic sequence discovery.

Each script refuses to run if ``.venv\Scripts\python.exe`` is missing.
The CI workflow installs ``.[documents,gemini,dev,test,s3,auth]``
into the venv before invoking tooling.
