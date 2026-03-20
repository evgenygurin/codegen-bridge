: ; # Cross-platform polyglot hook wrapper (Windows CMD / Unix shell)
: ; # On Unix: runs as shell script. On Windows: runs as CMD batch.
: ; # Usage: run-hook.cmd <hook-name> [args...]
: ; exec bash "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/$1.sh" "${@:2}" 2>/dev/null || exec sh "${CLAUDE_PLUGIN_ROOT}/hooks/scripts/$1.sh" "${@:2}"
: ; exit

@echo off
setlocal enabledelayedexpansion

set "HOOK_NAME=%~1"
if "%HOOK_NAME%"=="" (
    echo {"error": "No hook name provided"}
    exit /b 1
)

set "SCRIPT=%CLAUDE_PLUGIN_ROOT%\hooks\scripts\%HOOK_NAME%.sh"

:: Try Git Bash first (most common on Windows with git installed)
where git >nul 2>nul
if %errorlevel% equ 0 (
    for /f "tokens=*" %%i in ('git --exec-path') do set "GIT_EXEC=%%i"
    set "GIT_DIR=!GIT_EXEC:\libexec\git-core=!"
    if exist "!GIT_DIR!\bin\bash.exe" (
        "!GIT_DIR!\bin\bash.exe" "%SCRIPT%" %*
        exit /b %errorlevel%
    )
)

:: Try WSL
where wsl >nul 2>nul
if %errorlevel% equ 0 (
    wsl bash "%SCRIPT%" %*
    exit /b %errorlevel%
)

:: Try MSYS2
if exist "C:\msys64\usr\bin\bash.exe" (
    "C:\msys64\usr\bin\bash.exe" "%SCRIPT%" %*
    exit /b %errorlevel%
)

echo {"error": "No bash found. Install Git for Windows, WSL, or MSYS2."}
exit /b 1
