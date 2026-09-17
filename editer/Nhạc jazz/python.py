# CELL 2B — LOCAL ONLY (KHÔNG CHẠY CELL NÀY TRONG COLAB)
#
# Lưu đoạn code này thành create_youtube_state.py trên MÁY CÁ NHÂN.
# Cài: pip install playwright
# Sau đó: playwright install chromium
#
# Chạy: python create_youtube_state.py
#
# Một cửa sổ Chromium sẽ mở. Đăng nhập YouTube thủ công.
# Khi đã vào được YouTube, quay lại terminal và nhấn Enter.

from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(
        viewport={"width": 1440, "height": 1000},
        locale="en-US",
    )
    page = context.new_page()
    page.goto("https://www.youtube.com/", wait_until="domcontentloaded")

    print("Đăng nhập YouTube trong cửa sổ Chromium.")
    input("Khi đã đăng nhập xong, nhấn Enter tại terminal... ")

    # Kiểm tra nhanh
    page.goto("https://www.youtube.com/audiolibrary/music", wait_until="domcontentloaded")
    page.wait_for_timeout(5000)

    if "accounts.google.com" in page.url:
        raise RuntimeError(
            "YouTube vẫn yêu cầu đăng nhập. Chưa lưu state."
        )

    context.storage_state(path="youtube_auth_state.json")
    print("Đã tạo: youtube_auth_state.json")

    browser.close()
