from rich.console import Console
from radar.scanner import run_scan
from radar.reports import render_site
from radar.sound_intel import build_sound_report
from radar.db import connect, rows
from radar.config import CONFIG

console=Console()
if __name__=='__main__':
    console.print('[bold cyan]Trend Radar X Creator AI[/]')
    usable=run_scan()
    con=connect(CONFIG.db_path)
    all_rows=rows(con)
    build_sound_report(all_rows)
    render_site()
    console.print('[bold green]Done.[/] Open outputs/site/index.html')
