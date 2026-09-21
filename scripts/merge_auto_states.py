#!/usr/bin/env python3
"""بيدمج «الحالات» القديمة اللي الاستيراد كان بيعملها من داخلي/خارجي × نهار/ليل.

قبل 9ef528f الاستيراد كان بيعمل حالة لكل تركيبة («INT - نهار»، «INT - ليل»...)
فالمكان الواحد بيطلع بكذا حالة مالهاش أي معنى درامي. السكريبت ده، لكل مكان،
بيعمل حالة واحدة «الشكل الأساسي»، بيحوّل المشاهد ليها، وبيمسح القديمة.

بيلمس بس الحالات اللي اسمها **بالظبط** "<int_ext> - <day_night>" بتاعتها هي —
حالة زي «شقة حسين - القاهرة - الصالون» فيها شرطة بس اسم حقيقي، فبتفضل.
مابيلمسش أي حالة ليها وصف أو صورة.

    python3 scripts/merge_auto_states.py --db /var/lib/cimafast/studio.db          # معاينة بس
    python3 scripts/merge_auto_states.py --db /var/lib/cimafast/studio.db --apply  # تنفيذ

مع --apply بياخد نسخة احتياطية الأول في snapshots/ جنب القاعدة، وبينفذ كله في
transaction واحدة: يا كله يا مفيش.
"""
import argparse
import os
import sqlite3
import sys
import time

DEFAULT = "الشكل الأساسي"


def auto_states(c):
    rows = c.execute(
        "SELECT id, location_id, variant_name, int_ext, day_night, "
        "COALESCE(description,''), COALESCE(reference_image_path,'') FROM location_variants"
    ).fetchall()
    return [r for r in rows
            if r[2] == f"{r[3] or 'غير محدد'} - {r[4] or 'غير محدد'}" and not r[5] and not r[6]]


def stats(c):
    return {
        "scenes": c.execute("SELECT COUNT(*) FROM scenes").fetchone()[0],
        "scenes_without_state": c.execute(
            "SELECT COUNT(*) FROM scenes WHERE location_variant_id IS NULL").fetchone()[0],
        "dangling": c.execute(
            "SELECT COUNT(*) FROM scenes s WHERE location_variant_id IS NOT NULL AND NOT EXISTS "
            "(SELECT 1 FROM location_variants v WHERE v.id = s.location_variant_id)").fetchone()[0],
        "states": c.execute("SELECT COUNT(*) FROM location_variants").fetchone()[0],
    }


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)

    c = sqlite3.connect(a.db, timeout=30)
    auto = auto_states(c)
    by_loc = {}
    for r in auto:
        by_loc.setdefault(r[1], []).append(r[0])
    ids = [r[0] for r in auto]
    n_scenes = c.execute(
        f"SELECT COUNT(*) FROM scenes WHERE location_variant_id IN ({','.join('?' * len(ids))})", ids
    ).fetchone()[0] if ids else 0
    before = stats(c)
    print(f"حالات قديمة هتتدمج: {len(auto)} في {len(by_loc)} مكان، مستخدمة في {n_scenes} مشهد")
    if not a.apply:
        print("معاينة بس — ضيف --apply للتنفيذ.")
        return 0
    if not auto:
        print("مفيش حاجة تتعمل.")
        return 0

    snap_dir = os.path.join(os.path.dirname(os.path.abspath(a.db)), "snapshots")
    os.makedirs(snap_dir, exist_ok=True)
    bak = os.path.join(snap_dir, f"studio-before-state-merge-{time.strftime('%Y%m%d-%H%M%S')}.db")
    b = sqlite3.connect(bak)
    c.backup(b)
    b.close()
    st = os.stat(a.db)
    try:
        os.chown(bak, st.st_uid, st.st_gid)
    except PermissionError:
        pass
    print(f"نسخة احتياطية: {bak}")

    moved = 0
    with c:
        for loc, old in by_loc.items():
            row = c.execute("SELECT id FROM location_variants WHERE location_id=? AND variant_name=?",
                            (loc, DEFAULT)).fetchone()
            new_id = row[0] if row else c.execute(
                "INSERT INTO location_variants (location_id, variant_name, description) VALUES (?,?,?)",
                (loc, DEFAULT, "")).lastrowid
            q = ",".join("?" * len(old))
            moved += c.execute(f"UPDATE scenes SET location_variant_id=? WHERE location_variant_id IN ({q})",
                               [new_id, *old]).rowcount
            c.execute(f"DELETE FROM location_variants WHERE id IN ({q})", old)

    after = stats(c)
    ok = (after["scenes"] == before["scenes"]
          and after["scenes_without_state"] == before["scenes_without_state"]
          and after["dangling"] == 0 and moved == n_scenes
          and c.execute("PRAGMA integrity_check").fetchone()[0] == "ok")
    print(f"مشاهد اتحوّلت: {moved} | الحالات: {before['states']} → {after['states']}")
    print("✅ سليم" if ok else f"❌ فيه حاجة غلط — رجّع النسخة الاحتياطية: {bak}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
