"""
Extraction Agent v3
--------------------
Key fixes:
- Insurance card: extracts name from "Member Name" label first,
  NOT from the first name-looking line (which could be a dependent)
- Gender: checks filled checkbox ADJACENT to Male/Female correctly
- Claim amount: rejects boilerplate "I, , son/daughter..." lines
- DOB: rejects dates that look like effective/policy dates (future or on insurance card)
"""

import re


class ExtractionAgent:

    # ── Name ──────────────────────────────────────────────────────────────

    def clean_name(self, name: str) -> str:
        if not name or name == "Not Found":
            return "Not Found"
        for word in ["Gender", "DOB", "Date", "prefer", "say"]:
            name = re.sub(rf'\b{re.escape(word)}\b', '', name, flags=re.IGNORECASE)
        name = re.sub(r'[^A-Za-z\s\-]', '', name)
        name = " ".join(name.split())
        return name if len(name) >= 2 else "Not Found"

    def extract_name(self, text: str) -> str:
        """
        Strategy 1 — Form labels:        First Name: X   Last Name: Y
        Strategy 2 — Insurance card:     "Member Name" label (NOT dependents)
        Strategy 3 — Aadhaar Title-case: e.g. "Nandhini Suresh"
        Strategy 4 — Uppercase fallback
        """
        # Strategy 1: PDF form labels
        first_m = re.search(r'First\s*Name\s*[:\-]?\s*([A-Za-z][A-Za-z\s]*)', text)
        last_m  = re.search(r'Last\s*Name\s*[:\-]?\s*([A-Za-z][A-Za-z\s]*)',  text)
        if first_m:
            first = first_m.group(1).strip().split('\n')[0].strip()
            last  = ""
            if last_m:
                raw_last = last_m.group(1).strip().split('\n')[0].strip()
                # Only accept last name with >=2 real alpha chars (blocks "S" or "Ss" noise)
                if len(re.sub(r'[^A-Za-z]', '', raw_last)) >= 2:
                    last = raw_last
            full = f"{first} {last}".strip() if last else first
            return self.clean_name(full)

        # Strategy 2: Insurance card — look for explicit "Member Name" label
        # This prevents picking up a dependent's name from the right column
        member_name_m = re.search(
            r'Member\s*Name\s*[:\n]\s*([A-Za-z][A-Za-z\s]+)',
            text, re.IGNORECASE
        )
        if member_name_m:
            name = member_name_m.group(1).strip().split('\n')[0].strip()
            return self.clean_name(name)

        # Strategy 3: Aadhaar — Title-case English name line
        SKIP = {"Aadhaar", "India", "Government", "Insurance", "BlueCross",
                "BlueShield", "Dependents", "Enrolled", "Member", "Effective",
                "Benefit", "Office", "Specialist", "Emergency", "Deductible",
                "Female", "Male", "Plan", "Group", "Policy"}
        for line in text.split('\n'):
            line = line.strip()
            if (re.match(r'^[A-Z][a-z]+(\s[A-Z][a-z]+){0,3}$', line)
                    and 3 < len(line) < 50):
                if not any(skip in line for skip in SKIP):
                    return self.clean_name(line)

        # Strategy 4: uppercase line fallback
        SKIP_UPPER = {"INSURANCE", "FORM", "PLAN", "DATE", "MEDICAL",
                      "PATIENT", "INFORMATION", "DEPENDENTS", "MEMBER",
                      "ENROLLED", "BLUECROSS", "BLUESHIELD"}
        for line in text.split('\n'):
            line = line.strip()
            if (line.isupper() and 3 < len(line) < 50
                    and not any(s in line for s in SKIP_UPPER)):
                return self.clean_name(line)

        return "Not Found"

    # ── Gender ────────────────────────────────────────────────────────────

    def extract_gender(self, text: str) -> str:
        """
        Priority:
        1. Checkbox symbol ☒/☑ directly adjacent to Male or Female
        2. Standalone MALE/FEMALE word (Aadhaar)
        3. Tamil script
        4. Explicit "Gender: X" label
        """
        filled = r'[\u2611\u2612]'
        empty  = '\u2610'

        for m in re.finditer(
                rf'({filled})\s*(Male|Female)|(Male|Female)\s*({filled})',
                text, re.IGNORECASE):
            word   = (m.group(2) or m.group(3) or "").strip()
            marker = (m.group(1) or m.group(4) or "").strip()
            if marker and empty not in marker:
                return word.capitalize()

        if re.search(r'\bFEMALE\b', text):
            return "Female"
        if re.search(r'\bMALE\b', text):
            return "Male"
        if 'பெண்' in text:
            return "Female"
        if 'ஆண்' in text:
            return "Male"

        m = re.search(r'Gender\s*[:\-]\s*(Male|Female)', text, re.IGNORECASE)
        if m:
            return m.group(1).capitalize()

        return "Not Found"

    # ── DOB ───────────────────────────────────────────────────────────────

    def extract_dob(self, text: str) -> str:
        """
        For forms and ID cards only — insurance card effective dates are NOT DOBs.
        Skip any date that follows 'Eff', 'Effective', or 'Policy' keywords.
        """
        # Remove lines containing effective/policy date keywords
        # so those dates are never captured as DOB
        clean = re.sub(
            r'(Eff\.?|Effective|Policy\s*Eff)[^\n]*', '', text, flags=re.IGNORECASE
        )

        # Format 1: standard DD/MM/YYYY
        m = re.search(r'\b(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})\b', clean)
        if m:
            dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
            if 1 <= int(dd) <= 31 and 1 <= int(mm) <= 12 and 1900 <= int(yyyy) <= 2025:
                return f"{dd}/{mm}/{yyyy}"

        # Format 2: digit-box grid after "Date Of Birth" label
        dob_section = re.search(
            r'Date\s+Of\s+Birth\s*[:\-]?\s*([\d\s]{8,30})',
            text, re.IGNORECASE
        )
        if dob_section:
            digits = re.findall(r'\d', dob_section.group(1))
            if len(digits) >= 8:
                dd   = digits[0] + digits[1]
                mm   = digits[2] + digits[3]
                yyyy = digits[4] + digits[5] + digits[6] + digits[7]
                if 1 <= int(dd) <= 31 and 1 <= int(mm) <= 12 and 1900 <= int(yyyy) <= 2025:
                    return f"{dd}/{mm}/{yyyy}"

        # Format 3: 8 spaced single digits
        m = re.search(
            r'\b(\d)\s+(\d)\s+(\d)\s+(\d)\s+(\d)\s+(\d)\s+(\d)\s+(\d)\b', clean
        )
        if m:
            d = [m.group(i) for i in range(1, 9)]
            dd, mm = d[0]+d[1], d[2]+d[3]
            yyyy = d[4]+d[5]+d[6]+d[7]
            if 1 <= int(dd) <= 31 and 1 <= int(mm) <= 12 and 1900 <= int(yyyy) <= 2025:
                return f"{dd}/{mm}/{yyyy}"

        return "Not Found"

    # ── Policy Number ─────────────────────────────────────────────────────

    def extract_policy_number(self, text: str) -> str:
        clean = re.sub(r'Contact\s*Number[^\n]*', '', text, flags=re.IGNORECASE)
        clean = re.sub(r'(Phone|Mobile|Tel)\s*[:\-]?[^\n]*', '', clean, flags=re.IGNORECASE)

        for pattern in [
            r'Member\s*ID\s*[:\n]\s*([A-Z0-9\-]{4,20})',
            r'Policy\s*Number\s*[:\-]?\s*([A-Z0-9\-]{4,20})',
            r'Policy\s*No\.?\s*[:\-]?\s*([A-Z0-9\-]{4,20})',
        ]:
            m = re.search(pattern, clean, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if val.upper() not in ("DATE", "DDMMYYYY", ""):
                    return val

        m = re.search(r'\b[A-Z]{2,5}\d{5,12}\b', clean)
        if m:
            return m.group()

        return "Not Found"

    # ── Claim Amount ──────────────────────────────────────────────────────

    def extract_claim_amount(self, text: str) -> str:
        m = re.search(
            r'Claim\s+Amount(?:\s+in\s+words)?\s*[:\-]?\s*([A-Za-z0-9,\s\.]+)',
            text, re.IGNORECASE
        )
        if m:
            raw = m.group(1).strip().split('\n')[0].strip()
            boilerplate = ["son", "daughter", "wife", "shri", "solemnly", "declare", "i,"]
            if (raw and len(raw) > 2
                    and raw.lower() not in ("not found", "")
                    and not any(b in raw.lower() for b in boilerplate)):
                return raw

        m = re.search(r'(?:Rs\.?|INR|₹)\s*([\d,]+(?:\.\d{2})?)', text, re.IGNORECASE)
        if m:
            return m.group(0).strip()

        return "Not Found"

    # ── Main entry point ──────────────────────────────────────────────────

    def extract_fields(self, ocr_text: str) -> dict:
        if not ocr_text or not ocr_text.strip():
            return {k: "Not Found" for k in
                    ["name", "gender", "dob", "policy_number", "claim_amount"]}
        return {
            "name":          self.extract_name(ocr_text),
            "gender":        self.extract_gender(ocr_text),
            "dob":           self.extract_dob(ocr_text),
            "policy_number": self.extract_policy_number(ocr_text),
            "claim_amount":  self.extract_claim_amount(ocr_text),
        }
