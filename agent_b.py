import asyncio, json, hashlib, re, time, sys
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PWTimeout
from typing import List

# ---- heuristics / selectors ----
BUTTON_RX = re.compile(r"(create|new|add|save|submit)", re.I)
MODAL_SEL = '[role="dialog"], [aria-modal="true"], .modal'
TOAST_SEL = '[role="status"], [role="alert"], [data-qa*="toast"]'
TEXTBOX_RX = re.compile(r"(name|title)", re.I)

def nowstamp():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def sha1(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()

async def dom_signature(page):
    # small accessibility-based fingerprint to detect non-URL state changes
    return await page.evaluate("""
    () => {
      const q = sel => Array.from(document.querySelectorAll(sel));
      const parts = [];
      const add = (role, el) => {
        let name = el.getAttribute('aria-label') || el.textContent || el.getAttribute('placeholder') || '';
        name = (name || '').trim().replace(/\s+/g,' ').slice(0,80);
        parts.push(role+':'+name);
      };
      q('button, [role=button]').forEach(el=>add('button', el));
      q('input, textarea, [role=textbox]').forEach(el=>add('textbox', el));
      q('[role=dialog]').forEach(el=>add('dialog', el));
      q('h1,h2,h3,[role=heading]').forEach(el=>add('heading', el));
      return parts.slice(0,200).join('|');
    }
    """)

async def safe_is_visible(locator):
    try:
        return await locator.is_visible()
    except Exception:
        return False

async def capture_state(page, out_dir: Path, label: str, focus=None):
    out_dir.mkdir(parents=True, exist_ok=True)
    full_path = out_dir / f"{label}.png"
    await page.screenshot(path=str(full_path), full_page=True)

    vis_hash = sha1(full_path.read_bytes())
    signature = await dom_signature(page)

    # optional focused crop (e.g., modal or toast)
    if focus:
        try:
            box = await focus.bounding_box()
            if box:
                await page.screenshot(path=str(out_dir / f"{label}_focus.png"), clip=box)
        except Exception:
            pass

    meta = {
        "label": label,
        "url": page.url,
        "time": datetime.now().isoformat(),
        "dom_signature": sha1(signature.encode()),
        "visual_hash": vis_hash
    }
    (out_dir / f"{label}.json").write_text(json.dumps(meta, indent=2))

async def find_first_button(page, rx=BUTTON_RX):
    # prefer ARIA role buttons
    try:
        buttons = page.get_by_role("button")
        count = await buttons.count()
        for i in range(min(count, 80)):
            b = buttons.nth(i)
            label = await b.get_attribute("aria-label")
            text = (label or (await b.inner_text() or "").strip())
            if text and rx.search(text):
                return b
    except Exception:
        pass
    # fallback: any element with visible text matching
    try:
        cand = page.get_by_text(rx)
        if await cand.count():
            return cand.first
    except Exception:
        pass
    return None

async def find_textbox_by_label(page, rx=TEXTBOX_RX):
    try:
        tbs = page.get_by_role("textbox")
        count = await tbs.count()
        for i in range(min(count, 60)):
            tb = tbs.nth(i)
            name = await tb.get_attribute("aria-label")
            ph = await tb.get_attribute("placeholder")
            lab = (name or ph or "").strip()
            if rx.search(lab):
                return tb
    except Exception:
        pass
    # fallback
    try:
        inputs = page.locator("input, textarea")
        count = await inputs.count()
        for i in range(min(count, 60)):
            el = inputs.nth(i)
            ph = await el.get_attribute("placeholder") or ""
            if rx.search(ph):
                return el
    except Exception:
        pass
    return None


async def wait_for_manual_login(page):
    """
    Keep the browser open so you can complete the Linear login manually.
    When you reach your workspace (not the login page), press ENTER here.
    """
    print("[AgentB] A browser window opened.")
    print("[AgentB] Please complete the Linear login there, then come back and press ENTER here...")
    # block the event loop on a background thread so the browser stays open
    await asyncio.get_event_loop().run_in_executor(None, input)
    return True

async def run_linear_create_project(start_url: str, project_name: str):
    out_dir = Path("tasks") / "linear" / f"create-issue_{nowstamp()}"

    async with async_playwright() as pw:
        # persistent context keeps your Linear login session across runs
        user_data = Path(".user_data") / "linear"
        user_data.mkdir(parents=True, exist_ok=True)

        ctx = await pw.chromium.launch_persistent_context(
            user_data_dir=str(user_data),
            headless=False  # keep visible for the first run
        )
        page = await ctx.new_page()
        await page.goto(start_url, wait_until="domcontentloaded")
        await capture_state(page, out_dir, "01_loaded")

        # If we're at login/auth, wait for you to finish logging in once.
        logged_in = await wait_for_manual_login(page)
        if not logged_in:
            print("[AgentB] Login did not complete in time. You can rerun the script.")
            await ctx.close()
            return

        # try to find an entry-point like "Create/New/Add"
        create_btn = await find_first_button(page)
        if create_btn:
            await create_btn.scroll_into_view_if_needed()
            await create_btn.click()
            await page.wait_for_timeout(700)

            modal = page.locator(MODAL_SEL).first
            if await safe_is_visible(modal):
                await capture_state(page, out_dir, "02_modal", focus=modal)

                tb = await find_textbox_by_label(page)
                if tb:
                    await tb.fill(project_name)
                    await capture_state(page, out_dir, "03_filled", focus=tb)

                submit = await find_first_button(page, re.compile(r"(create|add|save|submit)", re.I))
                if submit:
                    await submit.click()
                    await page.wait_for_timeout(1500)

                    toast = page.locator(TOAST_SEL).first
                    if await safe_is_visible(toast):
                        await capture_state(page, out_dir, "04_success_toast", focus=toast)
                    else:
                        await capture_state(page, out_dir, "04_post_submit")
            else:
                await capture_state(page, out_dir, "02_post_click")
        else:
            print("[AgentB] Could not find a Create/New/Add button on this page.")

        await ctx.close()

        write_task_readme(
            out_dir,
            "Create an Issue in Linear",
            "Capture of modal-based invite workflow.",
            ["01_loaded", "02_modal", "03_filled", "04_success_toast"]
        )
        


def write_task_readme(out_dir: Path, title: str, description: str, states: List[str]):
    readme = out_dir / "README.md"
    content = [f"# Task: {title}\n",
               f"**Goal:** {description}\n\n",
               "**States captured:**\n"]
    for s in states:
        content.append(f"- `{s}.png`\n")
    content.append("\n**Notes:** Automatically captured using heuristic agent.\n")
    readme.write_text("".join(content))





if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="https://linear.app/", help="Linear start URL")
    ap.add_argument("--name", default=f"AgentB Demo {int(time.time())}", help="Project name to create")
    args = ap.parse_args()
    asyncio.run(run_linear_create_project(args.url, args.name))
