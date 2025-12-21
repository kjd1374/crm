@echo off
title CRM Messenger Listener
echo CRM Messenger Listener started.
echo Monitoring 'messenger_log.txt' for keywords (발주, 문의, 완료)...
echo Keep this window OPEN to maintain the link.
echo.
cd /d "%~dp0"
python messenger_listener.py
pause
