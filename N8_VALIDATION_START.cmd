@echo off
setlocal
cd /d "%~dp0"

echo ANTHBOT N8 validation helper
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\n8_validation_windows.ps1"
set "rc=%ERRORLEVEL%"

echo.
if not "%rc%"=="0" (
  echo HIBA: a validation helper hibaval allt le. Kod: %rc%
) else (
  echo KESZ. A n8_validation_diff.json es n8_validation_summary.txt fajlt kuldd vissza elemzesre.
)
echo.
pause
exit /b %rc%
