import os
import json
from evaluators.base import EvaluationStep
from config.prompts import STEP_PROMPTS, SYSTEM_PROMPTS

from preprocessing import extract_pdf_data

class TextualCheck(EvaluationStep):
    def run(self, pdf_path: str, client, model_name: str, anchor_data_dict: dict) -> dict:
        text_context = anchor_data_dict.get("text_context", "")
        parsed_target_text, _ = extract_pdf_data(pdf_path)
        
        if not parsed_target_text:
            return {
                "is_desk_reject": 0,
                "rejection_category": None,
                "detailed_justification": f"TextualCheck failed to parse PDF text layer for {pdf_path}."
            }
        
        payload_content = (
            f"{STEP_PROMPTS['step_3_textual_integrity']}\n\n"
            f"[HISTORICAL ANCHOR CASES]:\n{text_context}\n\n"
            f"[TARGET PAPER LAYER TO AUDIT]:\n{parsed_target_text}"
        )

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPTS['general_system']},
                    {"role": "user", "content": payload_content}
                ],
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            result["usage"] = {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens
            }
            return result
        except Exception as e:
            return {
                "is_desk_reject": 0,
                "rejection_category": None,
                "detailed_justification": f"TextualCheck pipeline execution failed: {e}"
            }