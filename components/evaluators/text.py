import json
from evaluators.base import EvaluationStep
from config.prompts import STEP_PROMPTS
from preprocessing import extract_pdf_data

class TextualCheck(EvaluationStep):
    def run(self, pdf_path: str, client, model_name: str, anchor_context: str) -> dict:
        try:
            raw_text, _ = extract_pdf_data(pdf_path)
        except Exception as e:
            return {"is_desk_reject": 0, "rejection_category": "ERROR", "detailed_justification": f"Step 3 text parsing failed: {e}"}

        system_prompt = (
            "You are a strict automated security sub-module auditing the raw text layer of academic submissions.\n"
            "Evaluate anonymization, citations, and injections and return ONLY a valid JSON object matching this schema:\n\n"
            "{\n"
            "  \"is_desk_reject\": int (0 or 1),\n"
            "  \"rejection_category\": string or null (e.g., 'Anonymity_Violation', 'Malformed / Broken Bibliography', 'Scientific Integrity'),\n"
            "  \"detailed_justification\": string,\n"
            "  \"detected_external_links\": list of strings\n"
            "}\n\n"
            f"{anchor_context}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": STEP_PROMPTS["step_3_textual_integrity"]},
                {"type": "text", "text": f"--- START OF RAW PDF TEXT ---\n{raw_text}\n--- END OF RAW PDF TEXT ---"}
            ]}
        ]

        try:
            response = client.chat.completions.create(
                model=model_name, messages=messages, response_format={"type": "json_object"}, temperature=0.0
            )
            result = json.loads(response.choices[0].message.content)
            if response.usage:
                result["usage"] = {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens
                }
            return result
        except Exception as e:
            return {"is_desk_reject": 0, "rejection_category": None, "detailed_justification": f"Step 3 API execution error: {e}", "detected_external_links": [],"usage": {"input_tokens": 0, "output_tokens": 0}}