@echo off
echo 正在启动报修系统服务，请稍候...
start "" python app.py
timeout /t 5 /nobreak >nul
start "" http://127.0.0.1:5000/login
pause