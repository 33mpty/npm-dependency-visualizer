@echo off
setlocal
chcp 65001 >nul
pushd "%~dp0" || exit /b 1
where py >nul 2>nul
if errorlevel 1 (
    python -X utf8 -m src.depviz %*
) else (
    py -3 -X utf8 -m src.depviz %*
)
set "status=%errorlevel%"
popd
exit /b %status%
