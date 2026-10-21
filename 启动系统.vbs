Set WshShell = CreateObject("WScript.Shell")
' 后台静默启动Flask，完全隐藏黑窗口
WshShell.Run "cmd /c python app.py", 0, False
' 等6秒让服务完全启动
WScript.Sleep 6000
' 自动打开登录页面
WshShell.Run "http://127.0.0.1:5000/login"