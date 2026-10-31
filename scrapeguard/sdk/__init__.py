"""
ScrapeGuard SDK — @monitor + ctx.select
Usage:
  from scrapeguard.sdk import monitor, ctx
  @monitor(project="moneycontrol-gainers")
  def scrape(ctx):
      rows = ctx.select("gainer_rows", "table.gainers > tbody > tr.row")
      ...
"""
from .client import monitor, ctx, ScrapeGuardContext
__all__ = ["monitor", "ctx", "ScrapeGuardContext"]
