# مرتب‌سازی و افزایش سرعت کامپیوتر (ویندوز)

این اسکریپت‌ها **هیچ فایلی را حذف نمی‌کنند**.

## اجرا
1. فایل‌های `PC-Tidy.ps1` و `Undo-Tidy.ps1` را دانلود کنید.
2. PowerShell را **Run as Administrator** باز کنید و به پوشهٔ فایل‌ها بروید.
3. اول پیش‌نمایش (هیچ تغییری نمی‌دهد):
   ```powershell
   Set-ExecutionPolicy -Scope Process Bypass
   .\PC-Tidy.ps1
   ```
4. اگر نتیجه را پسندیدید، اعمال واقعی:
   ```powershell
   .\PC-Tidy.ps1 -Apply
   ```

## کارهایی که انجام می‌دهد
| بخش | کار |
|---|---|
| مرتب‌سازی | فایل‌های روی Desktop، Downloads و Documents را در پوشه‌های Images / Videos / Music / Documents / Archives / Installers / Code / Other جابه‌جا می‌کند. فایل هم‌نام بازنویسی نمی‌شود. |
| فایل‌های حجیم | لیست فایل‌های بزرگ‌تر از ۵۰۰ مگابایت ← `large-files.csv` |
| فایل‌های اضافه | اندازهٔ Temp و کش مرورگرها و سطل زباله، نصب‌کننده‌ها و فایل‌های فشردهٔ قدیمی در Downloads، و فایل‌های تکراری ← فایل‌های CSV جداگانه |
| سرعت | فضای خالی دیسک‌ها، رم، نوع دیسک (HDD/SSD)، ۱۰ برنامه‌ای که بیشترین رم را مصرف می‌کنند، برنامه‌های Startup و Power Plan |
| با `-Apply` | Power Plan را روی High performance می‌گذارد و درایوها را Optimize می‌کند (TRIM/Defrag، بدون حذف داده) |

همهٔ گزارش‌ها روی Desktop در پوشهٔ `PC-Tidy-Report-<تاریخ>` ذخیره می‌شوند.

## برگرداندن جابه‌جایی‌ها
```powershell
.\Undo-Tidy.ps1 -Log "$HOME\Desktop\PC-Tidy-Report-XXXX\moves-log.csv"
```

## کارهای دستی پیشنهادی برای سرعت بیشتر
- **Task Manager ← Startup:** برنامه‌های غیرضروری را Disable کنید.
- **Storage Sense:** در Settings ← System ← Storage آن را روشن کنید تا Temp خودکار پاک شود.
- **Disk Cleanup:** بعد از بررسی `temp-cache-sizes.csv`، این ابزار را اجرا کنید (خودتان تصمیم می‌گیرید).
- **جلوه‌های بصری:** Win+R ← `sysdm.cpl` ← Advanced ← Performance ← Adjust for best performance
- اگر دیسک از نوع **HDD** است و بیشتر از ۹۰٪ آن پر شده، ارتقا به **SSD** بیشترین تأثیر را در سرعت دارد.
- اگر رم کمتر از ۸ گیگابایت است و مرتب پر می‌شود، رم را اضافه کنید.
