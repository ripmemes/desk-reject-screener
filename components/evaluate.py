import json
import urllib.request
from llm_client import ScreeningLLMClient
from config.paths import ProjectPaths
from config.misc import *
import os 

def get_openrouter_pricing(model_name: str) -> tuple[float, float]:
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/models")
        with urllib.request.urlopen(req, timeout=10) as response:
            models_data = json.loads(response.read().decode())
            for model in models_data.get("data", []):
                if model["id"] == model_name:
                    prompt_price = float(model["pricing"]["prompt"]) * 1_000_000
                    completion_price = float(model["pricing"]["completion"]) * 1_000_000
                    return prompt_price, completion_price
    except Exception as e:
        print(f"Warning: Could not fetch live pricing for '{model_name}' ({e}). Using fallback.")
    return 0.14, 0.28 

def calculate_metrics():
    paths = ProjectPaths()
    
    with open(paths.ground_truth_dataset, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
        
    client = ScreeningLLMClient()
    client.load_anchors(paths.anchor_dataset_json)
    
    step_metrics = {}
    for step in client.pipeline:
        step_name = step.__class__.__name__
        step_metrics[step_name] = {"TP": 0, "FP": 0, "TN": 0, "FN": 0, "total": 0 , "in_tokens": 0, "out_tokens": 0}

    TP, FP, TN, FN = 0, 0, 0, 0
    right_wrong_reason = 0
    total_evaluated_samples = 0
    error_log_stream = []

    # ---- exclude citations
    TP_no_cit, FP_no_cit, TN_no_cit, FN_no_cit = 0, 0, 0, 0
    right_wrong_reason_no_cit = 0
    total_eval_no_cit = 0
    # ----
    total_in = 0
    total_out = 0
    
    # ---- real time log 
    realtime_log_path = os.path.join(os.path.dirname(paths.ground_truth_dataset), "realtime_eval_log.txt")
    with open(realtime_log_path, "w", encoding="utf-8") as f:
        f.write("STARTING EVALUATION RUN...\n" + "="*50 + "\n")
    # ----
    # --- progress data
    progress_db_path = os.path.join(os.path.dirname(paths.ground_truth_dataset), "eval_progress_checkpoint.json")
    if os.path.exists(progress_db_path):
        with open(progress_db_path, "r", encoding="utf-8") as pf:
            cached_progress_runs = json.load(pf)
        print(f"Found active checkpoint! Resuming execution. ({len(cached_progress_runs)} papers already evaluated).")
    else:
        cached_progress_runs = {}

    # small_test = 2
    for key, data in dataset.items():
        # if total_evaluated_samples >= small_test :
        #     break
        try: 
            ground_truth = data.get("is_desk_reject")
            ground_truth_reason = data.get("rejection_category")
            forum_id = data.get("forum_id")
        
            status_folder = "desk-rejects" if ground_truth == 1 else "accepted"    
            file_path = paths.get_evaluation_pdf_path(forum_id, status_folder)
            if not os.path.exists(file_path) or forum_id in INVALID_ACCEPTED_PAPERS: 
                continue
            if forum_id in cached_progress_runs :
                result = cached_progress_runs[forum_id]
            else :
                print(f"\nEvaluating {forum_id}...")
                
                try: 
                    result = client.evaluate_paper(file_path)
                    cached_progress_runs[forum_id] = result
                    with open(progress_db_path, "w", encoding="utf-8") as pf:
                        json.dump(cached_progress_runs, pf, indent=4)
                except Exception as e:
                    print(f"  [!] API or processing error on {forum_id}: {e}. Skipping.")
                    continue

            if "usage" in result:
                total_in += result["usage"].get("input_tokens", 0)
                total_out += result["usage"].get("output_tokens", 0)

                if "step_usages" in result["usage"]:
                    for s_name, s_usage in result["usage"]["step_usages"].items():
                        if s_name in step_metrics:
                            step_metrics[s_name]["in_tokens"] += s_usage.get("input_tokens", 0)
                            step_metrics[s_name]["out_tokens"] += s_usage.get("output_tokens", 0)
                
            prediction = result["is_desk_reject"]
            prediction_reasons = result["rejection_category"]
            responsible_steps = result.get("responsible_steps", [])
            
            try:
                prediction = int(prediction)
            except ValueError:
                print(f"\n Output value for the prediction {prediction} is invalid")
                prediction = -1

            if ground_truth == 1 and prediction == 1 and ground_truth_reason in prediction_reasons:
                TP += 1
                
                for step_name in responsible_steps:
                    if step_name in step_metrics:
                        step_metrics[step_name]["TP"] += 1
                        step_metrics[step_name]["total"] += 1
                with open(realtime_log_path, "a", encoding="utf-8") as rlog:
                    rlog.write(f"Forum ID  : {forum_id}\n")
                    rlog.write(f"Truth     : {ground_truth} | Reason: {ground_truth_reason}\n")
                    rlog.write(f"TRUE POSITIVE ! Number of True Positives so far : {TP}\n")
                    rlog.write(f"LLM Output: {prediction} | Reason: {prediction_reasons} | Steps: {responsible_steps}\n")
                    rlog.write(f"   Model Justification: {result.get('detailed_justification', 'No justification provided.')}")
                    rlog.write("-" * 60 + "\n")
            elif ground_truth == 1 and prediction == 1 :
                right_wrong_reason += 1
                FN += 1
                
                for step_name in responsible_steps:
                    if step_name in step_metrics:
                        step_metrics[step_name]["FP"] += 1 # The isolated module falsely flagged a non-existent issue
                        step_metrics[step_name]["total"] += 1
                with open(realtime_log_path, "a", encoding="utf-8") as rlog:
                    rlog.write(f"Forum ID  : {forum_id}\n")
                    rlog.write(f"Truth     : {ground_truth} | Reason: {ground_truth_reason}\n")
                    rlog.write(f"FALSE NEGATIVE (Model failed to detect the true reason!)! Number of False Negatives so far : {FN}\n")
                    rlog.write(f"LLM Output: {prediction} | Reason: {prediction_reasons} | Steps: {responsible_steps}\n")
                    rlog.write(f"   Model Justification: {result.get('detailed_justification', 'No justification provided.')}")
                    rlog.write("-" * 60 + "\n")

            elif ground_truth == 0 and prediction == 1:
                FP += 1
                
                for step_name in responsible_steps:
                    if step_name in step_metrics:
                        step_metrics[step_name]["FP"] += 1
                        step_metrics[step_name]["total"] += 1
                with open(realtime_log_path, "a", encoding="utf-8") as rlog:
                    rlog.write(f"Forum ID  : {forum_id}\n")
                    rlog.write(f"Truth     : {ground_truth} | Reason: {ground_truth_reason}\n")
                    rlog.write(f"FALSE POSITIVE ! Number of False Positives so far : {FP}\n")
                    rlog.write(f"LLM Output: {prediction} | Reason: {prediction_reasons} | Steps: {responsible_steps}\n")
                    rlog.write(f"   Model Justification: {result.get('detailed_justification', 'No justification provided.')}")
                    rlog.write("-" * 60 + "\n")
                error_log_stream.append(
                    f"ERROR TYPE: False Positive (Clean paper flagged as reject)\n"
                    f"Forum ID: {forum_id}\n"
                    f"Steps Responsible: {', '.join(responsible_steps)}\n"
                    f"Assigned Category: {result.get('rejection_category', 'N/A')}\n"
                    f"Model Justification: {result.get('detailed_justification', 'No justification provided.')}\n"
                    f"{'-'*50}\n"
                )
            elif ground_truth == 0 and prediction == 0:
                TN += 1
                
                for step_name in step_metrics:
                    step_metrics[step_name]["TN"] += 1
                    step_metrics[step_name]["total"] += 1
                with open(realtime_log_path, "a", encoding="utf-8") as rlog:
                    rlog.write(f"Forum ID  : {forum_id}\n")
                    rlog.write(f"Truth     : {ground_truth} | Reason: {ground_truth_reason}\n")
                    rlog.write(f"TRUE NEGATIVE ! Number of True Negatives so far : {TN}\n")
                    rlog.write(f"LLM Output: {prediction} | Reason: {prediction_reasons} | Steps: {responsible_steps}\n")
                    rlog.write(f"   Model Justification: {result.get('detailed_justification', 'No justification provided.')}")
                    rlog.write("-" * 60 + "\n")
            elif ground_truth == 1 and prediction == 0:
                FN += 1
                
                for step_name in step_metrics:
                    step_metrics[step_name]["FN"] += 1
                    step_metrics[step_name]["total"] += 1
                with open(realtime_log_path, "a", encoding="utf-8") as rlog:
                    rlog.write(f"Forum ID  : {forum_id}\n")
                    rlog.write(f"Truth     : {ground_truth} | Reason: {ground_truth_reason}\n")
                    rlog.write(f"FALSE NEGATIVE ! Number of FALSE NEGATIVES so far : {FN}\n")
                    rlog.write(f"LLM Output: {prediction} | Reason: {prediction_reasons} | Steps: {responsible_steps}\n")
                    rlog.write(f"   Model Justification: {result.get('detailed_justification', 'No justification provided.')}")
                    rlog.write("-" * 60 + "\n")
                error_log_stream.append(
                    f"ERROR TYPE: False Negative (Violation completely missed)\n"
                    f"Forum ID: {forum_id}\n"
                    f"Ground Truth Category: {data.get('rejection_category', 'N/A')}\n"
                    f"Model Justification: Evaluated as compliant/passed checking gates.\n"
                    f"{'-'*50}\n"
                )
            else:
                with open(realtime_log_path, "a", encoding="utf-8") as rlog:
                    rlog.write(f"Forum ID  : {forum_id}\n")
                    rlog.write(f"Truth     : {ground_truth} | Reason: {ground_truth_reason}\n")
                    rlog.write(f"Invalid LLM Output")
                    rlog.write(f"LLM Output: {prediction} | Reason: {prediction_reasons} | Steps: {responsible_steps}\n")
                    rlog.write("-" * 60 + "\n")
                error_log_stream.append(
                    f"ERROR TYPE: Invalid LLM Output\n"
                    f"Forum ID: {forum_id}\n"
                    f"Raw Output: {prediction}\n"
                    f"{'-'*50}\n"
                )

            total_evaluated_samples = TP + FP + TN + FN
            # --- added calculations for no cit 
            is_citation_gt = (ground_truth_reason == "Hallucinated / Malformed Citations")
            reasons_no_cit = [r for r in prediction_reasons if r != "Hallucinated / Malformed Citations"]
            pred_no_cit = 1 if len(reasons_no_cit) > 0 else 0
            # ---
            if not is_citation_gt:
                total_eval_no_cit += 1
                if ground_truth == 1 and pred_no_cit == 1 and ground_truth_reason in reasons_no_cit:
                    TP_no_cit += 1
                elif ground_truth == 1 and pred_no_cit == 1 :
                    right_wrong_reason_no_cit += 1
                    FN_no_cit += 1
                elif ground_truth == 0 and pred_no_cit == 1:
                    FP_no_cit += 1
                elif ground_truth == 0 and pred_no_cit == 0:
                    TN_no_cit += 1
                elif ground_truth == 1 and pred_no_cit == 0:
                    FN_no_cit += 1

            
        except Exception as e:
            print(f"  [!] ERROR on {forum_id}: {e}. Continuing...")
            with open(realtime_log_path, "a", encoding="utf-8") as rlog:
                rlog.write(f"[!] SCRIPT ERROR CAUGHT ON {forum_id}: {e}\n" + "-"*60 + "\n")
            continue

    precision = TP / (TP + FP) if (TP + FP) > 0 else 0.0
    recall = TP / (TP + FN) if (TP + FN) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    accuracy = (TP + TN) / total_evaluated_samples if total_evaluated_samples > 0 else 0.0

    # --- added metrics for no cit 
    prec_no_cit = TP_no_cit / (TP_no_cit + FP_no_cit) if (TP_no_cit + FP_no_cit) > 0 else 0.0
    rec_no_cit = TP_no_cit / (TP_no_cit + FN_no_cit) if (TP_no_cit + FN_no_cit) > 0 else 0.0
    f1_no_cit = 2 * (prec_no_cit * rec_no_cit) / (prec_no_cit + rec_no_cit) if (prec_no_cit + rec_no_cit) > 0 else 0.0
    acc_no_cit = (TP_no_cit + TN_no_cit) / total_eval_no_cit if total_eval_no_cit > 0 else 0.0

    # ---
    
    print(f"\nFetching live pricing for model: {client.model_name}...")
    INPUT_PRICE_PER_1M_USD, OUTPUT_PRICE_PER_1M_USD = get_openrouter_pricing(client.model_name)
    print(f"\nThe price for {client.model_name} : input :{INPUT_PRICE_PER_1M_USD} , output : {OUTPUT_PRICE_PER_1M_USD} ")
    EUR_TO_USD = 1.05 

    
    total_cost_usd = (total_in / 1_000_000 * INPUT_PRICE_PER_1M_USD) + (total_out / 1_000_000 * OUTPUT_PRICE_PER_1M_USD)
    total_cost_eur = total_cost_usd / EUR_TO_USD
    tokens_per_euro = (total_in + total_out) / total_cost_eur if total_cost_eur > 0 else 0
    accuracy_per_euro = accuracy / total_cost_eur if total_cost_eur > 0 else 0.0
    
    print("\n" + "="*55)
    print("         PER-STEP PIPELINE METRICS")
    print("="*55)
    for step_name, metrics in step_metrics.items():
        s_tp, s_fp, s_tn, s_fn = metrics["TP"], metrics["FP"], metrics["TN"], metrics["FN"]

        s_in = metrics["in_tokens"]
        s_out = metrics["out_tokens"]
        s_cost_usd = (s_in / 1_000_000 * INPUT_PRICE_PER_1M_USD) + (s_out / 1_000_000 * OUTPUT_PRICE_PER_1M_USD)
        s_cost_eur = s_cost_usd / EUR_TO_USD


        s_prec = s_tp / (s_tp + s_fp) if (s_tp + s_fp) > 0 else 0.0
        s_rec = s_tp / (s_tp + s_fn) if (s_tp + s_fn) > 0 else 0.0
        s_f1 = 2 * (s_prec * s_rec) / (s_prec + s_rec) if (s_prec + s_rec) > 0 else 0.0
        print(f"Module: {step_name}")
        print(f"  Cost: €{s_cost_eur:.4f} (In: {s_in:,} | Out: {s_out:,})")
        print(f"  [TP: {s_tp} | FP: {s_fp} | TN: {s_tn} | FN: {s_fn}]")
        print(f"  Precision: {s_prec:.4f} | Recall: {s_rec:.4f} | F1: {s_f1:.4f}")
        print("-" * 55)

    print("\n" + "="*45)
    print("      AGGREGATED PIPELINE EVALUATION METRICS")
    print("="*45)
    print(f"Model Evaluated:      {client.model_name}")
    print(f"Prices Used (1M USD): In: ${INPUT_PRICE_PER_1M_USD:.4f} | Out: ${OUTPUT_PRICE_PER_1M_USD:.4f}")
    print("-" * 45)
    print(f"True Positives (TP):  {TP}")
    print(f"False Positives (FP): {FP}")
    print(f"True Negatives (TN):  {TN}")
    print(f"False Negatives (FN): {FN}")
    print(f"Right for Wrong Reason: {right_wrong_reason}")
    print("-" * 45)
    print(f"Precision: {precision:.4f}")
    print(f"Recall:    {recall:.4f}")
    print(f"F1 Score:  {f1:.4f}")
    print("-" * 45)
    print(f"Total Input Tokens:   {total_in:,}")
    print(f"Total Output Tokens:  {total_out:,}")
    print(f"Total Cost (EUR):    €{total_cost_eur:.4f}")
    print(f"Tokens per Euro:      {tokens_per_euro:,.0f}")
    print(f"Accuracy per Euro (Economic Density): {accuracy_per_euro:.4f}")

    # === ADDED: "No Citations" Metrics ==============================
    print("\n" + "="*45)
    print("      METRICS (EXCLUDING CITATION CHECK)")
    print("="*45)
    print(f"Total Evaluated:      {total_eval_no_cit}")
    print(f"True Positives (TP):  {TP_no_cit}")
    print(f"False Positives (FP): {FP_no_cit}")
    print(f"True Negatives (TN):  {TN_no_cit}")
    print(f"Right for Wrong Reason: {right_wrong_reason_no_cit}")
    print(f"False Negatives (FN): {FN_no_cit}")
    print("-" * 45)
    print(f"Precision: {prec_no_cit:.4f}")
    print(f"Recall:    {rec_no_cit:.4f}")
    print(f"F1 Score:  {f1_no_cit:.4f}")
    print(f"Accuracy:  {acc_no_cit:.4f}")
    # =================================================================
    
    final_error_report = "".join(error_log_stream) if error_log_stream else "No structural errors or classification discrepancies recorded during evaluation."
    final_error_report += f"\nTotal evaluated papers: {total_evaluated_samples}\n"

    print("\nCLASSIFICATION ERROR ENTRIES")
    print(final_error_report)
    print("="*45)

    log_output_path = os.path.join(os.path.dirname(paths.ground_truth_dataset), "evaluation_errors.log")
    with open(log_output_path, "w", encoding="utf-8") as log_file:
        log_file.write(final_error_report)
    print(f"Saved evaluation log to: {log_output_path}")

if __name__ == "__main__":
    calculate_metrics()