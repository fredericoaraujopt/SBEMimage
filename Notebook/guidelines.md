# SBEMimage Developer Guidelines

For developers:
The following notes (to be expanded) are for developers who would like to contribute to the development of SBEMimage. Questions? Please contact `btitze AT protonmail.ch`.

Additional development reference:
- Check more information here: [SBEMimage Development Docs](https://sbemimage.github.io/SBEMimage/development/)

## General

- Use Python 3 and PyQt 5 or higher.
- See `requirements.txt` for dependencies.

## Folder Structure

- `cfg`: Contains default configuration files `default.ini` and `system.cfg`, and all custom user and system configuration files. Also, `status.dat` is saved here when SBEMimage is closed; it contains the file name of the last configuration used. When using the Windows uninstaller, this directory is preserved.
- `dm`: Scripts for DigitalMicrograph (in a proprietary language) for both GMS 2 and GMS 3.
- `docs`: Documentation (generated using mkdocs: https://www.mkdocs.org and hosted as GitHub Pages: https://sbemimage.github.io/SBEMimage).
- `gui`: All PyQt user interface files (`.ui`), created with Qt Designer (bundled with Anaconda).
- `img`: Various images and icons.
- `array`: Array imaging example data from Thomas Templier.
- `src`: All Python source files.
- `tests`: Tests (starting with `test_`).

In the repository root:
- `.gitattributes` and `.gitignore` for GitHub.
- `LICENSE`: Text of MIT License.
- `README.md`: Readme file (Markdown) for GitHub.
- `requirements.txt`: Required libraries, currently listed without version specifications.
- `installer.cfg` and `installer.nsi`: Configuration files for building the installer with pynsist/NSIS installer.
- `SBEMimage.bat`: Windows batch file to run SBEMimage (works for both the system Python and the Python interpreter plus packages installed by the NSIS installer).

## Conventions

- Use PEP8 (https://pep8.org) as a general guideline.
- Use four spaces as one unit of indentation. Do not mix spaces and tabs.
- Use `snake_case` for all variable names, functions, and filenames:
  - `grid_index`
  - `very_long_variable_name`
  - `load_parameters()`
  - `my_module.py`
- Note that PyQt uses camelCase style (`pushButton`, `setWindowIcon()`). You can keep this style when naming PyQt GUI elements.
- Follow established naming patterns and conventions and aim for consistency with existing code. Example: when referring to the index of a tile, use `tile_index` (not `tile` or `tile_number`).

## Architecture Overview

- The application is launched from `sbemimage.py`.
- The Main Controls window is created first as a `QMainWindow`, and the Viewport window is created from Main Controls as a `QWidget`.
- Dialog windows associated with Main Controls are implemented in `main_controls_dlg_windows.py`; those associated with the Viewport are in `viewport_dlg_windows.py`.
- `main_controls.py` contains the startup routine and the Main Controls GUI.
- `viewport.py` contains all code for the Viewport, the Slice-by-slice Viewer, and the Acquisition Monitor.
- The acquisition loop `run()` in `acquisition.py` is started from Main Controls and runs in a thread.

The elements to be acquired and/or displayed are managed by:
- `grid_manager`: for the tile grids
- `overview_manager`: for the ROI overviews and the stub overview
- `imported_images`: for imported single images

Abbreviations used throughout SBEMimage:
- `self.gm`: instance of `grid_manager`
- `self.ovm`: instance of `overview_manager`

Hardware control:
- Base classes are provided in `sem_control.py` and `microtome_control.py`.
- Implementations for different manufacturers use the same name followed by `_` and the brand name, for example: `sem_control_zeiss.py`.

Supporting modules:
- `image_inspector.py`: image integrity and quality checks (including debris detection) for overview and tile images.
- `coordinate_system.py`: conversion between stage, SEM, and viewport coordinates.
- `utils.py`: constants and helper functions.

## Git Workflow

- The `master` branch contains tested code ready for production use.
- `master` is protected; currently only `btitze` can push to this branch.
- The `dev` branch is used for ongoing development.
- Developers familiar with the code base may work directly on `dev`.
- Pull requests to `dev` are welcome, ideally from short-lived feature branches.
- If you want to develop new functionality or suggest larger structural changes, contact `btitze AT protonmail.ch` first or post on SBEMimage GitHub Issues.
