@echo off
cd /d "%~dp0"
call .venv\Scripts\activate
echo [Running Batch Processor] %date% %time%
python batch_processor.py
echo Done.
