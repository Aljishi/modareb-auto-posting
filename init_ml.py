"""
init_ml.py — تشغيل يدوي مرة واحدة قبل الإطلاق
يدرّب نموذج ML على 60 يوم تاريخي لجميع أسهم تاسي

الاستخدام:
  python scripts/init_ml.py
أو عبر GitHub Actions: Run workflow على weekly-report
"""

import sys
import os

print("="*60)
print("تهيئة نموذج ML — تشغيل أولي")
print("="*60)

if not os.environ.get("API_KEY"):
    print("\n❌ API_KEY غير موجود في المتغيرات البيئية")
    print("   أضف API_KEY وأعد التشغيل")
    sys.exit(1)

print("\nجاري تدريب النموذج على 60 يوم تاريخي...")
print("قد يستغرق هذا 5-10 دقائق...\n")

try:
    from ml_trainer import main as train_main
    train_main()
    print("\n✅ نموذج ML جاهز — يمكنك الآن تشغيل النظام")
except Exception as e:
    print(f"\n❌ خطأ في التدريب: {e}")
    sys.exit(1)
