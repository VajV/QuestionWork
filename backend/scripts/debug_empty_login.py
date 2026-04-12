from playwright.sync_api import sync_playwright
import time

p = sync_playwright().start()
b = p.chromium.launch(
    headless=True,
    args=["--window-size=1280,720", "--disable-dev-shm-usage", "--ipc=host", "--disable-web-security"]
)
ctx = b.new_context()
ctx.set_default_timeout(15000)
pg = ctx.new_page()

pg.goto("http://127.0.0.1:3000/auth/login")
pg.wait_for_load_state("networkidle")

# Try to fill username but leave password empty
pg.fill("#username", "test_user")

pg.click("button[type=submit]")
time.sleep(2)
print("After fill user only - URL:", pg.url)
body = pg.inner_text("body")
print("Has error?", any(c in body for c in ["💀", "Заполните", "поля", "Секретный"]))

# Fill just password
pg2 = ctx.new_page()
pg2.goto("http://127.0.0.1:3000/auth/login")
pg2.wait_for_load_state("networkidle")
pg2.fill("#password", "TestPass1!")
pg2.click("button[type=submit]")
time.sleep(2)
print("After fill pass only - URL:", pg2.url)
body2 = pg2.inner_text("body")
print("Body2:", body2[:300].replace("\n", " | "))
print("Has error?", any(c in body2 for c in ["💀", "Заполните", "поля"]))

b.close()
p.stop()

