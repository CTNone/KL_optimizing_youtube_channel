# Repository Guidelines

## Project Structure

This is a Windows-first Python repository for managing YouTube content production. `CONTENT HUB/` contains the SQLite workflow manager (`app.py`, `store.py`, `services.py`), demo data, tests, and PyInstaller build script. `TOOL NCTT/` contains market research; `TOOL THUMBNAIL/` contains thumbnail generation and shared Chrome/Flow integration; `TOOL Video Flow/` contains the integrated studio, video controller, and pipeline tests. `editer/TOOL EDIT/v3/v3/` contains the Tkinter editor, FFmpeg loop engine, and rendering tests. Supporting music tools are under `editer/Nhạc jazz/`. Test files live beside the code they cover; generated media, local databases, credentials, build output, and downloaded libraries are not source files.

## Run, Build, and Test

Run the local management app with `cd "CONTENT HUB"; py app.py`; use `py app.py --demo` to open its separate sample database. Run manager tests with `py -m unittest test_hub -v` from `CONTENT HUB/`. From the editor directory, run `py selftest.py` and `py -m unittest test_flow_loop -v`; build its Windows package with `build_flow.bat`. Market research and thumbnail tools use their local `run.bat` launchers. Flow integration tests are in `TOOL Video Flow/`; run the relevant `python -m unittest` command from that directory. Read each tool’s README before installing dependencies or building.

## Style and Changes

Use four spaces for Python indentation, `snake_case` for functions and variables, and `CapWords` for classes. Keep UI code in app modules, workflow and persistence rules in `CONTENT HUB/store.py`, and tool/process integration in `services.py`. Preserve existing Tkinter and standard-library conventions. There is no repository-wide formatter or linter configured. Make focused changes and keep generated media and secrets out of commits.

## Testing and External Services

Name tests `test_*.py` and use `unittest`. Run the tests relevant to the changed tool; media integration tests require the bundled FFmpeg. Use the Hub demo or synthetic fixtures for local checks. Tests or scripts that submit work to Google Flow can consume account credits: inspect the target script and obtain explicit user authorization before starting a real generation. Do not expose API keys, browser profiles, or downloaded account data in logs or fixtures.

## Commits and Pull Requests

Git history currently contains only the initial import, so no commit convention is established. Use short, descriptive imperative subjects, such as `Add asset version checks`. A pull request should summarize behavior, list affected tools, include test commands and outcomes, describe any external-service checks, and provide screenshots for visible UI changes. Document Windows-specific setup or migration steps when applicable.
