"""حسابات تباين WCAG — عشان نقيس مش نخمّن.

الزجاج شفاف، يعني لون النص الفعلي بيتحسب بعد ما طبقة الزجاج تتركب على
الأرضية اللي تحتها. الملف ده بيعمل التركيب ده بالظبط (alpha compositing)
وبعدين يحسب نسبة التباين، عشان نقدر نثبّت الأرقام في اختبار بدل ما نبص
بالعين ونقول "شكله واضح".

الحدود اللي بنمشي عليها (WCAG 2.1 AA):
  - نص عادي      >= 4.5:1
  - نص كبير/عنوان >= 3.0:1
"""

from __future__ import annotations

BODY_FLOOR = 4.5
LARGE_FLOOR = 3.0


def parse(color):
    """بياخد ‎#RRGGBB‎ / ‎#RGB‎ / ‎rgba(r,g,b,a)‎ / ‎rgb(r,g,b)‎ ويرجّع
    ‎(r, g, b, a)‎ بقيم 0-255 للألوان و0-1 للشفافية."""
    if isinstance(color, (tuple, list)):
        if len(color) == 3:
            return (float(color[0]), float(color[1]), float(color[2]), 1.0)
        return tuple(float(c) for c in color)  # type: ignore[return-value]
    c = str(color).strip()
    if c.startswith("#"):
        h = c[1:]
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        if len(h) == 8:
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16) / 255)
        if len(h) != 6:
            raise ValueError(f"hex color مش مفهوم: {color}")
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    if c.startswith("rgb"):
        inner = c[c.index("(") + 1: c.rindex(")")]
        parts = [p.strip() for p in inner.replace("/", ",").split(",") if p.strip()]
        vals = [float(p) for p in parts]
        if len(vals) == 3:
            vals.append(1.0)
        return (vals[0], vals[1], vals[2], vals[3])
    raise ValueError(f"لون مش مدعوم: {color}")


def over(fg, bg):
    """بتركّب لون شفاف ‎fg‎ فوق لون ‎bg‎ (لازم يكون معتم) وترجّع hex معتم.

    ده بالظبط اللي المتصفح بيعمله لما طبقة زجاج بشفافية تقعد فوق الأرضية.
    ملحوظة: ‎backdrop-filter‎ (blur/saturate) بيغيّر شكل الأرضية بس مش
    بيغيّر متوسط لمعانها بشكل ملحوظ، فالحساب ده تقريب أمين للحالة العملية.
    """
    fr, fg_, fb, fa = parse(fg)
    br, bg_, bb, ba = parse(bg)
    if ba < 1.0:
        raise ValueError("الأرضية لازم تكون معتمة عشان التركيب يبقى معناه واضح")
    r = fr * fa + br * (1 - fa)
    g = fg_ * fa + bg_ * (1 - fa)
    b = fb * fa + bb * (1 - fa)
    return "#%02X%02X%02X" % (round(r), round(g), round(b))


def stack(layers, ground):
    """بتركّب كذا طبقة بالترتيب من تحت لفوق فوق أرضية معتمة."""
    out = ground
    for layer in layers:
        out = over(layer, out)
    return out


def _channel(v):
    v = v / 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def luminance(color):
    r, g, b, a = parse(color)
    if a < 1.0:
        raise ValueError("اللمعان بيتحسب للألوان المعتمة بس — ركّب الشفاف الأول بـ over()")
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def ratio(c1, c2):
    """نسبة التباين بين لونين معتمين (>= 1.0)."""
    l1, l2 = luminance(c1), luminance(c2)
    hi, lo = max(l1, l2), min(l1, l2)
    return (hi + 0.05) / (lo + 0.05)


def check(name, fg, bg, floor=BODY_FLOOR):
    """بترجّع صف جاهز لجدول التدقيق."""
    r = ratio(fg, bg)
    return {
        "pair": name,
        "fg": fg if isinstance(fg, str) else str(fg),
        "bg": bg if isinstance(bg, str) else str(bg),
        "ratio": round(r, 2),
        "floor": floor,
        "pass": r >= floor,
    }


def audit(rows):
    """‎rows‎ = قايمة ‎(name, fg, bg, floor)‎ → قايمة نتايج + عدد الفشل."""
    out = [check(n, f, b, fl) for (n, f, b, fl) in rows]
    return out, sum(0 if r["pass"] else 1 for r in out)


def fmt(rows):
    """جدول نصي بسيط للطباعة في الاختبارات."""
    w = max(len(r["pair"]) for r in rows) if rows else 4
    lines = [f"{'pair'.ljust(w)}  {'fg':>9}  {'bg':>9}  {'ratio':>6}  floor  ok"]
    for r in rows:
        lines.append(
            f"{r['pair'].ljust(w)}  {r['fg']:>9}  {r['bg']:>9}  "
            f"{r['ratio']:>6.2f}  {r['floor']:>5}  {'PASS' if r['pass'] else 'FAIL'}"
        )
    return "\n".join(lines)
