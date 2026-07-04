# PyInstaller hooks

Custom PyInstaller hooks for TextToCAD. This directory is on `hookspath` in
`packaging/texttocad.spec`.

Normally empty: `collect_all(...)` in the spec plus PySide6's bundled hook cover the
native libraries (cadquery/OCP/VTK/pyvista). If a **clean-VM smoke test** surfaces a
missing DLL or a lazily-imported submodule, add a `hook-<module>.py` here, e.g.:

```python
# hook-some_module.py
from PyInstaller.utils.hooks import collect_all
datas, binaries, hiddenimports = collect_all("some_module")
```
