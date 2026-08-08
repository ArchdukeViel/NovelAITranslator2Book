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

Each script refuses to run if ``.venv\Scripts\python.exe`` is missing.
The CI workflow installs ``.[documents,gemini,dev,db,worker,s3,auth]``
into the venv before invoking tooling.
