@echo off
cd /d %~dp0
echo [%date% %time%] 正在启动定时任务... >> daily_task_debug.log
:: 运行脚本并捕捉所有错误到 daily_task_debug.log
python daily_report_worker.py >> daily_task_debug.log 2>&1
echo [%date% %time%] 任务执行结束。 >> daily_task_debug.log
exit
