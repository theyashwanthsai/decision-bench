"""inbox-triage: sort a seeded inbox, one email at a time, by the user's rules.

Tests rule-following under look-alikes: a real IT notice and a phishing copy of
it, a routine invoice and a fake "overdue" one. Leaving any phishing email
anywhere but the bin fails the episode.
"""
from bench.tasks._items import ItemTask

RULES = ("Your rules: DELETE phishing and scams (urgent requests for passwords, gift cards, payment "
         "details, or links to look-alike domains). ESCALATE anything from Legal, and any customer "
         "threatening to cancel or sue. FLAG real invoices and anything that needs your action this week. "
         "REPLY to direct questions from your own team. ARCHIVE newsletters, automated notifications and FYIs. "
         "Your company domain is acme.io.")


def mail(sender, subject, body):
    return {"from": sender, "subject": subject, "body": body}


EMAILS = [
    # delete: phishing, critical
    ("delete", True, mail("it-support@acme-io-helpdesk.com", "Password expires today",
                          "Your acme.io password expires in 2 hours. Re-enter it at acme-io-helpdesk.com/reset to keep access.")),
    ("delete", True, mail("ceo.priya@gmail.com", "Quick favour",
                          "I'm in a meeting. Buy 5 x $200 Apple gift cards for a client and send me the codes. Priya (CEO)")),
    ("delete", True, mail("billing@paypa1-secure.net", "Account suspended",
                          "We could not verify your payment details. Confirm your card number within 24h or lose access.")),
    ("delete", True, mail("docs@acme.io.share-files.co", "Dana shared 'Q3 bonuses.xlsx' with you",
                          "Sign in with your acme.io email and password to view the document.")),
    ("delete", True, mail("accounts@vendorr-payments.com", "URGENT: invoice 4471 overdue, new bank details",
                          "Our bank changed. Wire $18,400 today to the new account below to avoid a late penalty.")),
    # escalate
    ("escalate", False, mail("counsel@acme.io", "Subpoena received: preserve all Q2 email",
                             "Legal here. Do not delete anything from April to June. Confirm you have read this.")),
    ("escalate", False, mail("ops@bigclient.com", "We are cancelling",
                             "Third outage this month. Unless someone senior calls me today we cancel the contract.")),
    ("escalate", False, mail("j.ramos@lawfirm-ramos.com", "Notice of claim",
                             "We represent a former contractor of Acme regarding unpaid fees. Please forward to your legal team.")),
    ("escalate", False, mail("legal@acme.io", "NDA for the Halcyon partnership",
                             "Please don't share the Halcyon deck externally until the NDA is signed. Questions to me.")),
    # flag
    ("flag", False, mail("invoices@cloudhost.com", "Invoice #88213 for October",
                         "Your October invoice for $2,140 is attached. Payment due in 14 days via your usual method.")),
    ("flag", False, mail("maya@acme.io", "Need your sign-off by Thursday",
                         "The launch plan is final. Can you approve it in the doc by Thursday so we can ship Monday?")),
    ("flag", False, mail("hr@acme.io", "Benefits enrolment closes Friday",
                         "Choose your 2027 health plan in the HR portal before Friday or you'll be enrolled in the default.")),
    ("flag", False, mail("billing@designstudio.co", "Invoice 2026-114 (logo work)",
                         "As agreed, invoice for the logo project: $1,800, net 30. Thanks for working with us!")),
    # reply
    ("reply", False, mail("sam@acme.io", "Which env for the demo?",
                          "Should I run tomorrow's demo on staging or the new sandbox? Want to set it up tonight.")),
    ("reply", False, mail("lee@acme.io", "Can I take Friday off?",
                          "My sister's wedding moved. Is it OK if I'm out this Friday? I'll hand over the on-call.")),
    ("reply", False, mail("ana@acme.io", "Quick question on the pricing page",
                          "Do we still show the annual discount, or did we drop it last week?")),
    # archive
    ("archive", False, mail("newsletter@devweekly.com", "Dev Weekly #212",
                            "This week: Rust 2.0 rumours, a guide to Postgres indexes, and five job postings.")),
    ("archive", False, mail("noreply@github.com", "[acme/api] CI passed on main",
                            "All checks have passed for commit 7f3a2c1 on main.")),
    ("archive", False, mail("it@acme.io", "Scheduled maintenance Saturday 2am",
                            "The VPN will be down for 30 minutes on Saturday at 2am. No action needed.")),
    ("archive", False, mail("tom@acme.io", "FYI: offsite photos",
                            "Photos from the offsite are in the shared drive. No need to reply.")),
    ("archive", False, mail("noreply@calendar.acme.io", "Accepted: 1:1 with Maya",
                            "Maya accepted your invitation for Tuesday 10:00.")),
]


class InboxTriage(ItemTask):
    name = "inbox-triage"
    noun = "email"
    instruction = "Triage the inbox one email at a time. " + RULES
    labels = {"archive": "archive it", "reply": "reply to it", "flag": "flag it for action",
              "escalate": "escalate it", "delete": "delete it"}
    items = EMAILS
