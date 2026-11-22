# Preferences intake (fast, multiple choice)

Part of `onboarding.md`. Run once on first use, and again when the user's goals change. Optimise for speed: send **all questions in one message** as lettered options, and let the user reply in a single line (for example "1 A,C - 2 B - 3 ..."). Where the client offers tappable choices, use them instead. Accept "skip" or "default" for anything.

Before asking, read the user's background and use it to fill in Question 2. Never assume the user's field, country, language or goals: everything below is a choice, not a default about them.

## The questions

**1. What are you looking for?** (pick all that apply)
- A. Quick gigs and short contracts (hourly work such as freelance, task or project work, AI training or data labelling, support or content work)
- B. Full-time or long-term remote work
- C. Relocation with visa sponsorship
- D. Part-time or side income

**2. Which roles?** (pick all that apply)
Build this list from the user's background, as lettered options: three to six role families that fit what they have done, **including adjacent roles** they could credibly do (for example, a support specialist may also fit community, operations, quality review, onboarding, or social media roles). Add the last option: "Other (type it)". Say clearly that this list is your reading of their background, not a fact. For each chosen role the skill will later build a keyword set (see `role-and-keyword-expansion.md`).

**3. Pay (hourly, in a foreign currency)**
- Currency: A. USD  B. EUR  C. GBP  D. Other (type it)
- Lowest hourly rate you will consider (jobs below it are flagged, never blocked): A. 10  B. 15  C. 20  D. 30  E. Other
- Hourly rate you are aiming for: A. 15 to 25  B. 25 to 40  C. 40 to 75  D. 75 or more  E. Other

(Salaried roles are converted to an approximate hourly rate for comparison.)

**4. Employment type**
- A. Employee  B. Contractor or freelance  C. Either

**5. Where and when**
- The country you work from: type it.
- Time-zone overlap you accept: A. Any  B. Up to 4 hours  C. Up to 8 hours  D. Must match my hours
- Only if you chose C in question 1, countries you would relocate to: A. Open to any  B. Europe  C. North America  D. Gulf or Asia-Pacific  E. Specific (type them)

**6. Getting paid** (pick all that apply)
- A. Bank transfer  B. Wise or Payoneer  C. PayPal  D. A platform's own payout  E. None of these, ask me

**7. Pace and documents**
- Applications you want to send per day: A. 1 to 5  B. 5 to 10  C. 10 to 20  D. 20 or more
- Documents: A. Files (DOCX and PDF, nothing to set up)  B. Reactive Resume (optional, guided setup)

**8. Your CV details** (type, one line)
Name, email, city and country, portfolio link, LinkedIn. Phone and street address are hidden by default.

## After the answers

Show a five-line summary and save it using `templates/preferences.example.md`. Remind the user that the preferences are private, especially the pay numbers, and where they are stored. Do not ask for anything else (notice period, start date, availability): ask only if a posting needs it.

## Defaults (not questions)

- Equity-only or commission-only pay does not count as pay. The user can change this.
- The CV hides phone and street address.
- A voice sample for cover letters is requested only the first time a letter is written.
- Screening problems are flagged, never blocking.
