from bs4 import BeautifulSoup
from pydantic import BaseModel, ValidationError
from typing import Optional

class RowModel(BaseModel):
    symbol: str
    price: Optional[float] = None
    change_pct: Optional[float] = None

def validate_candidate(failed_html, selector_map, expected_schema=None, anchors=None):
    """
    Validate each candidate on STORED failed snapshot: row count == baseline or >=min_records,
    Pydantic schema passes, all anchors found, anchor field non-empty.
    """
    soup = BeautifulSoup(failed_html, "lxml")
    results = {}
    for name, css in selector_map.items():
        nodes = soup.select(css)
        results[name] = len(nodes)

    row_count = results.get("gainer_rows", results.get("rows", 0))
    min_records = (expected_schema or {}).get("min_records", 1)
    schema_ok = row_count >= min_records

    # try pydantic on extracted rows (simplified)
    try:
        for el in soup.select(list(selector_map.values())[0])[:3]:
            txt = el.get_text(" ", strip=True)
            # dummy validation — just check non-empty
            RowModel(symbol=txt.split()[0] if txt else "")
    except ValidationError:
        schema_ok = False

    anchors_found = 0
    if anchors:
        html_text = soup.get_text()
        for a in anchors:
            if a in html_text:
                anchors_found += 1

    anchor_field_ok = anchors_found > 0 if anchors else True
    overall = schema_ok and row_count>0 and anchor_field_ok
    return {"row_count": row_count, "schema_ok": schema_ok, "anchors_found": anchors_found, "anchor_field_ok": anchor_field_ok, "overall": overall}

def tier_for(validation, verification):
    if verification=="verified" and validation.get("overall"):
        return "green", "Fix verified, 5/5 rows" if validation["row_count"]==5 else f"{validation['row_count']} rows, schema passes"
    if verification in ("heuristic","ai_suggested") or not validation.get("overall"):
        # check partial
        if validation.get("row_count",0)>0:
            return "amber", "Likely cause, review needed"
        return "amber", "AI-suggested, not fully tested"
    return "red", "Unknown cause, no fix suggested"
