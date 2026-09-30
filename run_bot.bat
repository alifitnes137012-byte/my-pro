@echo off
cd /d "%~dp0"

where python >nul 2>nul || (
  echo Python is not installed. Install it from python.org and tick "Add python.exe to PATH".
  pause
  exit /b
)

if exist token.txt goto run
set /p TOKEN="Paste your bot token from BotFather, then press Enter: "
>token.txt echo %TOKEN%

:run
set /p TELEGRAM_BOT_TOKEN=<token.txt
echo Installing requirements...
python -m pip install -q -r bot\requirements.txt
echo.
echo Bot is running. Keep this window open. Close it to stop the bot.
python -m bot.main
pause
