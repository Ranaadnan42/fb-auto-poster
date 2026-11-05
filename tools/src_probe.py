import sys, json
sys.path.insert(0, ".")
import footage, world
for q in ["lisbon", "lisbon tram", "mosque", "pasteis de nata", "desert camel"]:
    a = footage.mixkit(q); b = world.mixkit_search(q)
    print(q, len(a), len(b), [c["text"][:40] for c in a[:4]], a[0]["url"] if a else "", a[0]["dur"] if a else "")
