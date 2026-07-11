import subprocess, sys, webbrowser, time, os
print('Starting Trend Radar X website...')
proc=subprocess.Popen([sys.executable,'app.py'])
time.sleep(1)
webbrowser.open('http://127.0.0.1:5000')
print('Website running. Close this window or Ctrl+C to stop.')
try:
    proc.wait()
except KeyboardInterrupt:
    proc.terminate()
