"""🤖 «ارسمها لي» — البرومبت والرد بتوع رسمة المكان من فوق (موديول نقي: json بس).

الـ AI بياخد وصف المكان وحالاته ونص المشاهد اللي بتحصل فيه، ويرجّع رسمة
بسيطة بنفس شكل blocking.clean_plan. دي **اقتراح** بيتعلّم عليه في الشاشة
(source=ai) واليوزر بيعدّله براحته — ومطلوب منه صراحةً مايحطش حاجة مش
مذكورة أو مفهومة من النص (قاعدة المالك: مانخترعش بيانات).
"""
import json

KINDS = ["door", "window", "wall", "table", "chair", "sofa", "bed", "desk", "counter",
         "cabinet", "plant", "car", "block"]

RESPONSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "w": {"type": "number"}, "h": {"type": "number"},
        "items": {"type": "array", "items": {
            "type": "object",
            "properties": {"k": {"type": "string", "enum": KINDS}, "x": {"type": "number"},
                           "y": {"type": "number"}, "w": {"type": "number"}, "h": {"type": "number"},
                           "r": {"type": "number"}, "label": {"type": "string"}},
            "required": ["k", "x", "y", "w", "h", "r", "label"]}},
    },
    "required": ["w", "h", "items"],
}

MAX_SCENES = 8
MAX_SCENE_CHARS = 900


def build_prompt(context):
    """context = {location, base_description, variants: [{name, description}], scenes: [text]}."""
    scenes = [s[:MAX_SCENE_CHARS] for s in (context.get("scenes") or [])[:MAX_SCENES]]
    parts = [
        "You draft a SIMPLE top-down floor plan (a director's blocking sketch) of one filming location.",
        "Units are roughly centimetres. Origin is the top-left corner of the space; x grows right, y grows down.",
        "Return JSON only: {w, h, items:[{k, x, y, w, h, r, label}]} where (x, y) is the CENTRE of each item,",
        "w/h its size, r its rotation in degrees, k one of: " + ", ".join(KINDS) + ".",
        "Rules:",
        "- Include only furniture, doors, windows and features that the texts below state or clearly imply.",
        "  Do not invent decor. If the texts say little, return the room with its obvious openings only.",
        "- Doors and windows sit on the outer walls (thin items along the edge). Use 'wall' for inner walls.",
        "- Keep it sparse: at most 25 items. Room size between 300 and 1500 each side; exterior spaces may be larger (max 2000).",
        "- Labels are short Arabic names as used in the script (e.g. «كنبة», «ترابيزة السفرة»), empty if the kind says it all.",
        "",
        "LOCATION: " + (context.get("location") or ""),
        "DESCRIPTION: " + (context.get("base_description") or "(none)"),
    ]
    for v in context.get("variants") or []:
        parts.append(f"STATE «{v.get('name') or ''}»: {v.get('description') or '(no description)'}")
    for i, s in enumerate(scenes, 1):
        parts.append(f"SCENE TEXT {i}: {s}")
    return "\n".join(parts)


def parse_response(body):
    """نص الرد → dict (التنضيف النهائي في blocking.clean_plan وقت الحفظ)."""
    data = json.loads(body) if isinstance(body, str) else body
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise ValueError("response is not a plan")
    return {"w": data.get("w"), "h": data.get("h"), "items": data["items"], "strokes": []}
