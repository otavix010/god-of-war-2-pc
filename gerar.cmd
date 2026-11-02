@echo off
rem Clique duas vezes: gera e compila o port a partir da sua ISO (veja o README).
rem Pede a ISO numa janela; tambem aceita os parametros do gerar.ps1 (-Iso -Jobs -RefazerDe).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0gerar.ps1" %*
echo.
pause
