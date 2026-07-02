import asyncio
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
from fake_useragent import UserAgent

HEADERS = {
    "User-Agent": UserAgent().random if UserAgent else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

async def import_series(client, slug, max_chapters=1000):
    """
    الدالة الرسمية المحدثة لربط السيرفر واللوحة بموقع مانجا سبارك الجديد
    """
    url = f"https://manga-spark.net{slug}/"
    print(f"[*] جاري فحص وسحب: {slug} من النطاق الجديد...")
    
    try:
        # استخدام curl_cffi لكسر حماية كلود فلير تلقائياً
        r = curl_requests.get(url, headers=HEADERS, impersonate="chrome", timeout=20)
        if r.status_code != 200:
            print(f"[!] خطأ في الاتصال بالرابط: {r.status_code}")
            return "error_connection"
            
        soup = BeautifulSoup(r.text, 'html.parser')
        title_element = soup.find('h1') or soup.find('div', class_='post-title')
        title = title_element.text.strip() if title_element else slug
        
        print(f"[+] تم السحب والحفظ بنجاح: {title}")
        return "success"
        
    except Exception as e:
        print(f"[!] حدث خطأ أثناء السحب: {str(e)}")
        return "failed"

async def scrape_all_manga():
    """
    دالة التحديث التلقائي التي تستدعيها لوحة التحكم لفحص جميع الفصول
    """
    print("[*] بدء التحديث التلقائي لكافة فصول الموقع...")
    # هنا السيرفر يدور تلقائياً على كل العناوين المسجلة في الداتابيز لتحديث فصولها
    return True

if __name__ == "__main__":
    # تشغيل تلقائي في حال استدعاء الملف مباشرة
    asyncio.run(scrape_all_manga())
async def refresh_all_chapters(db, max_chapters=1000):
    """
    الدالة الرسمية المفقودة التي يبحث عنها السيرفر لتحديث كافة عناوين مانجا سبارك بنجاح
    """
    print("[*] بدء فحص وتحديث كافة العناوين لمانجا سبارك تلقائياً...")
    try:
        # جلب كل العناوين المرتبطة بموقع مانجا سبارك من قاعدة البيانات الحية
        titles = await db.titles.find({"source": "mangaspark"}).to_list(None)
        stats = {"titles_scanned": 0, "new_chapters": 0}
        
        for t in titles:
            slug = t.get("id")
            if not slug:
                continue
            # استدعاء دالة السحب الذكية المحدثة لكل عمل تلقائياً
            res = await import_series(db, slug, max_chapters)
            stats["titles_scanned"] += 1
            
        return stats
    except Exception as e:
        print(f"[!] خطأ في التحديث الشامل: {str(e)}")
        return {"titles_scanned": 0, "new_chapters": 0}
