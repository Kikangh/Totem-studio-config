#!/usr/bin/env python3
"""Génère une page HTML interactive qui représente la keymap ZMK du Totem
(calques, combos, macros) avec les caractères réellement produits par la
disposition Optimot sur macOS.

Usage (depuis la racine du dépôt) :
    python3 tools/totem_viz.py                  # -> tools/totem-viz.html
    python3 tools/totem_viz.py --keylayout "…/Optimot-Qu.keylayout"   # relit la disposition
Options : --out FICHIER, --fragment (sans <html>/<body>, pour publication)
"""
import argparse, json, os, re, sys, datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = os.path.join(ROOT, "config")
SHIELD = os.path.join(ROOT, "boards", "shields", "totem")
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- utilitaires
def strip_block_comments(t):
    return re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), t, flags=re.S)

def strip_line_comment(line):
    i = line.find("//")
    return (line[:i], line[i + 2:].strip()) if i >= 0 else (line, "")

def parse_defines(text, groups=False):
    """#define NOM valeur (macros sans paramètres). Optionnellement, rattache
    chaque define au dernier commentaire '//Groupe' rencontré."""
    defs, meta, group = {}, {}, None
    for raw in strip_block_comments(text).splitlines():
        code, com = strip_line_comment(raw)
        s = code.strip()
        if not s and com and groups and re.fullmatch(r"[A-Za-z0-9 ./&+-]{2,30}", com):
            group = com
        m = re.match(r"#define\s+([A-Za-z_]\w*)\s+(.+)$", s)
        if m and "(" not in m.group(1):
            defs[m.group(1)] = m.group(2).strip()
            meta[m.group(1)] = {"group": group, "comment": com}
    return defs, meta

def expand(expr, defs, depth=0):
    if depth > 12:
        return expr
    out = re.sub(r"\b[A-Za-z_]\w*\b", lambda m: defs.get(m.group(0), m.group(0)), expr)
    return out if out == expr else expand(out, defs, depth + 1)

# ------------------------------------------------- HID -> code touche macOS
# Positions ANSI de macOS ; GRAVE et NUBS suivent l'inversion des claviers ISO
# (vérifiée avec OP_DLR = GRAVE -> $ et OP_K = NUBS -> k).
HID2VK = {
 "A":0,"S":1,"D":2,"F":3,"H":4,"G":5,"Z":6,"X":7,"C":8,"V":9,"B":11,"Q":12,"W":13,"E":14,
 "R":15,"Y":16,"T":17,"N1":18,"N2":19,"N3":20,"N4":21,"N6":22,"N5":23,"EQUAL":24,"N9":25,
 "N7":26,"MINUS":27,"N8":28,"N0":29,"RBKT":30,"O":31,"U":32,"LBKT":33,"I":34,"P":35,
 "L":37,"J":38,"SQT":39,"K":40,"SEMI":41,"BSLH":42,"COMMA":43,"FSLH":44,"N":45,"M":46,
 "DOT":47,"GRAVE":10,"NUBS":50,"SPACE":49,
}
ALIAS = {"NUMBER_%d" % i: "N%d" % i for i in range(10)}
ALIAS.update({"LEFT_BRACKET":"LBKT","RIGHT_BRACKET":"RBKT","APOS":"SQT","APOSTROPHE":"SQT",
 "SINGLE_QUOTE":"SQT","SEMICOLON":"SEMI","SLASH":"FSLH","BACKSLASH":"BSLH","PERIOD":"DOT",
 "NON_US_BACKSLASH":"NUBS","NON_US_BSLH":"NUBS","EQUALS":"EQUAL","RETURN":"RET","ENTER":"RET",
 "BACKSPACE":"BSPC","DELETE":"DEL","ESCAPE":"ESC","SPC":"SPACE","PAGE_UP":"PG_UP",
 "PAGE_DOWN":"PG_DN","CAPSLOCK":"CAPS","LEFT_ARROW":"LEFT","RIGHT_ARROW":"RIGHT",
 "UP_ARROW":"UP","DOWN_ARROW":"DOWN","LSHIFT":"LSHFT","RSHIFT":"RSHFT","LCTL":"LCTRL",
 "RCTL":"RCTRL","LCMD":"LGUI","RCMD":"RGUI","LMETA":"LGUI","RMETA":"RGUI","LOPT":"LALT",
 "ROPT":"RALT","SCROLLLOCK":"SLCK","KP_NUMLOCK":"KP_NUM"})

SPECIAL = {
 "RET":("↵","Entrée"),"BSPC":("⌫","Retour arr."),"DEL":("⌦","Suppr"),"TAB":("⇥","Tab"),
 "ESC":("⎋","Échap"),"SPACE":("␣","Espace"),"LEFT":("←",""),"RIGHT":("→",""),"UP":("↑",""),
 "DOWN":("↓",""),"HOME":("⇱","Début"),"END":("⇲","Fin"),"PG_UP":("⇞","Page ↑"),
 "PG_DN":("⇟","Page ↓"),"CAPS":("⇪","Verr. maj"),"SLCK":("ScrLk",""),"KP_NUM":("Num",""),
 "LSHFT":("⇧",""),"RSHFT":("⇧",""),"LCTRL":("⌃",""),"RCTRL":("⌃",""),"LALT":("⌥",""),
 "RALT":("⌥",""),"LGUI":("⌘",""),"RGUI":("⌘",""),
 "C_MUTE":("🔇","Muet"),"C_VOL_UP":("🔊","Vol +"),"C_VOL_DN":("🔉","Vol −"),
 "C_PREV":("⏮","Préc."),"C_NEXT":("⏭","Suiv."),"C_PP":("⏯","Lecture"),
 "C_PLAY_PAUSE":("⏯","Lecture"),
 "KP_PLUS":("+","pavé"),"KP_MINUS":("−","pavé"),"KP_MULTIPLY":("×","pavé"),
 "KP_SLASH":("÷","pavé"),"KP_EQUAL":("=","pavé"),"KP_DOT":(".","pavé"),"KP_COMMA":(",","pavé"),
}
for i in range(10):
    SPECIAL["KP_N%d" % i] = (str(i), "pavé")
for i in range(1, 25):
    SPECIAL["F%d" % i] = ("F%d" % i, "")

MODFN = {"LS":"S","RS":"S","LC":"C","RC":"C","LA":"A","RA":"A","LG":"G","RG":"G"}
MODGLYPH = [("C","⌃"),("A","⌥"),("S","⇧"),("G","⌘")]
MODKEY = {"LSHFT":"S","RSHFT":"S","LCTRL":"C","RCTRL":"C","LALT":"A","RALT":"A","LGUI":"G","RGUI":"G"}

def pretty_char(c):
    return {" ":"␣"," ":"⍽"," ":"⍽"}.get(c, c)

class Translator:
    def __init__(self, table, defs, user_meta):
        self.t, self.defs, self.meta = table, defs, user_meta

    def split_mods(self, expr):
        mods, e = set(), expr.strip()
        while True:
            m = re.fullmatch(r"(LS|RS|LC|RC|LA|RA|LG|RG)\((.*)\)", e)
            if not m:
                break
            mods.add(MODFN[m.group(1)]); e = m.group(2).strip()
        return mods, e

    def char(self, base, mods, caps=False):
        vk = HID2VK.get(base)
        if vk is None:
            return None
        if "G" in mods or "C" in mods:
            layer = "cmd"
        elif caps and "A" not in mods:
            layer = "shift_caps" if "S" in mods else "caps"
        else:
            layer = {frozenset(): "base", frozenset("S"): "shift", frozenset("A"): "alt",
                     frozenset("SA"): "shift_alt"}[frozenset(mods)]
        e = self.t.get(layer, {}).get(str(vk))
        return e

    def key(self, expr, caps=False):
        """-> dict(t=libellé principal, s=sous-libellé, raw=forme QWERTY, name=define utilisateur)"""
        expr = expr.strip()
        name = None
        if re.fullmatch(r"[A-Z_][A-Z0-9_]*", expr) and expr in self.meta and not expr.startswith("OP_"):
            name = expr
        full = expand(expr, self.defs)
        mods, base = self.split_mods(full)
        base = ALIAS.get(base, base)
        raw = full
        dead = False
        if base in MODKEY and not mods:
            t, s = SPECIAL[base][0], {"S":"Shift","C":"Ctrl","A":"Option","G":"Cmd"}[MODKEY[base]]
        elif base in HID2VK:
            e = self.char(base, mods, caps) or {"c": "?"}
            c = pretty_char(e["c"]); dead = bool(e.get("dead"))
            if "G" in mods or "C" in mods:
                t = "".join(g for k, g in MODGLYPH if k in mods) + c.upper()
                s = ""
            else:
                t, s = c, ("morte" if dead else "")
        elif base in SPECIAL:
            g, s = SPECIAL[base]
            t = "".join(g2 for k, g2 in MODGLYPH if k in mods) + g
            if mods and not s:
                s = ""
        else:
            t = "".join(g for k, g in MODGLYPH if k in mods) + base
            s = ""
        if base == "SPACE" and not (mods & {"G", "C"}):
            c0 = (self.char(base, mods, caps) or {}).get("c", " ")
            s = {" ": "espace", "\u00a0": "insécable", "\u202f": "insécable fine"}.get(c0, s)
        d = {"t": t, "raw": raw, "q": full}
        if s: d["s"] = s
        if dead: d["dead"] = True
        if name:
            d["name"] = name
            g = self.meta[name].get("group")
            if g: d["app"] = g
        return d

# ------------------------------------------------------------- comportements
MOUSE_MOVES = {"MOVE_UP":"↑","MOVE_DOWN":"↓","MOVE_LEFT":"←","MOVE_RIGHT":"→",
               "SCRL_UP":"↑","SCRL_DOWN":"↓","SCRL_LEFT":"←","SCRL_RIGHT":"→"}
CLICKS = {"LCLK":"Clic G","RCLK":"Clic D","MCLK":"Clic M","MB4":"Bouton 4","MB5":"Bouton 5"}

def parse_behaviors(text):
    """Comportements définis par l'utilisateur (hold-tap, mod-morph, macros)."""
    res = {}
    for m in re.finditer(r"(\w+)\s*:\s*[\w-]+\s*\{([^{}]*)\}", text):
        label, body = m.group(1), m.group(2)
        comp = re.search(r'compatible\s*=\s*"zmk,behavior-([\w-]+)"', body)
        if not comp:
            continue
        b = {"kind": comp.group(1)}
        bm = re.search(r"bindings\s*=\s*(.*?);", body, re.S)
        if bm:
            b["bindings"] = [x.strip() for x in re.findall(r"<([^>]*)>", bm.group(1))]
        lm = re.search(r'label\s*=\s*"([^"]*)"', body)
        if lm: b["label"] = lm.group(1)
        mm = re.search(r"mods\s*=\s*<\(?([^>)]*)\)?>", body)
        if mm: b["mods"] = mm.group(1)
        res[label] = b
    return res

class Renderer:
    def __init__(self, tr, layers_idx, behaviors):
        self.tr, self.L, self.B = tr, layers_idx, behaviors

    def lname(self, x):
        x = expand(x, self.tr.defs)
        try:
            return self.L[int(x)]
        except (ValueError, IndexError):
            return x

    def binding(self, b):
        toks = b.split()
        beh, args = toks[0].lstrip("&"), toks[1:]
        k = self.tr.key
        if beh == "kp":   return {**k(args[0]), "kind": "key"}
        if beh == "trans": return {"t": "", "kind": "trans", "raw": "&trans"}
        if beh == "none":  return {"t": "", "kind": "none", "raw": "&none"}
        if beh in ("mo",):  return {"t": self.lname(args[0]), "s": "maintien", "kind": "layer", "raw": b}
        if beh == "to":    return {"t": "→ " + self.lname(args[0]), "kind": "layer", "raw": b}
        if beh == "tog":   return {"t": "⇄ " + self.lname(args[0]), "kind": "layer", "raw": b}
        if beh == "sl":    return {"t": "◔ " + self.lname(args[0]), "kind": "layer", "raw": b}
        if beh == "mkp":   return {"t": CLICKS.get(args[0], args[0]), "kind": "mouse", "raw": b}
        if beh == "mmv":   return {"t": MOUSE_MOVES.get(args[0], args[0]), "s": "souris", "kind": "mouse", "raw": b}
        if beh == "msc":   return {"t": MOUSE_MOVES.get(args[0], args[0]), "s": "défil.", "kind": "mouse", "raw": b}
        if beh == "bt":
            a = " ".join(args)
            m = re.match(r"BT_SEL\s+(\d+)", a)
            t = ("BT " + m.group(1)) if m else {"BT_CLR": "BT ✕", "BT_NXT": "BT ▸", "BT_PRV": "BT ◂",
                                                 "BT_CLR_ALL": "BT ✕✕"}.get(a, a)
            return {"t": t, "s": "bluetooth" if m else "", "kind": "system", "raw": b}
        if beh == "out":   return {"t": {"OUT_TOG":"USB⇄BT","OUT_USB":"USB","OUT_BLE":"BT"}.get(args[0], args[0]), "kind": "system", "raw": b}
        if beh in ("bootloader", "sys_reset", "studio_unlock"):
            return {"t": {"bootloader":"Boot","sys_reset":"Reset","studio_unlock":"Studio"}[beh], "s": beh.replace("_"," "), "kind": "system", "raw": b}
        if beh in ("mt", "lt") or (beh in self.B and self.B[beh]["kind"] == "hold-tap"):
            if beh == "mt":   hold_b, tap_b = "kp", "kp"
            elif beh == "lt": hold_b, tap_b = "mo", "kp"
            else:
                hb = self.B[beh].get("bindings", ["&kp", "&kp"])
                hold_b, tap_b = hb[0].lstrip("&"), hb[1].lstrip("&")
            tap = self.binding("&%s %s" % (tap_b, args[1]))
            hold = self.binding("&%s %s" % (hold_b, args[0]))
            ht = hold["t"] if hold_b != "mo" else hold["t"]
            r = {**tap, "hold": ht, "holdKind": "layer" if hold_b == "mo" else "mod",
                 "raw": b, "beh": beh}
            if hold_b == "kp" and hold.get("s"): r["holdName"] = hold["s"]
            return r
        if beh in self.B and self.B[beh]["kind"] == "mod-morph":
            bb = self.B[beh]["bindings"]
            a, c = self.binding(bb[0]), self.binding(bb[1])
            mods = self.B[beh].get("mods", "")
            mg = "".join(g for key, g in (("CTL","⌃"),("ALT","⌥"),("SFT","⇧"),("GUI","⌘")) if key in mods)
            return {**a, "morph": mg + "+ → " + c["t"], "raw": b, "beh": beh}
        if beh in self.B and self.B[beh]["kind"] == "macro":
            return {"t": beh.replace("_", " "), "s": "macro", "kind": "macro", "macro": beh, "raw": b}
        return {"t": beh, "s": " ".join(args), "kind": "other", "raw": b}

def tokenize_bindings(s):
    return [m.group(0).strip() for m in re.finditer(r"&[\w-]+(?:\s+(?!&)[^\s&]+)*", s)]

# ------------------------------------------------------------------ parsing
def parse_layout(path):
    t = open(path, encoding="utf-8").read()
    keys = []
    for m in re.finditer(r"&key_physical_attrs\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+\(?(-?\d+)\)?\s+(\d+)\s+(\d+)", t):
        w, h, x, y, rot, rx, ry = map(int, m.groups())
        keys.append({"w": w, "h": h, "x": x, "y": y, "r": rot / 100, "rx": rx, "ry": ry})
    return keys

def parse_keymap(text):
    body = strip_block_comments(text)
    km = body[body.index('compatible = "zmk,keymap"'):]
    layers = []
    for m in re.finditer(r"(\w+)\s*\{(.*?)\}\s*;", km, re.S):
        blk = m.group(2)
        dn = re.search(r'display-name\s*=\s*"([^"]*)"', blk)
        bd = re.search(r"bindings\s*=\s*<(.*?)>\s*;", blk, re.S)
        if not bd:
            continue
        lines = [strip_line_comment(l)[0] for l in bd.group(1).splitlines()]
        layers.append({"node": m.group(1), "name": dn.group(1) if dn else m.group(1),
                       "bindings": tokenize_bindings(" ".join(lines))})
    return layers

def parse_combos(text):
    combos, section = [], None
    for raw in strip_block_comments(text).splitlines():
        s = raw.strip()
        if s.startswith("//"):
            c = s.lstrip("/").strip()
            if c and not c.startswith("COMBO"):
                section = c
            continue
        code, com = strip_line_comment(raw)
        m = re.match(r"\s*COMBO\(\s*([\w-]+)\s*,\s*(&[^,]+?)\s*,\s*([\d\s]+?)\s*,\s*([\w\s]+?)\s*,\s*(\d+)\s*,\s*(-?\d+)\s*\)", code)
        if m:
            combos.append({"id": m.group(1), "binding": m.group(2).strip(),
                           "keys": [int(x) for x in m.group(3).split()],
                           "layers": m.group(4).split(), "term": int(m.group(5)),
                           "idle": int(m.group(6)), "section": section, "comment": com})
    return combos

def macro_steps(beh, rd):
    """Suit la sémantique ZMK : &macro_tap / &macro_press / &macro_release
    fixent le mode appliqué aux comportements suivants (défaut : tap)."""
    out, verb, held, caps = [], "tape", [], False
    MODS = {"LSHFT": "LS", "RSHFT": "RS", "LCTRL": "LC", "RCTRL": "RC", "LALT": "LA", "RALT": "RA", "LGUI": "LG", "RGUI": "RG"}
    verbs = {"macro_tap": "tape", "macro_press": "presse", "macro_release": "relâche"}
    for item in beh.get("bindings", []):
        for tok in tokenize_bindings(item):
            parts = tok.split()
            ctl = parts[0].lstrip("&")
            if ctl in verbs:
                verb = verbs[ctl]
            elif ctl == "macro_pause_for_release":
                out.append({"verb": "attend", "t": "le relâchement", "kind": "note", "raw": tok})
            elif ctl == "macro_wait_time":
                out.append({"verb": "attend", "t": parts[1] + " ms", "kind": "note", "raw": tok})
            elif ctl in ("macro_tap_time", "macro_param_1to1", "macro_param_1to2", "macro_param_2to1", "macro_param_2to2"):
                continue
            else:
                p = tok.split()
                if p[0] == "&kp" and len(p) == 2:
                    k = expand(p[1], rd.tr.defs)
                    if k in MODS:
                        if verb == "presse": held.append(MODS[k])
                        elif verb == "relâche" and MODS[k] in held: held.remove(MODS[k])
                        out.append({"verb": verb, **rd.binding(tok)}); continue
                    if k in ("CAPS", "CAPSLOCK") and verb == "tape":
                        caps = not caps
                        out.append({"verb": verb, **rd.binding(tok), "s": "verr. maj " + ("activé" if caps else "désactivé")}); continue
                    e = k
                    for m in held: e = "%s(%s)" % (m, e)
                    b = {**rd.tr.key(e, caps=caps), "kind": "key"}
                    if held or caps: b["eff"] = True
                    out.append({"verb": verb, **b}); continue
                out.append({"verb": verb, **rd.binding(tok)})
    return out

# --------------------------------------------------------------- contrôles
def checks(data):
    notes = []
    names = [l["name"].upper() for l in data["layers"]]
    for c in data["combos"]:
        b = c["binding"].split()
        m = re.match(r"(?:to|tog|lay|mo)[-_]+([a-z]+)$", c["id"].lower())
        if b[0] in ("&to", "&tog", "&mo") and len(b) > 1 and m:
            w = m.group(1)
            exp = [n for n in names if n.lower().startswith(w) or w.startswith(n.lower())]
            tgt = c["out"]["target"]
            if exp and tgt.upper() not in exp:
                notes.append({"level": "warn", "combo": c["id"],
                    "text": "« %s » devrait activer %s d'après son nom, mais active %s (%s)."
                            % (c["id"], exp[0], tgt, " ".join(b))})
        if re.fullmatch(r"&\w+\s+\d+", c["binding"]) and b[0] in ("&to", "&tog", "&mo"):
            notes.append({"level": "info", "combo": c["id"],
                "text": "« %s » vise le calque par numéro (%s) ; un nom de calque (#define) résisterait mieux à un réordonnancement."
                        % (c["id"], b[1])})
        if any(re.fullmatch(r"\d+", l) for l in c["layer_tokens"]):
            notes.append({"level": "info", "combo": c["id"],
                "text": "« %s » liste ses calques par numéros (%s) : soit %s."
                        % (c["id"], " ".join(c["layer_tokens"]), ", ".join(data["layers"][i]["name"] for i in c["layers"]))})
    seen = {}
    for c in data["combos"]:
        for l in c["layers"]:
            key = (tuple(sorted(c["keys"])), l)
            if key in seen:
                notes.append({"level": "warn", "combo": c["id"],
                    "text": "« %s » et « %s » utilisent les mêmes touches sur %s."
                            % (seen[key], c["id"], data["layers"][l]["name"])})
            seen[key] = c["id"]
    return notes

# -------------------------------------------------------------------- main
def build(args):
    table = json.load(open(args.map, encoding="utf-8"))
    opt_defs, _ = parse_defines(open(os.path.join(CFG, "keymap_optimot.h"), encoding="utf-8").read())
    km_text = open(os.path.join(CFG, "totem.keymap"), encoding="utf-8").read()
    km_defs, km_meta = parse_defines(km_text, groups=True)
    defs = {**opt_defs, **km_defs}
    layer_defs = {k: int(v.split()[0]) for k, v in km_defs.items() if re.fullmatch(r"\d+(\s.*)?", v)}
    layers = parse_keymap(km_text)
    names = [l["name"] for l in layers]
    tr = Translator(table, defs, km_meta)
    behaviors = parse_behaviors(strip_block_comments(km_text))
    rd = Renderer(tr, names, behaviors)

    out_layers = [{"name": l["name"], "keys": [rd.binding(b) for b in l["bindings"]]} for l in layers]
    combos = []
    for c in parse_combos(open(os.path.join(CFG, "combos.dtsi"), encoding="utf-8").read()):
        idx = []
        for tok in c["layers"]:
            v = expand(tok, defs)
            if re.fullmatch(r"\d+", v): idx.append(int(v))
        o = rd.binding(c["binding"])
        b = c["binding"].split()
        if b[0] in ("&to", "&tog", "&mo"): o["target"] = rd.lname(b[1])
        combos.append({"id": c["id"], "binding": c["binding"], "keys": c["keys"], "layers": idx,
                       "layer_tokens": c["layers"], "term": c["term"], "idle": c["idle"],
                       "section": c["section"], "comment": c["comment"], "out": o})
    macros = []
    for name, b in behaviors.items():
        if b["kind"] == "macro":
            macros.append({"id": name, "label": b.get("label", ""), "steps": macro_steps(b, rd)})
    morphs = [{"id": n, "label": rd.binding("&" + n)} for n, b in behaviors.items() if b["kind"] == "mod-morph"]
    data = {"generated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "keylayout": table.get("_source", "?"), "layout": parse_layout(os.path.join(SHIELD, "totem-layouts.dtsi")),
            "layers": out_layers, "combos": combos, "macros": macros, "morphs": morphs}
    data["notes"] = checks(data)
    return data

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", default=os.path.join(HERE, "optimot_map.json"))
    ap.add_argument("--keylayout", help="relit un .keylayout et régénère optimot_map.json")
    ap.add_argument("--out", default=os.path.join(HERE, "totem-viz.html"))
    ap.add_argument("--fragment", action="store_true", help="sans <html>/<body> (publication)")
    ap.add_argument("--json", help="écrit aussi les données brutes")
    args = ap.parse_args()
    if args.keylayout:
        sys.path.insert(0, HERE)
        import extract_keylayout
        d = extract_keylayout.parse(args.keylayout); d["_source"] = os.path.basename(args.keylayout)
        json.dump(d, open(args.map, "w", encoding="utf-8"), ensure_ascii=False)
    data = build(args)
    if args.json:
        json.dump(data, open(args.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tpl = open(os.path.join(HERE, "totem_viz_template.html"), encoding="utf-8").read()
    page = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    if not args.fragment:
        page = "<!doctype html>\n<html lang=\"fr\">\n<head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n" + page.replace("<!--BODY-->", "</head>\n<body>", 1) + "\n</body>\n</html>\n"
    else:
        page = page.replace("<!--BODY-->", "", 1)
    open(args.out, "w", encoding="utf-8").write(page)
    print("écrit :", args.out, "-", len(data["combos"]), "combos,", len(data["layers"]), "calques,", len(data["notes"]), "remarques")

if __name__ == "__main__":
    main()
