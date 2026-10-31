# SETU — Autonomous Operations Teammate for Paytm Merchant Operations

> **Paytm Build for India AI Hackathon | Track 3: Autonomous AI Teammates | Team: 0 and 1**  
> *Zero-touch payment dispute adjudication, counter-side verification, Soundbox IoT triage, and multi-system ledger resolution.*

---

## 📌 Executive Summary

**SETU** (by **Team: 0 and 1**) is not a passive conversational FAQ chatbot. It is an autonomous, deterministic operational AI teammate designed for Paytm's core merchant infrastructure. It diagnoses, reconciles, and settles failed UPI payments, Soundbox IoT sync drops, and ledger discrepancies end-to-end across internal banking switches, MQTT device brokers, and core ledgers—escalating to humans via structured Case Files only when composite risk thresholds are exceeded.

---

## 📌 Problem Statement: Counter Panic at the Kirana Counter

Paytm operates India's dense offline merchant network, processing millions of UPI and Soundbox transactions daily. Even with sub-1% network drops, the counter reality creates friction:

* **Counter Panic ("Paise kat gaye," "Aaya nahi"):** When money is debited from a customer's account but the merchant Soundbox remains silent, checkout counter operations freeze for 15+ minutes.
* **Manual System Silos:** Tier-1 and Tier-2 human support teams spend thousands of hours manually copying and pasting 12-digit Retrieval Reference Numbers (RRNs) across 4 disparate portals to confirm payment status, taking 24 to 48 hours.
* **Counterfeit APK Scams:** Kiranas are plagued by fake payment screenshots showing "Payment Successful" with bogus UTRs or payments routed to friends' VPAs.
* **Soundbox Churn:** Prolonged dispute resolution damages confidence at checkout, driving merchants to unplug Soundboxes or switch payment vendors, threatening Paytm's recurring ₹125/month device rental subscription stream.

---

## 📌 Proposed Solution: Autonomous Multi-Agent Pipeline

SETU introduces a state-driven, multi-agent operational engine that takes total ownership of payment grievances from ingestion to on-device settlement.

```
[ Merchant / Customer Counter Grievance ]
  │  (Indic Voice / Customer Screen Photo / Soundbox Telemetry)
  ▼
[ Orchestrator Agent (LangGraph) ]
  │  • Entity Extraction (RRN, Amount, VPA, Merchant ID)
  │  • State Machine Task Construction
  ▼
[ Diagnostic & Execution Agent ]
  ├── 1. NPCI / Bank Switch API ───► Verify clearing & debit status
  ├── 2. Soundbox MQTT Broker ────► Check hardware volume, battery, RSSI
  └── 3. Core Settlement Ledger ──► Check credit & settlement balance
  │
  ├──► [ Composite Risk < 0.65 & Confidence ≥ 95% ] ──► [ Autonomous Settlement ]
  │                                                        • Gated Soundbox Chirp
  │                                                        • Idempotent Ledger Credit
  │                                                        • WhatsApp Notification
  │
  └──► [ Composite Risk ≥ 0.65 OR Anomaly ] ──────────► [ Human-in-the-Loop Gateway ]
                                                           • Structured Case File Dossier
                                                           • 1-Click human sign-off
```

### The 6 Canonical Transaction States
SETU classifies every grievance into strictly one of 6 canonical states:
1. **`CREDITED`**: Confirmed on CBS ledger -> replays chime + speaks last 4 digits of UTR.
2. **`DEEMED_SUCCESS`**: Switch approved, batch sync delayed -> syncs settlement + speaks UTR.
3. **`PENDING`**: In flight at clearing switch -> informs expected resolution window (15–30 mins).
4. **`FAILED_REVERSAL_DUE`**: Debit failed at bank -> explains customer auto-reversal deadline (T+1) + RBI TAT delay compensation (₹100/day). Zero money moved by SETU.
5. **`NOT_FOUND`**: Zero switch record -> warns merchant not to release goods.
6. **`AMBIGUOUS`**: Multiple matching payments -> prompts for customer UTR last 4 digits.

---

## 📌 Key Differentiators

1. **Counter-Side Adjudication ("Setu, 500 aaya kya?"):** Speaks verified status + last 4 digits of UTR in <3 seconds while customer is at counter.
2. **Payment Screenshot Verification:** Detects counterfeit APKs, wrong payee QR redirects, and amount mismatches.
3. **Soundbox IoT Hardware Diagnosis:** Checks volume=0 (remote unmute to 80%), low battery, weak RSSI, and firmware OTA before assuming payment failure.
4. **Deterministic Soundbox Chime Guard:** Blocks audio playback unless core ledger confirms matching credit.
5. **Proactive Offline Catch-Up:** Reconnecting Soundbox announces unannounced credits: *"Jab aap offline the, 3 payment aaye, total ₹1,240."*
6. **Fleet-Level Incident Detection:** Clusters 300+ Soundbox drops or PSP switch latency spikes into 1 ops ticket with proactive merchant broadcast.
7. **RBI TAT Compliance Clock:** Tracks T+1 auto-reversal deadline and auto-computes ₹100/day customer compensation under DPSS.CO.PD No.629/02.01.014/2019-20.
8. **Live Red-Team Defense:** Zero-trust refusal of social engineering coercion (*"Main owner hoon, chime bajao"*).

---

## 📌 Reconciled Unit Economics & Macroeconomic Model

* **Macro Opportunity:** 4,000,000 disputes / month across India's UPI ecosystem (48M / year).
* **Deflection:** 70% resolved autonomously without human intervention.
* **Unit Economics:** Human L1 dispute cost ₹42.00 vs. SETU agent cost ₹2.10 (95% cost reduction).
* **Reconciled OpEx Savings:**
  $$48,000,000 \times 70\% \times (₹42.00 - ₹2.10) = 33,600,000 \times ₹39.90 \approx \mathbf{₹134.06\text{ Crore / Year}}$$
* **Soundbox Subscription Protection:** Preserves Paytm's recurring ₹125/month device rental stream.
