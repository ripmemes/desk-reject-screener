import os
import json
from evaluators.base import EvaluationStep
from config.prompts import STEP_PROMPTS, SYSTEM_PROMPTS

class LayoutCheck(EvaluationStep):
    def run(self, pdf_path: str, client, model_name: str, anchor_data_dict: dict) -> dict:
        target_image_b64 = self.get_page_as_base64_image(pdf_path, page_num=10)
        
        text_context = anchor_data_dict.get("text_context", "")
        visual_anchors = anchor_data_dict.get("visual_anchors", {})

        payload_content = [
            {
                "type": "text",
                "text": f"{STEP_PROMPTS['step_2_layout_compliance']}\n\n[CONTEXT BENCHMARKS]:\n{text_context}"
            }
        ]
        
        for anchor_id, data in visual_anchors.items():
            if "page_10" in data:
                verdict_label = "DESK REJECT VIOLATION" if data["is_desk_reject"] == 1 else "COMPLIANT"
                payload_content.append({
                    "type": "text",
                    "text": f"=== VISUAL BENCHMARK FOR ANCHOR {anchor_id} ({verdict_label}) ==="
                })
                payload_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{data['page_10']}"}
                })

        payload_content.append({
            "type": "text",
            "text": "=== TARGET PAPER TO EVALUATE ==="
        })
        payload_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{target_image_b64}"}
        })

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
                "detailed_justification": f"LayoutCheck pipeline execution failed: {e}"
            }