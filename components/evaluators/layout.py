import json
from evaluators.base import EvaluationStep
from prompts import STEP_PROMPTS

class LayoutCheck(EvaluationStep):
    def run(self, pdf_path: str, client, model_name: str, anchor_context: str) -> dict:
        try:
            random_page_img = self.get_page_as_base64_image(pdf_path, 4)    
        except IndexError:
            return {"is_desk_reject": 0, "rejection_category": None, "detailed_justification": "Page 4 does not exist to check layout constraints."}
        except Exception as e:
            return {"is_desk_reject": 0, "rejection_category": "ERROR", "detailed_justification": f"Step 2 internal error: {e}"}

        system_prompt = (
            "You are a strict automated sub-module checking for academic document layout and formatting consistency.\n"
            "Evaluate the page canvas layout and return ONLY a valid JSON object matching this schema:\n\n"
            "{\n"
            "  \"is_desk_reject\": int (0 or 1),\n"
            "  \"rejection_category\": \"Formatting\" or null,\n"
            "  \"detailed_justification\": string\n"
            "}\n\n"
            f"{anchor_context}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": STEP_PROMPTS["step_2_layout_compliance"]},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{random_page_img}"}}
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
            return {"is_desk_reject": 0, "rejection_category": None, "detailed_justification": f"Step 2 API execution error: {e}", "usage": {"input_tokens": 0, "output_tokens": 0}}