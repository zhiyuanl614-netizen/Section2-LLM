@echo off
setlocal
set HERE=%~dp0
set PLATFORM_ROOT=%HERE%platform
if not defined PLATFORM_RELEASE_DIR set PLATFORM_RELEASE_DIR=%PLATFORM_ROOT%\data\releases\B001-v1.2-text-scope-preview-20261010
if not defined PLATFORM_HOST set PLATFORM_HOST=127.0.0.1
if not defined PLATFORM_PORT set PLATFORM_PORT=8765
where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py -3 "%HERE%launcher.py" %*
) else (
  python "%HERE%launcher.py" %*
)
endlocal
