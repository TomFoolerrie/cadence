# Treasury Test Case — Interview Cheat Sheet

## Class-Level Onboard (from engagement root)

### When Claude asks: "What class of work is this?"
> Treasury

### When Claude asks: "What does this class cover?"
> Cash management and bank account operations. All our bank accounts are with Bank of America. We close monthly, starting the first Monday after month-end.

### When Claude asks: "Key domain concepts?"
> We use ZBA accounts — zero balance accounts. We have a master operating account, 1010, and four subsidiary ZBA accounts, 1011 through 1014. The subs sweep to the master daily. Service charges hit the master account.

### When Claude asks: "Shared data sources or systems?"
> Bank of America CashPro for all bank data. QuickBooks Online is our GL. Everything comes out of CashPro as CSVs.

---

## Task 1: bank-fee-analysis

### When Claude asks: "What task is this?"
> Bank fee analysis

### When Claude asks: "What does this produce?" (Purpose)
> A journal entry that books the monthly bank service charges. We categorize them — wire fees, ACH fees, lockbox, positive pay, account maintenance — and book them to sub-accounts under 6210 Bank Charges, with a credit to 1010.

### When Claude asks: "Where does the data come from?" (Data Sources)
> A CSV export from CashPro. It's all the fee and charge transactions for the month. Columns are date, description, amount, and reference number.

### When Claude asks: "Walk me through the procedure" (Procedure)
> I look at the description to figure out the category. Wire fees say "WIRE TRANSFER FEE" — domestic ones say "DOMESTIC", international say "INTERNATIONAL". ACH says "ACH" then "DEBIT FEE" or "CREDIT FEE". Lockbox says "LOCKBOX". Positive pay says "POSITIVE PAY". Account maintenance says "ACCOUNT MAINTENANCE". Everything else is "other". I sum by category, then build the JE. Debits go to 6210.1 through 6210.5 by category, credit goes to 1010.

### When Claude asks: "How do you validate?" (Validation)
> Total should be between $800 and $1,200 most months. If it's over $1,500 something is wrong. Wire fees are $25 domestic, $45 international. ACH fees are $0.50 for debits, $0.25 for credits.

### When Claude asks: "What artifacts must exist when done?" (Completion Criteria)
> A JE CSV in workpapers with columns: date, account_number, account_name, debit, credit, memo. And a summary workpaper showing the totals by category.

### When Claude asks: "Who do you call when something goes wrong?" (Contacts)
> Our BofA relationship manager, Jennifer Walsh.

### When Claude asks: "What goes wrong?" (What Goes Wrong)
> Sometimes there's a one-time fee that throws off the total — like an annual account review fee. Also sometimes the description format changes slightly and the categorization breaks.

### When Claude asks: "Expected ranges?" (Expected Ranges)
> Total fees $800-$1,200. Wire fees $25 domestic, $45 international. ACH $0.50 debit, $0.25 credit. Lockbox around $150/month. Positive pay $75/month. Account maintenance $500/month.

### When Claude asks about scheduling: (Scheduling)
> First Monday after month-end.

### When Claude asks about task ordering: (Dependencies)
> This can run in parallel with the ZBA sweep entries. The bank recon has to wait for both. So this is order 1.

### When Claude asks about period:
> Use 2026-02 for the dry run. That's February close.

### When Claude asks about period format:
> Monthly.

---

## Task 2: zba-sweep-entries

### When Claude asks: "What task is this?"
> ZBA sweep entries

### When Claude asks: "What does this produce?" (Purpose)
> A journal entry that books the net monthly sweeps between each subsidiary ZBA account and the master. Each sub should net to zero over time, but any given month has a net direction.

### When Claude asks: "Where does the data come from?" (Data Sources)
> CashPro CSV of sweep transactions. Columns are date, from_account, to_account, amount, and reference.

### When Claude asks: "Walk me through the procedure" (Procedure)
> Group by subsidiary account number. For each sub, compute the net flow for the month. If from_account is the sub and to_account is 1010, that's money flowing TO master (debit 1010, credit the sub). If from_account is 1010 and to_account is the sub, that's money flowing FROM master (debit the sub, credit 1010). Net them up and build one JE line per subsidiary.

### When Claude asks: "How do you validate?" (Validation)
> The net of all sweeps across all subsidiaries must be zero — it's a closed system, money just moves between accounts. If it doesn't net to zero, something is wrong with the data.

### When Claude asks: "What artifacts must exist when done?" (Completion Criteria)
> A JE CSV with the net sweep entries. And a reconciliation workpaper showing the daily sweep detail grouped by subsidiary with monthly net per account.

### When Claude asks: "Who do you call when something goes wrong?" (Contacts)
> Our BofA relationship manager, Jennifer Walsh.

### When Claude asks: "What goes wrong?" (What Goes Wrong)
> Occasionally a sweep transaction shows up with a wrong account number — like 1015 which doesn't exist. That means something new happened and we need to investigate.

### When Claude asks: "Expected ranges?" (Expected Ranges)
> Daily sweeps are usually between $500 and $20,000 per subsidiary. Monthly net per subsidiary should be under $50,000. The total net across all subs must be exactly zero.

### When Claude asks about scheduling: (Scheduling)
> First Monday after month-end. Same as bank fees.

### When Claude asks about task ordering: (Dependencies)
> Order 1 — runs in parallel with bank fees. The bank recon depends on this completing first.

### When Claude asks about period:
> 2026-02.

### When Claude asks about period format:
> Monthly.

---

## Task 3: bank-reconciliation

### When Claude asks: "What task is this?"
> Bank reconciliation

### When Claude asks: "What does this produce?" (Purpose)
> A reconciliation workpaper that proves the GL balance for account 1010 matches the bank statement, after adjusting for outstanding checks and deposits in transit.

### When Claude asks: "Where does the data come from?" (Data Sources)
> Two files. One is a GL trial balance extract for just account 1010 — columns are account_number, account_name, period, debit_balance, credit_balance, ending_balance. The other is the bank statement summary with ending balance and outstanding items — columns are account_number, statement_date, ending_balance, outstanding_checks, deposits_in_transit. The outstanding_checks field has semicolon-separated entries like "CHECK 4501:2500.00;CHECK 4502:1500.00".

### When Claude asks: "Walk me through the procedure" (Procedure)
> Take the bank statement ending balance. Parse and subtract each outstanding check. Add deposits in transit. That gives the adjusted bank balance. Compare it to the GL ending balance. If they match, we're done. If they don't, list the difference and figure out what's missing.

### When Claude asks: "How do you validate?" (Validation)
> The reconciliation difference must be zero. If it's not zero, something is missing or posted wrong.

### When Claude asks: "What artifacts must exist when done?" (Completion Criteria)
> A reconciliation workpaper showing: bank statement ending balance, minus outstanding checks (itemized), plus deposits in transit, equals adjusted bank balance, compared to GL balance. Difference line at the bottom.

### When Claude asks: "Who do you call when something goes wrong?" (Contacts)
> Our BofA relationship manager, Jennifer Walsh. Or the QuickBooks admin if the GL side looks wrong.

### When Claude asks: "What goes wrong?" (What Goes Wrong)
> Usually it's a timing issue — a check cleared after statement date but before the GL was closed, or vice versa. Sometimes a deposit gets posted to the wrong account in QB.

### When Claude asks: "Expected ranges?" (Expected Ranges)
> The difference must be exactly zero. Outstanding checks are usually under $10,000 total. Deposits in transit are usually under $5,000.

### When Claude asks about scheduling: (Scheduling)
> First Wednesday after month-end. Gives us two days after the Monday tasks to get the JEs posted.

### When Claude asks about task ordering: (Dependencies)
> This has to run after bank fees and ZBA entries are done. The GL balance isn't right until those JEs are booked. So this is order 2.

### When Claude asks about period:
> 2026-02.

### When Claude asks about period format:
> Monthly.

---

## Session 3: Second Period Correction

When running `/done` for the March bank-fee-analysis, give this correction:

> The row "WIRE TRANSFER FEE" at $45 on March 17 was miscategorized as domestic. It's actually an international wire — the bank just didn't include "INTERNATIONAL" in the description this time. The categorization logic should check the amount too: any wire fee of $45 should be categorized as international, since domestic wires are always $25. Update the tool and the SKILL.md procedure to reflect this.
