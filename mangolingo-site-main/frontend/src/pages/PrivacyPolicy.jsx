import React from "react";
import { Link } from "react-router-dom";

export default function PrivacyPolicy() {
  return (
    <div className="prose prose-invert max-w-3xl mx-auto py-8 space-y-6" data-testid="privacy-page" dir="rtl">
      <h1 className="font-display text-4xl font-black gradient-text">سياسة الخصوصية</h1>
      <p className="text-muted-foreground">آخر تحديث: فبراير 2026</p>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">١. المعلومات التي نجمعها</h2>
        <p>
          عند إنشاء حساب على MangaVerse، نقوم بتخزين بريدك الإلكتروني واسم المستخدم وكلمة المرور
          المُشفّرة. لا نطلب أي معلومات شخصية أخرى. عند التصفّح كزائر لا نطلب أي بيانات.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">٢. كيف نستخدم البيانات</h2>
        <ul className="list-disc ps-6 space-y-1">
          <li>تسجيل الدخول وحفظ تقدمك في القراءة.</li>
          <li>عرض ملفك الشخصي للأصدقاء وغرف النقاش.</li>
          <li>إرسال إشعارات داخل التطبيق عند تلقي رسالة أو طلب صداقة.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">٣. مصادر المحتوى</h2>
        <p>
          يستضيف MangaVerse فهرسًا للمانجا والمانهوا. الصور والفصول تأتي من مصادر خارجية عامة
          (MangaDex وغيرها) ولا يُخزَّن أي محتوى محمي بحقوق الطبع على خوادمنا.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">٤. مشاركة البيانات</h2>
        <p>
          لا نبيع بياناتك ولا نشاركها مع أطراف ثالثة لأغراض تسويقية. قد نعرض إعلانات من شبكات
          إعلانية تستخدم ملفات تعريف ارتباط للقياس فقط.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">٥. حقوقك</h2>
        <p>
          يمكنك في أي وقت طلب حذف حسابك وجميع بياناتك من خلال صفحة الإعدادات أو بمراسلتنا
          على البريد: <span className="text-primary">support@mangaverse.app</span>.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">٦. الأطفال</h2>
        <p>
          MangaVerse مخصّص للمستخدمين بعمر 13 عامًا فأكثر. لا نجمع عن قصد بيانات من أي طفل دون
          ذلك العمر.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-bold">٧. تحديثات هذه السياسة</h2>
        <p>
          قد نُحدّث هذه السياسة من وقت لآخر. سيتم إعلامك بالتغييرات الجوهرية داخل التطبيق.
        </p>
      </section>

      <p className="text-sm text-muted-foreground pt-6">
        — اقرأ أيضًا <Link to="/terms" className="text-primary hover:underline">شروط الاستخدام</Link>.
      </p>
    </div>
  );
}
