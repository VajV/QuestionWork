from playwright.sync_api import sync_playwright
import time

p = sync_playwright().start()
b = p.chromium.launch(headless=True, args=["--window-size=1280,720", "--disable-dev-shm-usage", "--ipc=host"])
ctx = b.new_context()
ctx.set_default_timeout(15000)
pg = ctx.new_page()

# Capture ALL network responses
def on_response(r):
    if "127.0.0.1:8001" in r.url:
        cors = r.headers.get("access-control-allow-origin", "MISSING")
        print(f"RESP [{r.status}] CORS={cors} {r.url[-70:]}")

def on_request(req):
    if "127.0.0.1:8001" in req.url:
        orig = req.headers.get("origin", "NO_ORIGIN")
        print(f"REQ  [{req.method}] Origin={orig} {req.url[-70:]}")

pg.on("response", on_response)
pg.on("request", on_request)
pg.on("console", lambda m: print("CONSOLE:", m.type[:4], m.text[:80]) if m.type in ("error", "warning") else None)

pg.goto("http://127.0.0.1:3001/auth/login")
pg.wait_for_load_state("networkidle")
print("Loaded:", pg.url)

pg.fill("#username", "test_hero")
pg.fill("#password", "QuestWork1!")
pg.click("button[type=submit]")
time.sleep(5)
print("Final URL:", pg.url)

b.close()
p.stop()

