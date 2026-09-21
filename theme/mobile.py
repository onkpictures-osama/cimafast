"""طبقة تكيّف الموبايل — CSS بس، جوه ‎@media‎ واحدة.

مفيش فلاج ومفيش session_state: المتصفح نفسه هو اللي بيقرر يطبّق الستايل ده
لما عرض الشاشة يبقى ضيق، فبيشتغل على أي جهاز موبايل من غير أي كود بايثون
إضافي ومن غير ما يلمس الباك إند خالص. التفاصيل والخطط في
‎MOBILE-REDESIGN-PLAN.md‎.

المرحلة صفر بس هنا دلوقتي: زرارات وحقول الإدخال بتاخد أقل ارتفاع 44px (نفس
الرقم المستخدم فعلاً لزرار الإعدادات في ‎classic.py‎). سطر المراحل القديم
(‎.cf-stepper‎) اتشال خالص من الشاشة في جولة تحسينات سابقة (شوف
‎test_the_five_stage_cards_are_gone‎) واتبدل بـ ‎.cf-progress‎ اللي شكله
كويس على الموبايل من غير أي تعديل، فمفيش داعي لستايل زيادة ليه.

نقطة الكسر (‎BREAKPOINT‎) متوافقة عمدًا مع ‎isMobile‎ بتاع Streamlit نفسها
(‎breakpoints.md = 768px‎ في ‎utils.BVKswTgl.js‎، الشرط ‎width < md‎) — مش
رقم اخترناه اعتباطي. لو الاتنين مش متطابقين، فيه عرض شاشات (موبايل كبير
بالعرض، أو تابلت صغير) بيدخل وضع الموبايل بتاع Streamlit نفسه (الشريط
الجانبي بيتحول overlay) من غير ما ستايلنا يتفعّل.
"""

from __future__ import annotations

BREAKPOINT = 767

MOBILE_CSS = f"""
@media (max-width: {BREAKPOINT}px) {{
    .stButton button,
    .stDownloadButton button,
    .stFormSubmitButton button,
    div[data-testid="stSelectbox"] > div,
    div[data-testid="stTextInput"] input,
    div[data-testid="stNumberInput"] input {{
        min-height: 44px !important;
    }}
}}
"""


def mobile_css():
    return MOBILE_CSS
