import json
from evaluators.base import EvaluationStep
from prompts import STEP_PROMPTS

class VisualBoundaryCheck(EvaluationStep):
    def run(self, pdf_path: str, client, model_name: str, anchor_context: str) -> dict:
        try:
            page_9_img = self.get_page_as_base64_image(pdf_path, 9)
            page_10_img = self.get_page_as_base64_image(pdf_path, 10)
        except IndexError:
            return {
                "is_desk_reject": 0, 
                "rejection_category": None, 
                "detailed_justification": "Paper has fewer than 9 pages. Main body spillover checks skipped."
            }
        except Exception as e:
            return {"is_desk_reject": 0, "rejection_category": "ERROR", "detailed_justification": f"Step 1 internal error: {e}"}

        system_prompt = (
            "You are a strict automated sub-module checking for academic paper page limit boundaries.\n"
            "Evaluate the provided visual assets and return ONLY a valid JSON object matching this schema:\n\n"
            "{\n"
            "  \"is_desk_reject\": int (0 or 1),\n"
            "  \"rejection_category\": \"Over-length\" or null,\n"
            "  \"detailed_justification\": string\n"
            "}\n\n"
            f"{anchor_context}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": [
                {"type": "text", "text": STEP_PROMPTS["step_1_visual_boundary"]},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{page_9_img}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{page_10_img}"}}
            ]}
        ]

        try:
            response = client.chat.completions.create(
                model=model_name, messages=messages, response_format={"type": "json_object"}, temperature=0.0
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"is_desk_reject": 0, "rejection_category": None, "detailed_justification": f"Step 1 API execution error: {e}"}