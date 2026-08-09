import React from "react";
import { Link } from "react-router-dom";

export default function Terms() {
  return (
    <div className="prose prose-invert max-w-3xl mx-auto py-8 space-y-6" data-testid="terms-page" dir="rtl">
      <h1 className="font-display text-4xl font-black gradient-text">شروط الاستخدام</h1>
      <p className="text-muted-foreground">آخر تحديث: فبراير 2026</p>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">١. قبول الشروط</h2>
        <p>
          باستخدامك MangaVerse فإنك توافق على هذه الشروط. إذا لم توافق، يُرجى عدم استخدام التطبيق.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">٢. السلوك المقبول</h2>
        <ul className="list-disc ps-6 space-y-1">
          <li>عدم نشر محتوى مسيء أو تمييزي أو مخالف للقانون.</li>
          <li>عدم انتحال شخصية أو مضايقة المستخدمين الآخرين.</li>
          <li>عدم استخدام التطبيق لإرسال رسائل مزعجة (سبام).</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">٣. الملكية الفكرية</h2>
        <p>
          MangaVerse هو منصة فهرسة فقط. جميع حقوق المانجا والمانهوا والترجمات تعود لمالكيها
          الأصليين. للإبلاغ عن خرق حقوق راسلنا فورًا.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">٤. حدود المسؤولية</h2>
        <p>
          يُقدَّم التطبيق &quot;كما هو&quot; دون أي ضمانات. لا نتحمل مسؤولية أي ضرر ناتج عن استخدام
          المحتوى أو انقطاع الخدمة.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">٥. إيقاف الحسابات</h2>
        <p>
          يحق لنا إيقاف أي حساب يخالف هذه الشروط دون إشعار مسبق.
        </p>
      </section>

      <p className="text-sm text-muted-foreground pt-6">
        — اقرأ أيضًا <Link to="/privacy" className="text-primary hover:underline">سياسة الخصوصية</Link>.
      </p>
    </div>
  );
}
