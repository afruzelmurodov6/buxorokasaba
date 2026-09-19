import logging
from html import escape

from aiohttp import web

import database as db
from utils import format_time_left, get_voting_status

logger = logging.getLogger(__name__)

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="20">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Buxoro Kasaba Uyushmasi — Ovoz berish natijalari</title>
<style>
  body {{
    font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif;
    background: #0f172a;
    color: #f1f5f9;
    margin: 0;
    padding: 24px 16px 60px;
  }}
  .container {{ max-width: 640px; margin: 0 auto; }}
  h1 {{
    text-align: center;
    font-size: 22px;
    margin-bottom: 4px;
  }}
  .subtitle {{
    text-align: center;
    color: #94a3b8;
    font-size: 14px;
    margin-bottom: 24px;
  }}
  .status {{
    text-align: center;
    font-size: 14px;
    margin-bottom: 24px;
    padding: 10px;
    border-radius: 10px;
    background: #1e293b;
  }}
  .row {{
    display: flex;
    align-items: center;
    gap: 12px;
    background: #1e293b;
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 10px;
  }}
  .rank {{ font-size: 20px; width: 28px; text-align: center; flex-shrink: 0; }}
  .info {{ flex: 1; min-width: 0; }}
  .title {{ font-weight: 600; font-size: 15px; margin-bottom: 6px; }}
  .bar-bg {{
    background: #334155;
    border-radius: 6px;
    height: 8px;
    overflow: hidden;
  }}
  .bar-fill {{
    background: linear-gradient(90deg, #38bdf8, #6366f1);
    height: 100%;
  }}
  .votes {{ font-size: 13px; color: #94a3b8; margin-top: 6px; }}
  .empty {{ text-align: center; color: #94a3b8; margin-top: 40px; }}
</style>
</head>
<body>
<div class="container">
  <h1>🏛 Buxoro Kasaba Uyushmasi</h1>
  <div class="subtitle">Video ovoz berish natijalari</div>
  <div class="status">{status_text}</div>
  {rows_html}
</div>
</body>
</html>
"""

MEDALS = ["🥇", "🥈", "🥉"]


async def build_results_html() -> str:
    videos = await db.get_results()
    total_votes = sum(v["votes_count"] for v in videos)

    status = await get_voting_status()
    if status == "not_started":
        status_text = "⏳ Ovoz berish hali boshlanmagan"
    elif status == "active":
        _, end_iso = await db.get_voting_period()
        status_text = f"⏰ Ovoz berish tugashiga: {format_time_left(end_iso)} qoldi"
    elif status == "ended":
        status_text = "🔒 Ovoz berish yakunlangan"
    else:
        status_text = "🗳 Ovoz berish davom etmoqda"

    if not videos:
        rows_html = '<div class="empty">Hozircha videolar mavjud emas.</div>'
    else:
        rows = []
        for i, video in enumerate(videos):
            rank = MEDALS[i] if i < 3 else str(i + 1)
            percent = (video["votes_count"] / total_votes * 100) if total_votes > 0 else 0
            title = escape(video["title"])
            rows.append(
                f'<div class="row">'
                f'<div class="rank">{rank}</div>'
                f'<div class="info">'
                f'<div class="title">{title}</div>'
                f'<div class="bar-bg"><div class="bar-fill" style="width:{percent:.1f}%"></div></div>'
                f'<div class="votes">{video["votes_count"]} ta ovoz — {percent:.1f}%</div>'
                f'</div></div>'
            )
        rows_html = "\n".join(rows)

    return PAGE_TEMPLATE.format(status_text=status_text, rows_html=rows_html)


async def handle_index(request: web.Request) -> web.Response:
    html = await build_results_html()
    return web.Response(text=html, content_type="text/html")


async def handle_health(request: web.Request) -> web.Response:
    return web.Response(text="OK")


def create_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/health", handle_health)
    return app


async def start_webserver(port: int) -> None:
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info(f"Veb-server {port}-portda ishga tushdi.")
