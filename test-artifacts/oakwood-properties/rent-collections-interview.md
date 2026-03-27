# Rent Collections Test Case -- Interview Cheat Sheet

## Class-Level Onboard (from engagement root)

### When Claude asks: "What class of work is this?"
> Rent collections

### When Claude asks: "What does this class cover?"
> Weekly rent collection tracking for a 12-unit residential property. I track who has paid, who is late, and send delinquency notices.

### When Claude asks: "Key domain concepts?"
> Rent is due on the 1st of each month, late after the 5th. Late fee is $50 flat. Units are numbered 101 through 112. Monthly rents range from $1,200 to $1,800 depending on the unit.

### When Claude asks: "Shared data sources or systems?"
> I export the deposit register from my BofA account as a CSV. The tenant rent roll I keep in Google Sheets and export as CSV. Both tasks use the same two data files each week.

---

## Task 1: weekly-collection-report

### When Claude asks: "What task is this?"
> Weekly collection report

### When Claude asks: "What does this produce?" (Purpose)
> A status report showing which tenants have paid their March rent and which are still outstanding. Plus a late fee summary if we are past the 5th of the month.

### When Claude asks: "Where does the data come from?" (Data Sources)
> Two CSVs. The rent roll has unit, tenant_name, monthly_rent, lease_start, and lease_end. The deposit register has date, unit, tenant_name, amount, payment_method, and reference. Both are simple CSVs, no special formatting.

### When Claude asks: "Walk me through the procedure" (Procedure)
> For each unit in the rent roll, check if there's a matching deposit in the register for the current month. Match on unit number. If the deposit amount matches the monthly rent, mark as paid. If no deposit found, mark as outstanding. If we're past the 5th of the month and the tenant hasn't paid, they're late -- add a $50 late fee to what they owe. Then total it up: expected rent (always $17,400), collected so far, outstanding balance.

### When Claude asks: "How do you validate?" (Validation)
> Total expected rent must be $17,400 -- that's the sum of all monthly rents in the roll. If the expected total is different, the rent roll data is wrong. Collection percentage should be above 85% by the second Monday of any month. If it's lower, that's unusual.

### When Claude asks: "What artifacts must exist when done?" (Completion Criteria)
> A collection status report (CSV or markdown table) with one row per unit showing: unit, tenant, rent amount, paid/outstanding/late status, payment date if paid, late fee if applicable. And a summary section with totals. Plus a separate late fee summary if any tenants are late.

### When Claude asks: "Who do you call when something goes wrong?" (Contacts)
> I handle it directly -- it's my property. For bank questions, the BofA business banking line.

### When Claude asks: "What goes wrong?" (What Goes Wrong)
> Sometimes a tenant pays a partial amount -- like $1,000 on a $1,500 rent. I have to decide whether to count it as paid or track the balance. For now, treat partial payments as outstanding -- only exact match counts as paid. Also sometimes the deposit reference doesn't match the unit exactly, but the tenant name should match.

### When Claude asks: "Expected ranges?" (Expected Ranges)
> Total rent $17,400/month. Usually 10 of 12 pay on time (83%). By week 3, should be 11 or 12. Late fees are $50 each, so max late fee revenue is $600/month (all 12 late, which never happens).

### When Claude asks about scheduling: (Scheduling)
> Every Monday. Weekly.

### When Claude asks about task ordering:
> Order 1. This runs in parallel with the delinquency notices -- same data, different output.

### When Claude asks about period:
> 2026-W13 for the dry run. That's the week of March 23.

### When Claude asks about period format:
> Weekly.

### When Claude asks about dependencies: (Dependencies)
> No dependencies. This and the delinquency notices are independent.

---

## Task 2: delinquency-notices

### When Claude asks: "What task is this?"
> Delinquency notices

### When Claude asks: "What does this produce?" (Purpose)
> A letter for each tenant who is late on rent. Tells them what they owe including the $50 late fee and when they need to pay by.

### When Claude asks: "Where does the data come from?" (Data Sources)
> Same two files as the collection report -- rent roll and deposit register. No new data needed.

### When Claude asks: "Walk me through the procedure" (Procedure)
> First, figure out who hasn't paid -- same logic as the collection report, match deposits to the rent roll by unit number. Then check: if today is after the 5th of the month, generate a notice for each unpaid tenant. If it's on or before the 5th, just note "no notices needed this week" and stop. Each notice includes: tenant name, unit number, monthly rent amount, $50 late fee, total due (rent + late fee), and a payment deadline of end of current month.

### When Claude asks: "How do you validate?" (Validation)
> Number of notices should match the number of unpaid tenants. The amounts on each notice should be rent + $50, matching the rent roll exactly.

### When Claude asks: "What artifacts must exist when done?" (Completion Criteria)
> One text file per delinquent tenant in workpapers (e.g., notice-unit-103.txt). Plus a summary file listing all notices generated with amounts. If no notices needed, just a summary saying "no delinquencies this week".

### When Claude asks: "Who do you call when something goes wrong?" (Contacts)
> I handle it directly -- it's my property. For bank questions, the BofA business banking line.

### When Claude asks: "What goes wrong?" (What Goes Wrong)
> Sometimes I forget to update the rent roll when a lease renews at a different rate. Then the notice shows the wrong rent amount. Also, a tenant might have paid after the deposit CSV was exported but before I run the notices -- so I always double-check with the bank before actually sending.

### When Claude asks: "Expected ranges?" (Expected Ranges)
> Usually 1 to 3 notices per month. More than 4 is unusual. Each notice total is between $1,250 and $1,850 (rent + $50 late fee).

### When Claude asks about scheduling: (Scheduling)
> Monday, same as the collection report. Order 1, parallel.

### When Claude asks about period:
> 2026-W13.

### When Claude asks about period format:
> Weekly.

### When Claude asks about dependencies: (Dependencies)
> No dependencies. Runs in parallel with the collection report.
