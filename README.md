# Softlight Agent B – Heuristic UI State Capture System

This project implements **Agent B**, a generalizable automation agent that navigates live web applications
and programmatically captures **non-URL UI states** (modals, forms, alerts, etc.) in real time.

---

## Overview

Agent B uses **Playwright** to observe, act, and record:
- Detects key interaction affordances (`create`, `filter`, `invite`, etc.) using accessibility roles and text.
- Captures screenshots + metadata (`URL`, `DOM signature`, `visual hash`) for distinct UI state.
- Works without task-specific code — relies on semantic heuristics, not hardcoded selectors.

---

## ⚙️ Implementation

| File | Purpose |
|------|----------|
| `agent_b.py` | Core framework + “Create Issue” workflow |
| `linear_tasks.py` | Additional Linear workflows (“Filter Issues”, “Invite Member”) |
| `tasks/` | Captured datasets (auto-generated) |
| `docs/` | Supporting write-ups for submission |

---

## 🧩 Workflows Demonstrated

| Task | Description | Example States |
|------|--------------|----------------|
| Create Issue | Modal-based creation flow | `01_loaded`, `02_modal`, `03_filled`, `04_success_toast` |
| Filter Issues | Dropdown filter interaction | `01_loaded`, `02_filter_open`, `03_filter_applied` |
| Invite Member | Form submission inside modal | `01_loaded`, `02_invite_modal`, `03_email_filled`, `04_invite_sent` |

---

## 🧰 How to Run

```bash
# 1. Activate environment
.\.venv\Scripts\activate

# 2. Run a task
python agent_b.py --url "https://linear.app/" --name "AgentB Demo Project"
python linear_tasks.py --task filter-issues
python linear_tasks.py --task invite-member