import json
from evaluators.base import EvaluationStep
from config.prompts import SYSTEM_PROMPTS
from preprocessing import extract_pdf_data

class AnonymityCheck(EvaluationStep):
    def run(self, pdf_path: str, client, model_name: str, anchor_data: dict) -> dict:
        target_image_b64 = self.get_page_as_base64_image(pdf_path, page_num=1)

        step_anchors = self.prepare_step_anchors(
            anchor_data=anchor_data, 
            target_categories=[
                "Anonymity Violation"
            ],
            requires_visuals=True
        )

        payload_content = [
            {
                "type": "text",
                "text": "[HISTORICAL ANCHOR CASES]:\n"
            }
        ]

        accepted_papers = [data for id, data in step_anchors.items() if data['is_desk_reject'] == 0]
        rejected_papers = [data for id, data in step_anchors.items() if data['is_desk_reject'] == 1]
        
        for i, reject_data in enumerate(rejected_papers):
            if i < len(accepted_papers):
                payload_content.append({
                    "type": "text",
                    "text": "=== ANCHOR CASE (VERDICT: 0) ===\nSTATUS: COMPLIANT\n"
                })
                if accepted_papers[i].get('text_fragment'):
                    payload_content.append({
                        "type": "text",
                        "text": f"FRAGMENT TEXT:\n{accepted_papers[i]['text_fragment']}\n"
                    })
                if "page_1" in accepted_papers[i].get('visual_anchors', {}):
                    payload_content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{accepted_papers[i]['visual_anchors']['page_1']}"}
                    })
            
            payload_content.append({
                "type": "text",
                "text": f"=== ANCHOR CASE (VERDICT: 1) ===\nREASON: {reject_data['rejection_category']}\n"
            })
            if reject_data.get('text_fragment'):
                payload_content.append({
                    "type": "text",
                    "text": f"FRAGMENT TEXT:\n{reject_data['text_fragment']}\n"
                })
            if "page_1" in reject_data.get('visual_anchors', {}):
                payload_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{reject_data['visual_anchors']['page_1']}"}
                })

        parsed_target_text, _ = extract_pdf_data(pdf_path)
        
        if not parsed_target_text and not target_image_b64:
            return {
                "is_desk_reject": 0,
                "rejection_category": None,
                "detailed_justification": f"AnonymityCheck failed to parse text layer or render page image for {pdf_path}."
            }
        
        payload_content.append({
            "type": "text",
            "text": f"=== TARGET PAPER LAYER TO AUDIT ===\n[TEXT LAYER]:\n{parsed_target_text or 'No raw text parsed.'}\n"
        })

        if target_image_b64:
            payload_content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{target_image_b64}"}
            })

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPTS['anonymity_compliance_system']},
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
                "detailed_justification": f"AnonymityCheck pipeline execution failed: {e}"
            }