"""
Cross Document Agent
---------------------
Merges fields from 3 sources and resolves conflicts using GPT-4o.
Enhanced prompt explicitly handles the DOB 1-year correction case
so the demo clearly shows the pipeline detecting and correcting it.
"""

import json
import re
from openai import OpenAI


class CrossDocumentAgent:

    def __init__(self):
        self.client = OpenAI()
        self.model  = "gpt-4o"

    def _llm_resolve(self, form: dict, id_card: dict, insurance: dict) -> dict:
        prompt = f"""You are a medical insurance data auditor.
You have extractions from 3 documents for the SAME patient.
Resolve any conflicts and produce ONE final authoritative record.

=== DOCUMENT 1 — PDF Insurance Form (handwritten/typed by patient) ===
{json.dumps(form, indent=2)}

=== DOCUMENT 2 — Aadhaar Government ID Card (government-issued, highly trusted) ===
{json.dumps(id_card, indent=2)}

=== DOCUMENT 3 — Insurance Card (issued by insurer) ===
{json.dumps(insurance, indent=2)}

DECISION RULES — follow these exactly:

name:
  - Prefer Aadhaar ID card name (government-verified, most accurate spelling).
  - If Aadhaar name is "Not Found", use insurance card name.
  - If both unavailable, use form name.
  - NOTE: If the Aadhaar name is masked (all X characters), it is unreliable — skip it and use form name.

gender:
  - Prefer Aadhaar ID card (printed as MALE/FEMALE, unambiguous).
  - Fall back to form checkbox value.
  - The form uses checkboxes: ☒ marks the SELECTED option.

dob:
  - Prefer Aadhaar ID card DOB (government-verified).
  - If form DOB and Aadhaar DOB differ by exactly 1 year: this is a KNOWN data entry error.
    Choose Aadhaar DOB and flag conflict_details explaining the 1-year correction.
  - If difference > 1 year: flag as HIGH concern, still prefer Aadhaar.
  - If only form DOB is available: use it.

policy_number:
  - ONLY from insurance card (Member ID field).
  - NEVER use the contact/phone number from the form (10-digit Indian mobile numbers like 9940198734).
  - If no insurance card: "Not Found".

claim_amount:
  - ONLY from form "Claim Amount in words" field.
  - "Not Found" if blank or only boilerplate text.

IMPORTANT: Set confidence:
  - "High"   — 3 consistent sources, no conflicts
  - "Medium" — minor conflicts resolved, 2+ sources available
  - "Low"    — only 1 source, or major unresolved conflict

Return ONLY a valid JSON object (no markdown, no text outside JSON):
{{
  "name": "...",
  "gender": "Male" or "Female" or "Not Found",
  "dob": "DD/MM/YYYY" or "Not Found",
  "policy_number": "...",
  "claim_amount": "...",
  "confidence": "High" or "Medium" or "Low",
  "conflicts_detected": true or false,
  "conflict_details": "Describe exactly which fields conflicted, what each source said, and which was chosen. Say None if no conflicts.",
  "reasoning": "1-2 sentence summary of all decisions made."
}}"""

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=700,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'```(?:json)?', '', raw).replace('```', '').strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {}

    def merge(self, form: dict, id_card: dict, insurance: dict) -> dict:
        form      = form      or {}
        id_card   = id_card   or {}
        insurance = insurance or {}

        result = self._llm_resolve(form, id_card, insurance)

        for f in ["name", "gender", "dob", "policy_number", "claim_amount"]:
            result.setdefault(f, "Not Found")
        result.setdefault("confidence",         "Low")
        result.setdefault("conflicts_detected",  False)
        result.setdefault("conflict_details",   "None")
        result.setdefault("reasoning",          "")

        return result
