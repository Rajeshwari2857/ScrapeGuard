from bs4 import BeautifulSoup
def build_ops(diff):
    ops=[]
    for old,new in diff.get("rename_pairs", []):
        old_cls = old.split(".")[-1] if "." in old else ""
        new_cls = new.split(".")[-1] if "." in new else ""
        loc="/".join(old.split("/")[:-1])
        ops.append({"type":"rename_class","location":loc,"before":old_cls,"after":new_cls,"old_path":old,"new_path":new})
    if diff.get("tag_changed"):
        ops.append({"type":"change_tag","location":"table","before":"table","after":"div"})
    for r in diff.get("removed", [])[:5]:
        if r not in [p[0] for p in diff.get("rename_pairs",[])]:
            ops.append({"type":"remove_node","location":r,"before":r,"after":None})
    for a in diff.get("added", [])[:5]:
        if a not in [p[1] for p in diff.get("rename_pairs",[])]:
            ops.append({"type":"insert_wrapper","location":a,"before":None,"after":a})
    return ops

def apply_op(html, op):
    soup=BeautifulSoup(html,"lxml")
    t=op["type"]
    if t=="rename_class":
        before=op["before"]; after=op["after"]
        for el in soup.select(f".{before}"):
            classes=el.get("class", [])
            if before in classes:
                classes=[after if c==before else c for c in classes]
                el["class"]=classes
    return str(soup)
