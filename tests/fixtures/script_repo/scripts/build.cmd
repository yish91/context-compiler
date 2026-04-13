@echo off
REM Build script
set APP_ENV=production
call scripts\compile.cmd
:build
echo Building project
goto :eof
