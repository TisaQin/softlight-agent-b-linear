import asyncio, re, time
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright
from agent_b import capture_state, find_first_button, safe_is_visible, dom_signature
from typing import List


async def wait_for_user(page, message="[AgentB] Browser open. Explore the app if needed, then press ENTER to continue..."):
    print(message)
    await asyncio.get_event_loop().run_in_executor(None, input)



def nowstamp():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

# ---------------------------------------------------
#  TASK 1: Filter Issues (demonstrates dropdown / filter state)
# ---------------------------------------------------
async def run_linear_filter_issues(start_url: str):
    out_dir = Path("tasks") / "linear" / f"filter-issues_{nowstamp()}"

    async with async_playwright() as pw:
        user_data = Path(".user_data") / "linear"
        ctx = await pw.chromium.launch_persistent_context(str(user_data), headless=False)
        page = await ctx.new_page()
        await page.goto(start_url, wait_until="domcontentloaded")

        await capture_state(page, out_dir, "01_loaded")

        await wait_for_user(page)

        # Try to find a "Filter" button (common in Linear issue list)
        filter_btn = await find_first_button(page, re.compile(r"^filter$", re.I))
        if filter_btn:
            await filter_btn.click()
            await page.wait_for_timeout(1000)
            await capture_state(page, out_dir, "02_filter_open")

            # Choose a status option (try clicking something that says 'In Progress' or 'Done')
            status_option = page.get_by_text(re.compile(r"in progress|done|todo", re.I))
            if await status_option.count():
                await status_option.first.click()
                await capture_state(page, out_dir, "03_filter_applied")

        await ctx.close()

        write_task_readme(
            out_dir,
            "Filter Issues in Linear",
            "Capture of modal-based invite workflow.",
            ["01_loaded", "02_filter_open", "03_filter_applied"]
        )


# ---------------------------------------------------
#  TASK 3: Invite Member (simple modal workflow)
# ---------------------------------------------------
async def run_linear_invite_member(start_url: str):
    out_dir = Path("tasks") / "linear" / f"invite-member_{nowstamp()}"

    async with async_playwright() as pw:
        user_data = Path(".user_data") / "linear"
        ctx = await pw.chromium.launch_persistent_context(str(user_data), headless=False)
        page = await ctx.new_page()
        await page.goto(start_url, wait_until="domcontentloaded")

        await capture_state(page, out_dir, "01_loaded")

        # Pause to ensure we're on the workspace home
        await asyncio.get_event_loop().run_in_executor(None, lambda: input(
            "[AgentB] Browser open. Navigate to the workspace home if needed, then press ENTER to continue..."
        ))

        # Find "Invite people" or "Invite members"
        invite_btn = page.get_by_role("button", name=re.compile(r"invite|add member", re.I))
        if not await invite_btn.count():
            invite_btn = page.get_by_text(re.compile(r"invite people|add member", re.I))

        if await invite_btn.count():
            btn = invite_btn.first
            await btn.scroll_into_view_if_needed()
            await btn.click()
            await page.wait_for_timeout(800)
            await capture_state(page, out_dir, "02_invite_modal")

            # Try to locate email textbox
            email_input = page.get_by_role("textbox")
            if await email_input.count():
                tb = email_input.first
                await tb.fill("test@example.com")
                await capture_state(page, out_dir, "03_email_filled", focus=tb)

            # Try to find submit button
            submit_btn = page.get_by_role("button", name=re.compile(r"send|invite|add", re.I))
            if await submit_btn.count():
                await submit_btn.first.click()
                await page.wait_for_timeout(1500)
                await capture_state(page, out_dir, "04_invite_sent", focus=submit_btn)
        else:
            print("[AgentB] Could not find an Invite button.")
        
        await ctx.close()

        write_task_readme(
            out_dir,
            "Invite a Member in Linear",
            "Capture of modal-based invite workflow.",
            ["01_loaded", "02_invite_modal", "03_email_filled", "04_invite_sent"]
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



# ---------------------------------------------------
#  CLI Runner
# ---------------------------------------------------
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=["filter-issues", "invite-member"])
    ap.add_argument("--url", default="https://linear.app/")
    args = ap.parse_args()

    if args.task == "filter-issues":
        asyncio.run(run_linear_filter_issues(args.url))
    elif args.task == "invite-member":
        asyncio.run(run_linear_invite_member(args.url))