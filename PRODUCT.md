# Product <!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Developers who run many Claude Code sessions at once inside herdr (a terminal workspace manager
for AI coding agents), on Linux or macOS. Today: the maintainer and a teammate on a shared Linux
box, plus the maintainer's Mac; the repo is public, so anyone running herdr + Claude Code.

They open the page mostly **on a desktop browser** (confirmed), next to the terminal, to answer
"what did I leave half-done, and where?" and to bring one session back. A phone is a secondary
glance surface (the page is also published on the LAN behind a home dashboard).

## Product Purpose

Idle Claude sessions hold 0.5–1.2 GB each; people keep them open so they don't forget what they
were doing. herdr-valet parks them (writes a card, closes the pane) and hands them back with the
full conversation. The page exists so that closing a session costs nothing: success is the user
reading a card, instantly remembering the context, and resuming in one click — or confidently
deleting the card.

## Positioning

The only parker that writes **an AI summary of where you left off** (title, where we left off,
still pending, next step) for every parked session, parks **automatically** after N idle days,
**recovers sessions cut off by a reboot**, and shows it all on **a web page** with a Resume
button. Neighbors (herdr-agent-parking, claude-siesta, claude-session-management) offer manual
notes, a TUI, or a placeholder in the pane — not the summary-as-memory loop.

## Operating Context

- Glanced at between tasks, usually with a terminal (herdr) open beside it.
- Three lists: **Parked** (the main content: cards with summary, directory, branch, model, age,
  reason), **Open now** (live Claude panes with idle time and a Park button), **Recently resumed**.
- Actions: Resume in herdr (opens a workspace, ~1 s), Delete card (in-card confirmation),
  Park (summarizes with Haiku and closes, ~15 s).
- Failure states that must read clearly: herdr not running (Resume shows a copyable command),
  could not read herdr, summary missing ("(no automatic summary) First request: …").
- Card count is unknown and grows: assume anywhere from 0 to 30+ parked at once.

## Capabilities and Constraints

- One self-contained `web.html`, served by Python's standard library (`web.py`). **No external
  requests**: no CDN, no web fonts, no frameworks — it runs on 127.0.0.1, sometimes offline.
  System font stacks only.
- Data comes from `GET api/state`; actions are `POST api/{resume,delete,park}/<id>` with the
  `X-Parking: 1` header. Relative URLs only (it is served under a path prefix behind a proxy).
- Follows the **system color scheme** (light and dark) — confirmed.
- Summaries may be in English (new cards) or Spanish (older cards); both label sets must render.
- No per-session memory data is available: never show RAM numbers the backend does not provide.

## Brand Commitments

Name: **herdr-valet** (lowercase). Valet-parking metaphor: you hand over the session, get a card,
and get it back ready. No logo exists. *(Decided by the designer at the user's request, not by
the user: the name should be visible on the page.)*

## Evidence on Hand

Real cards from two users (titles, summaries, directories, branches, models). No users count,
testimonials or benchmarks — do not invent them.

## Product Principles

1. **The summary is the product.** The card must make "where was I?" answerable in seconds.
2. **Resume is one click; destructive actions confirm in place.**
3. **Scale to many cards** without turning into noise: scanning and finding a card matter more
   than decoration. *(Designer's call: add search and grouping by project when the list grows.)*
4. **Honest states:** say clearly when herdr is down or a summary is missing.

## Accessibility & Inclusion

Keyboard operable, visible focus, readable contrast in both themes, works at narrow widths.
