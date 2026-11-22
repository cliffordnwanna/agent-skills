# Discovery mode: find the best-matched jobs

Use when the user asks to find jobs ("find me jobs", "top 5", "what should I apply for today"). It uses the client's own tools: the portfolio connector (or pasted CV) for the evidence, and built-in web search and page reading for the jobs. No extra setup.

## Steps
1. **Read the background** (portfolio connector or CV) and the saved preferences. Never assume a field or country.
2. **Build search terms** with `role-and-keyword-expansion.md`: title variants, adjacent roles, verticals, gig terms. Use several different queries, not one.
3. **Search broadly**: company career pages and applicant-tracking-system job pages, specialist and general job boards, region-appropriate boards. Prefer the original posting over aggregator copies.
4. **Open every candidate page.** Do not list a job from a search snippet alone. For each: confirm it is still open, read the posting date **from the page**, and read the location, eligibility and pay lines.
5. **Freshness.** Default window: posted in the last 48 hours (the user may ask for 24 hours or longer). If the date cannot be read from the page, set `date_verified` to false and rank those below verified ones, saying "date not verified". Never state a date you did not read. List pages and search results often hide dates, so check the posting itself.
6. **Screen** each (`eligibility-rules.md`, `legitimacy-checklist.md`, `pay-check.md`). Flags, not blocks. Drop dead links, duplicates and obvious scams from the list, and say how many you dropped and why in one line.
7. **Rank by real fit**, not keyword overlap: match each posting's requirements to the user's evidence (`role-and-keyword-expansion.md`, matching section). Prefer jobs the user can credibly win, plus a stretch or two worth the effort.
8. **Return the top five** (fewer if fewer qualify; never pad with weak ones) as a compact table: number, role at company, posted date (verified or not), link, one-line reason it fits, flags. Validate the underlying data against `DiscoveryResult` (`structured-output.md`).
9. **Then ask once:** "Reply with the numbers to prepare, or say 'all'." If the user already said to prepare them, go straight to apply-fast for each. Offer the Win Pack (`deep-prep.md`) for any of them.

## Honesty
You cannot see every job on the internet or guarantee a posting is still open the moment the user clicks. Say what you verified and what you did not.
