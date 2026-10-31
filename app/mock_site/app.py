from flask import Flask, render_template_string, request
import random

app = Flask(__name__)

BASE_TABLE = """
<table class="gainers">
  <thead><tr><th>Symbol</th><th>Price</th><th>Change %</th></tr></thead>
  <tbody>
    <tr class="{row_class}"><td class="sym">RELIANCE</td><td class="price">1,482.10</td><td class="change">+2.14%</td></tr>
    <tr class="{row_class}"><td class="sym">TCS</td><td class="price">3,905.40</td><td class="change">+1.82%</td></tr>
    <tr class="{row_class}"><td class="sym">INFY</td><td class="price">1,621.00</td><td class="change">+1.44%</td></tr>
    <tr class="{row_class}"><td class="sym">HDFC</td><td class="price">1,120.00</td><td class="change">+0.98%</td></tr>
    <tr class="{row_class}"><td class="sym">ICICI</td><td class="price">945.30</td><td class="change">+0.72%</td></tr>
  </tbody>
</table>
<div id="nifty-widget" class="card"><div class="card-head">NIFTY 50</div><div class="value">22,147.90</div></div>
"""

SHELL = """<div id="app"></div><script src="/assets/app.9c12.js"></script><script>window.__NEXT_DATA__={"props":{}}</script><noscript>Enable JavaScript</noscript>"""

def wrap(inner, mutation="none", decoy=False):
    decoy_html = '<div class="ad-banner css-a1b2c3">Ad — ignore me</div><footer class="footer-v2">Footer changed</footer>' if decoy else ''
    nav = '<nav class="css-x9k3l2">Markets</nav>'
    if mutation=="insert_wrapper":
        inner = inner.replace("<tbody>", '<div class="wrap"><tbody>').replace("</tbody>", "</tbody></div>")
    if mutation=="reorder":
        inner = inner.replace("<th>Symbol</th><th>Price</th><th>Change %</th>", "<th>Price</th><th>Symbol</th><th>Change %</th>")
    if mutation=="remove_col":
        inner = inner.replace('<td class="change">+2.14%</td>', '').replace('<th>Change %</th>', '')
    if mutation=="table_to_div":
        inner = inner.replace("<table", "<div").replace("</table>", "</div>").replace("<tr", "<div").replace("</tr>", "</div>").replace("<td", "<span").replace("</td>", "</span>")
    return f"<html><body><main>{nav}{decoy_html}{inner}</main></body></html>"

@app.get("/markets/v1")
def v1():
    html = BASE_TABLE.format(row_class="row")
    return wrap(html, decoy=False)

@app.get("/markets/v2")
def v2():
    mut = request.args.get("mut", "rename")
    decoy = request.args.get("decoy", "1") == "1"
    if mut=="rename":
        html = BASE_TABLE.format(row_class="stock-row")
    elif mut=="empty":
        html = SHELL
    elif mut=="decoy_only":
        html = BASE_TABLE.format(row_class="row")
        mut="none"
    else:
        html = BASE_TABLE.format(row_class="row")
    return wrap(html, mutation=mut, decoy=decoy)

@app.get("/markets/variants/<name>")
def variant(name):
    mapping = {
        "rename_row": ("rename", True),
        "insert_wrapper": ("insert_wrapper", True),
        "remove_column": ("remove_col", True),
        "reorder_columns": ("reorder", True),
        "table_to_div": ("table_to_div", True),
        "empty_js_shell": ("empty", True),
        "decoy_only": ("none", True),
    }
    mut, decoy = mapping.get(name, ("rename", True))
    if mut=="empty":
        return SHELL
    html = BASE_TABLE.format(row_class="stock-row" if name=="rename_row" else "row")
    return wrap(html, mutation=mut, decoy=decoy)

@app.get("/health")
def health(): return {"ok": True}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
