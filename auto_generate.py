from radar.db import connect, rows
from radar.auto_studio import generate_simple_draft
from radar.config import CONFIG
from rich.console import Console
console=Console()
con=connect(CONFIG.db_path)
videos=rows(con, "SELECT * FROM videos WHERE auto_recreate_score>=45 ORDER BY opportunity_score DESC LIMIT 10")
if not videos:
    console.print('[yellow]No Auto Studio candidates yet. Run py trend_radar.py first.[/]')
else:
    for v in videos[:3]:
        out=generate_simple_draft(v)
        console.print(f'[green]Generated:[/] {out}')
