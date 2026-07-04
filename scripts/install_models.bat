@echo off
REM ---------------------------------------------------------------------------
REM install_models.bat - assemble the side-loaded Ollama model pack OFFLINE.
REM SPEC 11.2: copies the shipped model blobs into a local models directory and
REM points OLLAMA_MODELS at it. NO download occurs (air-gapped).
REM
REM Usage:  scripts\install_models.bat [model_pack_folder]
REM Default model_pack_folder = "model_pack" next to this script's parent.
REM ---------------------------------------------------------------------------
setlocal
set "PACK=%~1"
if "%PACK%"=="" set "PACK=%~dp0..\model_pack"
set "DEST=%~dp0..\models"

if not exist "%PACK%" (
  echo [ERROR] Model pack folder not found: "%PACK%"
  echo Provide the folder that contains the Ollama blobs / manifests shipped on the media.
  exit /b 1
)

echo Copying model blobs from "%PACK%" to "%DEST%" ...
if not exist "%DEST%" mkdir "%DEST%"
xcopy /E /I /Y "%PACK%\*" "%DEST%\" >nul
if errorlevel 1 (
  echo [ERROR] Copy failed.
  exit /b 1
)

echo Setting OLLAMA_MODELS to "%DEST%" (persisted for this user) ...
setx OLLAMA_MODELS "%DEST%" >nul

echo Done. Model pack installed offline. Restart TextToCAD - it will detect the model.
endlocal
