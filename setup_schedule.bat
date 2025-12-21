@echo off
echo Registering CRM Batch Processor Task...
echo Run time: Daily at 17:00
echo Target: "%~dp0run_batch.bat"

schtasks /create /tn "CRM_Messenger_Batch" /tr "\"%~dp0run_batch.bat\"" /sc daily /st 17:00 /f

if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] Task registered successfully!
    echo It will run automatically every day at 5:00 PM.
) else (
    echo.
    echo [ERROR] Failed to register task. Please run as Administrator.
)
pause
