"""مرة واحدة (المالك 2026-09-24): كل المستخدمين الموجودين ← باقة Studio، وكل
واحد مدير مساحة العمل الشخصية بتاعته.

"الـ users اللي أنشأتهم سابقًا، انقلهم جميعًا لباقة Studio عشان يقدروا يضيفوا
أعضاء لفريق العمل جوه كل مشروع." وفي النموذج الجديد اللي بينشئ المشروع هو
مديره، فكل واحد لازم يبقى مدير مساحته الشخصية (الحسابات القديمة كانت
"رئيس قسم" أو "منتج" جوه مساحة هو لوحده فيها).

    STUDIO_DB_PATH=/var/lib/cimafast-v1/studio.db venv/bin/python scripts/upgrade_existing_to_studio.py [--apply]

من غير --apply بيعرض اللي هيتغيّر بس. الإنتاج مايتشغلش عليه غير بموافقة المالك.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database  # noqa: E402
from database import fetch_all, run_query  # noqa: E402
import permissions  # noqa: E402

apply = "--apply" in sys.argv
database.init_db()
companies = fetch_all("SELECT id, name, subscription_tier FROM companies ORDER BY id")
solo_non_admin = fetch_all("""
    SELECT m.id, c.name AS company, u.username, m.role FROM memberships m
    JOIN companies c ON c.id = m.company_id JOIN users u ON u.id = m.user_id
    WHERE m.active = 1 AND m.role <> 'admin'
      AND (SELECT COUNT(*) FROM memberships x WHERE x.company_id = m.company_id AND x.active = 1) = 1""")
print(f"مساحات عمل هتبقى Studio: {sum(1 for c in companies if (c['subscription_tier'] or 'creator') != 'studio')}"
      f" من {len(companies)}")
for r in solo_non_admin:
    print(f"  {r['username']}: {r['role']} ← admin (لوحده في «{r['company']}»)")
if apply:
    with permissions.system():
        run_query("UPDATE companies SET subscription_tier='studio' WHERE COALESCE(subscription_tier, 'creator') = 'creator'")
        for r in solo_non_admin:
            run_query("UPDATE memberships SET role='admin' WHERE id=?", (r["id"],))
    print("✓ اتطبق")
else:
    print("(عرض بس — ضيف --apply للتطبيق)")
