"""ورودی وب‌اپ روی PythonAnywhere.

در فایل WSGI سایت فقط این سه خط لازم است:
    import sys
    sys.path.insert(0, "/home/USERNAME/my-pro")
    from pa_wsgi import application

اگر راه‌اندازی خطا بدهد، متن خطا به‌جای صفحهٔ «Unhandled Exception» در مرورگر
نمایش داده می‌شود تا راحت بشود آن را دید و فرستاد.
"""

import os
import traceback

# PythonAnywhere رایگان فقط از طریق پراکسی خودش به اینترنت (از جمله تلگرام) وصل می‌شود
if os.environ.get("PYTHONANYWHERE_DOMAIN") and not os.environ.get("HTTPS_PROXY"):
    os.environ.setdefault("HTTPS_PROXY", os.environ.get("https_proxy", "http://proxy.server:3128"))

try:
    from bot.web import app as application
except Exception:
    _error = traceback.format_exc()
    try:
        from bot.main import load_token

        _error = _error.replace(load_token(), "<TOKEN>")
    except Exception:
        pass

    def application(environ, start_response):
        start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8")])
        return [("⚠️ خطا در راه‌اندازی بات — از این صفحه عکس بگیرید و بفرستید:\n\n" + _error).encode()]
