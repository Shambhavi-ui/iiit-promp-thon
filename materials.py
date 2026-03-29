materials_db = [
    {"name": "AAC", "cost": 2, "strength": 5},
    {"name": "Brick", "cost": 5, "strength": 7},
    {"name": "RCC", "cost": 9, "strength": 10}
]

def score(m, wall_type):
    if wall_type == "load":
        wc, ws = 0.3, 0.7
    else:
        wc, ws = 0.6, 0.4

    return ws*m["strength"] - wc*m["cost"]

def classify_wall(w):
    x1, y1 = w[0]
    x2, y2 = w[1]

    length = ((x2-x1)**2 + (y2-y1)**2)**0.5
    return "load" if length > 100 else "partition"

def recommend_materials(walls):
    results = []

    for w in walls:
        wtype = classify_wall(w)

        ranked = sorted(materials_db,
                        key=lambda m: score(m, wtype),
                        reverse=True)

        recommendations = [
            (m["name"], score(m, wtype))
            for m in ranked
        ]

        results.append({
            "wall": w,
            "type": wtype,
            "best": ranked[0]["name"],
            "recommendations": recommendations
        })

    return results