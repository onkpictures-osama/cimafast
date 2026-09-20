"""
Location Matching Engine - كشف الأماكن المتشابهة والحالات الدرامية
يربط الأماكن المتطابقة حتى لو اختلف الديكور بسبب الزمن أو الأحداث الدرامية
"""

import re
from difflib import SequenceMatcher

def extract_base_location(location_name):
    """
    استخراج اسم المكان الأساسي من الوصف
    مثال: "شقة أحمد المحترقة" -> "شقة أحمد"
    """
    # إزالة الكلمات الدرامية/الحالات
    dramatic_words = [
        'المحترقة', 'المدمرة', 'المهدومة', 'الجديدة', 'القديمة',
        'المليئة بالدماء', 'المظلمة', 'المضاءة', 'الفارغة', 'المكتظة',
        'المهجورة', 'المأهولة', 'الخربة', 'النظيفة', 'الوسخة',
        'burnt', 'destroyed', 'damaged', 'new', 'old', 'dark', 'bright'
    ]
    
    base = location_name
    for word in dramatic_words:
        base = re.sub(f'\\s*{word}\\s*', ' ', base, flags=re.IGNORECASE)
    
    return base.strip()

def similarity_score(name1, name2):
    """حساب التشابه بين اسمين (0-1)"""
    return SequenceMatcher(None, name1.lower(), name2.lower()).ratio()

def detect_state_change(location_text):
    """
    كشف التغيرات الدرامية/الزمنية في المكان
    يرجع: (base_location, state_description, is_variant)
    """
    state_patterns = {
        'fire': r'(محترق|حريق|النار|burnt|fire)',
        'time_passed': r'(بعد \d+ سنة|سنوات|بعد وقت|years later)',
        'destruction': r'(مدمر|مهدوم|destroyed|ruined)',
        'abandonment': r'(مهجور|مخلي|abandoned)',
        'renovation': r'(مجدد|محدث|renovated|updated)',
    }
    
    detected_states = []
    for state_type, pattern in state_patterns.items():
        if re.search(pattern, location_text, re.IGNORECASE):
            detected_states.append(state_type)
    
    return detected_states

def find_matching_locations(new_location, existing_locations, threshold=0.75):
    """
    البحث عن أماكن موجودة متطابقة مع المكان الجديد
    يرجع: [(existing_location, similarity_score, state_changes)]
    """
    new_base = extract_base_location(new_location['name'])
    matches = []
    
    for existing in existing_locations:
        existing_base = extract_base_location(existing['name'])
        score = similarity_score(new_base, existing_base)
        
        if score >= threshold:
            state_changes = detect_state_change(new_location['name'])
            matches.append({
                'existing_location': existing,
                'similarity': score,
                'state_changes': state_changes,
                'should_create_variant': len(state_changes) > 0
            })
    
    return sorted(matches, key=lambda x: x['similarity'], reverse=True)

def suggest_variant_name(base_location_name, state_changes):
    """
    اقتراح اسم للـ variant بناءً على الحالة الدرامية
    """
    if not state_changes:
        return None
    
    state_descriptions = {
        'fire': 'بعد الحريق',
        'time_passed': 'بعد مرور الزمن',
        'destruction': 'بعد التدمير',
        'abandonment': 'مهجورة',
        'renovation': 'بعد التجديد',
    }
    
    descriptions = [state_descriptions.get(s, s) for s in state_changes]
    return f"{base_location_name} - {' و '.join(descriptions)}"

