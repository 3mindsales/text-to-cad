@echo off
REM ---------------------------------------------------------------------------
REM build_windows.bat - clean-venv build of the TextToCAD one-folder bundle.
REM SPEC 11.1/11.3. Requires Python 3.11 (py -3.11) and internet ONLY at build
REM time to fetch wheels; the RESULT runs fully offline.
REM ---------------------------------------------------------------------------
setlocal
set "ROOT=%~dp0.."
pushd "%ROOT%"

echo [1/4] Creating clean build venv (.buildvenv) ...
py -3.11 -m venv .buildvenv || goto :fail
call .buildvenv\Scripts\activate.bat

echo [2/4] Installing pinned dependencies ...
python -m pip install --upgrade pip || goto :fail
pip install -r requirements.txt || goto :fail
pip install pyinstaller==6.5.0 || goto :fail

echo [3/4] Building one-folder bundle with PyInstaller ...
pyinstaller packaging\texttocad.spec --noconfirm || goto :fail

echo [4/4] Done. Bundle at: dist\TextToCAD\TextToCAD.exe
echo Remember to place bin\ollama.exe and run scripts\install_models.bat on the target.
popd
endlocal
exit /b 0

:fail
echo [ERROR] Build failed.
popd
endlocal
exit /b 1
