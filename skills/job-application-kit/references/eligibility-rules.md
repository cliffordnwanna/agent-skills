# Eligibility check

Report OK, Flag or Unknown (flags never block the work), and quote the exact line of the posting that decides it. Check each of these against `private/preferences.md`.

| Check | Look for | Result |
|---|---|---|
| Location | "US only", "must be based in", "authorised to work in", named countries or states | flag if the user's country is excluded; unknown if unclear |
| Timezone | required overlap hours, "must work EST hours" | flag if beyond the user's accepted overlap |
| Employment type | employee, contractor, "1099", EOR, "B2B" | flag if it conflicts with the user's choice |
| Remote status | fully remote, hybrid, on-site, "remote within a country" | compare with the user's arrangement |
| Visa and relocation | "visa sponsorship provided", "relocation package", "no sponsorship" | see below |
| Pay terms | currency, unit, equity-only, commission-only | equity-only or commission-only is flagged (default rule) |
| Language | required languages and fluency | OK, Flag or Unknown |
| Payment route | how contractors are paid | flag if the only route is one the user refuses |
| Start date and notice | start date, urgency | note conflicts |

## Visa sponsorship (when the user wants relocation)

- Sponsorship claims are common in scam listings. **Verify**: does the company's own careers page say it? Is it a licensed or registered sponsor in the destination country? Many countries publish an official sponsor register or employer data (for example the UK Home Office sponsor register). Check the current official source and cite it. If you cannot verify, mark "claimed, unverified".
- "Visa support" is not the same as "visa sponsorship". Quote the exact wording.
- Rank roles that offer verified sponsorship higher for these users.
- Do not give immigration or legal advice. Point to the official government source.

## When the posting is silent

Never assume. Mark it "unknown" and add the question to the action plan ("Is this role open to candidates in <country>?"). Do not reject a job for a missing detail.

## Output

A short table: check, result, deciding line, and a one-line verdict (OK, Flag, Unknown).
