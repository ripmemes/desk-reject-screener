import json
from evaluators.base import EvaluationStep
from config.prompts import SYSTEM_PROMPTS

class VisualBoundaryCheck(EvaluationStep):
    def run(self, pdf_path: str, client, model_name: str, anchor_data_dict: dict) -> dict:
        target_page_9_b64 = self.get_page_as_base64_image(pdf_path, page_num=9)
        target_page_10_b64 = self.get_page_as_base64_image(pdf_path, page_num=10)

        step_anchors = self.prepare_step_anchors(
            anchor_data=anchor_data_dict, 
            target_categories=["Over-Length"],
            requires_visuals=True
        )

        payload_content = [
            {
                "type": "text",
                "text": "[CONTEXT BENCHMARKS]:\n"
            }
        ]

        accepted_papers = [data for id, data in step_anchors.items() if data['is_desk_reject'] == 0]
        rejected_papers = [data for id, data in step_anchors.items() if data['is_desk_reject'] == 1]

        #---- CAP
        accepted_papers = accepted_papers[:25]
        rejected_papers = rejected_papers[:25]

        #----

        
        num_accepted = len(accepted_papers)
        num_rejected = len(rejected_papers)
        max_len = max(num_accepted, num_rejected)

        # for i, reject_data in enumerate(rejected_papers):
        for i in range(max_len):
            if i < num_accepted:
                payload_content.append({
                    "type": "text",
                    "text": "=== ANCHOR CASE (VERDICT: 0) ===\nSTATUS: COMPLIANT\n"
                })
                if "page_9" in accepted_papers[i]['visual_anchors']:
                    payload_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{accepted_papers[i]['visual_anchors']['page_9']}"}
                    })
                if "page_10" in accepted_papers[i]['visual_anchors']:
                    payload_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{accepted_papers[i]['visual_anchors']['page_10']}"}
                    })
            if i < num_rejected:
                reject_data = rejected_papers[i]
                payload_content.append({
                    "type": "text",
                    "text": f"=== ANCHOR CASE (VERDICT: 1) ===\nREASON: {reject_data['rejection_category']}\n"
                })
                if "page_9" in reject_data['visual_anchors']:
                    payload_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{reject_data['visual_anchors']['page_9']}"}
                    })
                if "page_10" in reject_data['visual_anchors']:
                    payload_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{reject_data['visual_anchors']['page_10']}"}
                    })

        payload_content.append({
            "type": "text",
            "text": "=== TARGET PAPER TO EVALUATE ==="
        })
        if ( not target_page_10_b64 ) :
            return {
                "is_desk_reject": 0,
                "rejection_category": None,
                "detailed_justification": "Document Pages Number <= 9 Pages."
            }
        
        
        if target_page_9_b64:
            payload_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{target_page_9_b64}"}
            })
        if target_page_10_b64:
            payload_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{target_page_10_b64}"}
            })
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPTS['page_limit_system']},
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
                "detailed_justification": f"VisualBoundaryCheck pipeline execution failed: {e}"
            }