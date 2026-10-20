"""Reconstruit index.html à partir de src/style.css, src/body.html et src/app.js.
Lancer depuis ce dossier : python3 build.py"""
import pathlib

R = pathlib.Path(__file__).parent
S = R / "src"
css = (S / "style.css").read_text(encoding="utf8")
body = (S / "body.html").read_text(encoding="utf8")
js = (S / "app.js").read_text(encoding="utf8")

DESC = "Piaule Fiction : tes agents structurent tes biens, suivent les dossiers et préparent les actions. Démo, données synthétiques."
page = f"""<meta name="description" content="{DESC}">
<title>Piaule Fiction</title>
<link rel="preload" href="fonts/instrument-sans-latin.woff2" as="font" type="font/woff2" crossorigin>
<style>
{css}
</style>
""" + body + "\n<script>\n" + js + "\n</script>\n"
full = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
</head>
<body>
""" + page + "</body>\n</html>\n"
(R / "index.html").write_text(full, encoding="utf8")
print("index.html reconstruit :", len(full.encode()), "octets")

# ---------- Espace participant / confirmations (espace.html) ----------
E = S / "espace"
src = js
a = src.index("const CITIES"); b = src.index("const quart")
parse_js = src[a:b]
ejs = (E / "app.js").read_text(encoding="utf8").replace("/* @@PARSE@@ (repris de l'accueil au moment de la construction) */", parse_js)
epage = f"""<meta name="description" content="Workspace propriétaire Piaule Fiction et espace participant.">
<meta name="robots" content="noindex">
<title>Mon espace · Piaule Fiction</title>
<link rel="preload" href="fonts/instrument-sans-latin.woff2" as="font" type="font/woff2" crossorigin>
<style>
{(E / "style.css").read_text(encoding="utf8")}
</style>
""" + (E / "body.html").read_text(encoding="utf8") + "\n<script>\n" + ejs + "\n</script>\n"
efull = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
</head>
<body>
""" + epage + "</body>\n</html>\n"
(R / "espace.html").write_text(efull, encoding="utf8")
print("espace.html reconstruit :", len(efull.encode()), "octets")
