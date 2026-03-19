#!/usr/bin/env python3
"""
Test the backend promoter with fake transcripts to see if relevant promotions surface.

Run from repo root:
  cd /Users/zhusiyi/TD1-Capstone
  USE_MOCK_LLM=false python scripts/test_promoter_scenarios.py

With USE_MOCK_LLM=true the promoter returns no recommendations (mock); set to false
and have the summarizer LLaMA model available to get real recommendations.
"""

import os
import sys
import json

# Run from repo root so services/summarizer is discoverable
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SUMMARIZER = os.path.join(_REPO_ROOT, "services", "summarizer")
if _SUMMARIZER not in sys.path:
    sys.path.insert(0, _SUMMARIZER)

from llama import promoter, _mock_promoter

# If mock LLM is enabled, use mock promoter so this script runs without loading the model
if os.getenv("USE_MOCK_LLM", "false").lower() == "true":
    promoter = _mock_promoter  # noqa: F811

# ---------------------------------------------------------------------------
# Scenario transcripts (fake call transcripts)
# ---------------------------------------------------------------------------

SCENARIO_1_TRANSCRIPT = """
Agent: Thank you for calling TD Bank. My name is Sarah. Before we continue, may I confirm your full name?
Caller: Sure, it's Alex Brown.
Agent: Thanks Alex. For verification purposes, could you confirm your postal code?
Caller: Actually I think I might have called the wrong number. I was trying to reach my internet provider but I must have dialed incorrectly.
Agent: No problem at all. This is TD Bank customer support.
Caller: Oh okay, sorry about that. While I have you on the line, do you happen to know if the TD branch on Bloor Street is open tomorrow?
Agent: Yes, that branch should be open during normal hours tomorrow.
Caller: Great, thanks for letting me know. Sorry again for the confusion.
Agent: No worries at all. Have a great day.
"""

SCENARIO_2_TRANSCRIPT = """
Agent: Thank you for calling TD Bank. My name is Daniel. Before we begin, may I confirm your full name?
Caller: Yes, it's Maria Garcia.
Agent: Thank you Maria. For verification, could you confirm your date of birth and the postal code on your account?
Caller: Sure, my birthday is April 18th 1996 and my postal code is M5V 2T6.
Agent: Perfect, thank you for confirming that. How can I help you today?
Caller: I'm calling because I lost my debit card yesterday evening and I'm really worried about it.
Agent: I'm sorry to hear that. Do you know roughly when or where you may have lost it?
Caller: I think it might have fallen out of my wallet while I was taking the subway home.
Caller: I checked my account this morning and I didn't see any strange transactions yet, but I'm still really concerned someone might try to use it.
Caller: Could you please cancel the card and issue a replacement?
Caller: I also have some bills coming up this week so I want to make sure my account will still work.
Agent: Absolutely, I can cancel the card right away and arrange a replacement for you.
Caller: Thank you, that would really help. I was pretty stressed about it.
"""

SCENARIO_3_TRANSCRIPT = """
Agent: Thank you for calling TD Bank. My name is Michael. May I confirm your full name before we begin?
Caller: Yes, my name is Kevin Li.
Agent: Thanks Kevin. For verification, could you confirm your date of birth and postal code?
Caller: Sure, my birthday is July 12th 2003 and my postal code is M4Y 1A7.
Agent: Perfect, thank you. How can I help you today?
Caller: I'm currently a student at the University of Toronto and I wanted to ask about opening a savings account.
Caller: Right now I only have a student chequing account with TD that I use for everyday spending.
Caller: I recently started a part-time job on campus and I want to start putting some money aside every month.
Caller: I was wondering if TD offers any savings accounts with good interest rates for students.
Caller: Ideally I'd prefer something with no monthly fee because I'm trying to keep my costs low.
Caller: Also are there any minimum balance requirements that I should know about?
Caller: If there are any promotions or special student offers I'd definitely be interested.
"""

SCENARIO_4_TRANSCRIPT = """
Agent: Thank you for calling TD Bank wealth services. My name is Rachel. May I confirm your full name?
Caller: Yes, this is Robert Chen.
Agent: Thank you Mr. Chen. For verification purposes, could you confirm your date of birth and the postal code on file?
Caller: Sure, my birthday is September 3rd 1978 and my postal code is M2N 5S2.
Agent: Perfect, thank you. How can I assist you today?
Caller: I wanted to talk about my investment accounts with TD.
Caller: I've had a portfolio with the bank for several years now and I usually check in every so often to see if there are better opportunities available.
Caller: Recently the market seems a bit more volatile and I'm wondering if it makes sense to adjust my investments.
Caller: Right now I have a mix of mutual funds and ETFs.
Caller: I also heard there might be promotional offers for certain investment products.
Caller: Could you check if I might qualify for anything like that?
"""

SCENARIO_5_TRANSCRIPT = """
Agent: Thank you for calling TD Bank. My name is Olivia. May I confirm your full name?
Caller: Yes, it's Emily Watson.
Agent: Thank you Emily. For verification, could you confirm your date of birth and postal code?
Caller: Sure, my birthday is February 20th 1985 and my postal code is M6J 3K1.
Agent: Great, thank you. How can I help you today?
Caller: I recently received a notice that my mortgage term is coming up for renewal in a few months.
Caller: I wanted to understand what my options are before the renewal date arrives.
Caller: Right now my mortgage is on a fixed rate.
Caller: I've been hearing a lot about interest rates changing recently and I'm wondering if switching to a variable rate might make sense.
Caller: I'm also curious if TD offers any incentives for renewing early.
Caller: I just want to make sure I'm making the best decision before the renewal deadline.
"""

# ---------------------------------------------------------------------------
# Mock client profiles (aligned with MOCK CLIENT DATA — for promoter context)
# ---------------------------------------------------------------------------

# Scenario 1 — Random call (wrong number): Alex Brown — minimal/unknown assets in seed
CLIENT_PROFILE_1 = (
    "Name: Alex Brown. "
    "Assets: 0.00. "
    "Address: Toronto, M5V2T6. No employment info. No accounts."
)

# Scenario 2 — Lost debit card: Maria Garcia
CLIENT_PROFILE_2 = (
    "Name: Maria Garcia. "
    "Assets: 18000.00. "
    "Address: Toronto, M5V2T6. "
    "Employment: Employed, RetailCo, Supervisor. "
    "Accounts: Checking 2500, Savings 15500."
)

# Scenario 3 — University student: Kevin Li
CLIENT_PROFILE_3 = (
    "Name: Kevin Li. "
    "Assets: 3200.00. "
    "Address: Toronto, M4Y1A7. "
    "Employment: Student, University of Toronto, part-time Campus Library. "
    "Accounts: Student Checking 800, Savings 2400."
)

# Scenario 4 — Wealth client: Robert Chen
CLIENT_PROFILE_4 = (
    "Name: Robert Chen. "
    "Assets: 850000.00. "
    "Address: North York, M2N5S2. "
    "Employment: Business Owner, Logistics. "
    "Accounts: Checking 40000, Investment 810000."
)

# Scenario 5 — Mortgage client: Emily Watson
CLIENT_PROFILE_5 = (
    "Name: Emily Watson. "
    "Assets: 220000.00. "
    "Address: Toronto, M6J3K1. "
    "Employment: Employed, City of Toronto. "
    "Accounts: Checking 6000, Mortgage 480000."
)

# ---------------------------------------------------------------------------
# Fake promotion catalog (so promoter has something to recommend)
# Format matches what get_promo_catalog() returns: promo_id, name, description, conditions
# ---------------------------------------------------------------------------

FAKE_PROMOTION_CATALOG = [
    {
        "promo_id": "1",
        "name": "Student High-Interest Savings",
        "description": "No monthly fee high-interest savings account for students. Good interest rate, no minimum balance. For students at recognized institutions.",
        "conditions": {"student": True, "max_assets": 50000},
    },
    {
        "promo_id": "2",
        "name": "10% Off Credit Card Annual Fee",
        "description": "10% off credit card annual fee for eligible clients.",
        "conditions": {"min_assets": 100000},
    },
    {
        "promo_id": "3",
        "name": "Investment Platform Fee Waiver",
        "description": "Promotional fee waiver on TD Direct Investing for new or existing investment clients. Limited time.",
        "conditions": {"min_assets": 500000},
    },
    {
        "promo_id": "4",
        "name": "Mortgage Renewal Cash Back",
        "description": "Cash back incentive for clients who renew their mortgage with TD. Applies to early renewal or renewal at term end.",
        "conditions": {"has_mortgage": True},
    },
    {
        "promo_id": "5",
        "name": "New Savings Account Bonus",
        "description": "Bonus interest rate for new high-interest savings accounts opened in the next 90 days.",
        "conditions": {},
    },
]

# ---------------------------------------------------------------------------
# Scenarios to run: (label, transcript, client_profile)
# ---------------------------------------------------------------------------

SCENARIOS = [
    ("Scenario 1 — Random Call (Wrong Number)", SCENARIO_1_TRANSCRIPT, CLIENT_PROFILE_1),
    ("Scenario 2 — Lost Debit Card (Upset Client)", SCENARIO_2_TRANSCRIPT, CLIENT_PROFILE_2),
    ("Scenario 3 — University Student Opening Savings", SCENARIO_3_TRANSCRIPT, CLIENT_PROFILE_3),
    ("Scenario 4 — Investment Client", SCENARIO_4_TRANSCRIPT, CLIENT_PROFILE_4),
    ("Scenario 5 — Mortgage Renewal", SCENARIO_5_TRANSCRIPT, CLIENT_PROFILE_5),
]


def main():
    use_mock = os.getenv("USE_MOCK_LLM", "false").lower() == "true"
    print("Promoter test with fake transcripts")
    print("USE_MOCK_LLM =", use_mock)
    if use_mock:
        print("(Mock mode: no LLM, so promoter always returns 0 recommendations.)")
    else:
        print("(Real LLM: promoter will automatically recommend from catalog when relevant.)")
    print()

    for label, transcript, client_profile in SCENARIOS:
        print("=" * 60)
        print(label)
        print("=" * 60)
        print("Transcript (first 400 chars):", transcript.strip()[:400], "...")
        print()
        print("Client profile:", client_profile[:200], "..." if len(client_profile) > 200 else "")
        print()

        result = promoter(transcript, client_profile, FAKE_PROMOTION_CATALOG)

        recs = result.get("recommendations", [])
        no_relevant = result.get("no_relevant_flag", True)

        print("Result:")
        print("  no_relevant_flag:", no_relevant)
        print("  recommendations:", len(recs))
        for i, r in enumerate(recs, 1):
            print(f"  [{i}] promo_id={r.get('promo_id')} name={r.get('name')}")
            print(f"      reason={r.get('reason', '')[:120]}")
        print()

    print("Done.")


if __name__ == "__main__":
    main()
