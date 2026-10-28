#!/usr/bin/env python3
"""Extrait d'un fichier macOS .keylayout la table code-touche -> caractère
pour les couches utiles (base, ⇧, ⌥, ⇧⌥, ⌃⇧⌥, ⌘, ⇧⌘).
Usage : python3 extract_keylayout.py <fichier.keylayout> <sortie.json>"""
import html, json, re, sys

def parse(path):
    t = open(path, encoding="utf-8").read()
    # actions
    actions = {}
    for a in re.finditer(r'<action id="([^"]*)">(.*?)</action>', t, re.S):
        aid = html.unescape(a.group(1))
        body = a.group(2)
        m = re.search(r'<when state="none"\s+(output|next)="([^"]*)"', body)
        actions[aid] = (m.group(1), html.unescape(m.group(2))) if m else None
    terms = {html.unescape(m.group(1)): html.unescape(m.group(2))
             for m in re.finditer(r'<when state="([^"]*)" output="([^"]*)"/>', t)
             if False}
    for m in re.finditer(r'<terminators>(.*?)</terminators>', t, re.S):
        for w in re.finditer(r'<when state="([^"]*)" output="([^"]*)"', m.group(1)):
            terms[html.unescape(w.group(1))] = html.unescape(w.group(2))
    iso = t[t.index('<keyMapSet id="ISO">'):]
    iso = iso[:iso.index('</keyMapSet>')]
    maps = {}
    for m in re.finditer(r'<keyMap index="(\d+)">(.*?)</keyMap>', iso, re.S):
        d = {}
        for k in re.finditer(r'<key code="(\d+)"\s+(output|action)="([^"]*)"', m.group(2)):
            code, typ, val = int(k.group(1)), k.group(2), html.unescape(k.group(3))
            if typ == "output":
                d[code] = {"c": val}
            else:
                act = actions.get(val)
                if act is None:
                    d[code] = {"c": val}
                elif act[0] == "output":
                    d[code] = {"c": act[1]}
                else:  # touche morte
                    d[code] = {"c": terms.get(act[1], val), "dead": True}
        maps[int(m.group(1))] = d
    names = {0: "base", 1: "shift", 2: "caps", 3: "shift_caps", 4: "alt", 5: "shift_alt", 8: "ctrl_shift_alt", 9: "cmd", 10: "shift_cmd"}
    return {names[i]: {str(k): v for k, v in maps[i].items()} for i in names if i in maps}

if __name__ == "__main__":
    data = parse(sys.argv[1])
    data["_source"] = sys.argv[1].split("/")[-1]
    json.dump(data, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print("ok", {k: len(v) for k, v in data.items() if isinstance(v, dict)})
