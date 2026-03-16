"""
Validation Agent
-----------------
Uses GPT-4o to validate the final merged record and return a
structured validation report.
"""

from openai import OpenAI


class ValidationAgent:

    def __init__(self):
        self.client = OpenAI()          # reads OPENAI_API_KEY from env
        self.model  = "gpt-4o"

    def validate(self, data: dict) -> str:
        """
        Validate the final merged record.
        Returns a short plain-text validation report.
        """
        prompt = f"""You are a medical insurance data validator.

Validate this extracted patient record and give a SHORT structured report.

Record:
{data}

Check and report on:
1. MISSING FIELDS — list any field that is "Not Found"
2. SUSPICIOUS VALUES — flag anything that looks wrong
   (e.g. policy_number that is a 10-digit phone number,
    DOB that seems impossible, name with OCR noise like "Ss")
3. CONFLICTS — if conflict_details is present, summarise it
4. OVERALL STATUS — PASS / WARN / FAIL with one-line reason

Keep the report under 150 words. Be direct and specific."""

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=400,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content.strip()
