from dotenv import load_dotenv
import os
import openreview
import json
from enum import StrEnum
from config.misc import *
from preprocessing import categorize_rejection
from config.paths import ProjectPaths

class desk_rej_violations(StrEnum):
    OVER_LENGTH = "Over-length"
    FORMATTING = "Formatting"
    ANONYMITY_VIOLATION = "Anonymity Violation"
    HALLUCINATED_MALFORMED_CITATIONS = "Hallucinated / Malformed Citations"
    SCIENTIFIC_INTEGRITY = "Scientific Integrity"
    UNCLASSIFED = "Unclassified/Other"



# this code was partially generated with the assistance of GitHub Copilot and Google Gemini, and thoroughly reviewed and adjusted by the author.

def parse_existing_data(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    else:
        return {}
    
def download_pdf(client,note_forum, note_id ,target_dir : str):
    try :
        f = client.get_pdf(id=note_forum)
        file_path = f"{target_dir}/{note_forum}.pdf"
        os.makedirs(target_dir, exist_ok=True)
        with open(file_path,'wb') as op:
            op.write(f)
    except Exception as e:
        print(f"Failed to download paper {note_id}: {e}")

def json_dumps_custom(file,data):
    try :
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e :
        print(f"An error occurred in json_dumps_custom: {e}")

"""Runs the main ingestion component
Args:
    UNIQUE_FLAG : When set to 1, desk-rejects with unique reasons will be fetched
"""
def run_ingestion(UNIQUE_FLAG):
    paths = ProjectPaths()
    script_dir = os.path.dirname(__file__)
    dotenv_path = os.path.join(script_dir, '..', '.env')
    load_dotenv(dotenv_path)

    username = os.getenv("OPEN_REVIEW_USERNAME")
    pw = os.getenv("OPEN_REVIEW_PASSWORD")
    n = 4
    n_desk_rej = 15
    dp_arr = [0] * 6

    client = openreview.api.OpenReviewClient(
        baseurl='https://api2.openreview.net',
        username=username,
        password=pw
    )

    violation_to_idx = {violation: i for i, violation in enumerate(desk_rej_violations)}

    try:
        # INVITATIONS_FILE = "invitations.json"
        DESK_REJECTS_FILE = os.path.join(script_dir,"..", "data","raw","desk-rejects","desk_rejects1.json")
        ACCEPTED_PAPERS_FILE = os.path.join(script_dir,"..","data","raw","accepted", "accepted_papers1.json")

        # venue_ids = ['ICLR.cc/2026/Conference', 'ICLR.cc/2025/Conference', 'ICLR.cc/2024/Conference', 'ICLR.cc/2023/Conference']
        venue_id = 'ICLR.cc/2026/Conference' 
        # venue_id = 'ICLR.cc/2026/Conference'
        print(f"[DEBUG] Fetching venue group metadata for: {venue_id}")


        # for desk rejected papers
        venue_group = client.get_group(venue_id) # might remove
        desk_rejected_venue_id = venue_group.content.get('desk_rejected_venue_id', {}).get('value')

        if not desk_rejected_venue_id:
            desk_rejected_venue_id = f"{venue_id}/Desk_Rejected_Submission"

        desk_rejected_submissions = client.get_all_notes(content={'venueid': desk_rejected_venue_id})

        # for peer review rejected papers

        rejected_venue_id = f"{venue_id}/Rejected_Submission"
        print(f"[DEBUG] Requesting compliant papers from target: '{rejected_venue_id}'")

        peer_rejected_submissions = client.get_all_notes(content={'venueid': rejected_venue_id})
        print(f"[DEBUG] API Query completed. Total compliant papers found: {len(peer_rejected_submissions)}")


        # invitation_data = {}
        accepted_data = {}
        desk_rej_data = {}
        desk_rej_unique_dict = {violation: [] for violation in desk_rej_violations}

        # invitation_data = parse_existing_data(INVITATIONS_FILE)
        # accepted_data = parse_existing_data(ACCEPTED_PAPERS_FILE)
        # desk_rej_data = parse_existing_data(DESK_REJECTS_FILE)

        
        
        for (idx, note) in enumerate(desk_rejected_submissions):
            all_quotas_full = all(count >= n_desk_rej for count in dp_arr)
            if len(desk_rej_data) >= n or all_quotas_full:
                print(f"[DEBUG] Loop terminates at item index {idx}. Targets met, quitting loop...")
                break
            
                
            if note.forum in TARGET_DESK_REJECTS : 
                continue

            print(f"   [DEBUG] Fetching thread replies for Paper {note.number} (Forum ID: {note.forum})")
            all_replies = client.get_all_notes(forum=note.forum)

            comments = "No Comments"
            decision_note_ref = None

            for reply in all_replies:
                if reply.invitations and any('Desk_Rejection' in inv for inv in reply.invitations):
                    decision_note_ref = reply
                    comments = reply.content.get('desk_reject_comments', {}).get('value', 'No Comments')
                    break
            if comments == "No Comments":
                print(f"   [DEBUG] Warning: Desk_Rejection note field missing. Checking submission content field extensions.")
                comments = note.content.get('desk_reject_comments', {}).get('value', 'No Comments') # might remove
            
            raw_reason = categorize_rejection(comments.split('\n')[0].split(':')[0].strip())
            try:
                rej_reason = desk_rej_violations(raw_reason)
            except ValueError:
                rej_reason = desk_rej_violations.UNCLASSIFED

            arr_idx = violation_to_idx[rej_reason]
            
        
            dp_arr[arr_idx] += 1
            desk_rej_unique_dict[rej_reason].append(note.forum)

            print(f"   [DEBUG] SUCCESS: Logged Desk Reject Paper {note.forum} under '{rej_reason}'. (Quota: {dp_arr[arr_idx]}/{n_desk_rej})")

            reason_key = comments.split(':')[0].strip() if ':' in comments else comments.split('.')[0].strip() if UNIQUE_FLAG else comments
            
            obj = {
                'id': note.id,
                'title': note.content.get('title', {}).get('value', 'No Title'),
                'rejection_category' : raw_reason,
                'comments': comments,
                'forum_id': note.forum,
                'submission_id': note.id,
                'program_chairs': decision_note_ref.signatures if decision_note_ref else note.signatures,
                'readers': note.readers,
                'last_modified': note.tmdate,
                'created_date': note.cdate,
                'license': note.license if hasattr(note, 'license') else 'CC BY 4.0'
            }


            target_dir = os.path.join(script_dir, "..", "data", "raw", "desk-rejects")
            
            if UNIQUE_FLAG:
                if reason_key not in desk_rej_data:
                    desk_rej_data[reason_key] = obj
                    download_pdf(client, note.forum, note.id, target_dir)
            else:
                dict_key = f"{reason_key} ( id: {note.id} )"
                desk_rej_data[dict_key] = obj
                download_pdf(client, note.forum, note.id, target_dir)

        for idx, note in enumerate(peer_rejected_submissions):
            if note.forum not in EVALUATION_ACCEPTED_PAPERS :
                continue


            if len(accepted_data) >= n:
                print(f"[DEBUG] Control group processing terminated. Target quota of {n} papers met.")
                break

            if note.forum in INVALID_ACCEPTED_PAPERS or note.forum in TARGET_ACCEPTED_PAPERS:
                continue     
            

            print(f"   [DEBUG] SUCCESS: Logging control paper {note.forum} (Paper {note.number})")
            
            obj = {
                'id': note.id,
                'title': note.content.get('title', {}).get('value', 'No Title'),
                'decision': 'Reject',
                'comment': 'Passed compliance checking gates, rejected via peer review context.',
                'forum_id': note.forum,
                'submission_id': note.id,
                'program_chairs': note.signatures,
                'readers': note.readers,
                'last_modified': note.tmdate,
                'created_date': note.cdate,
                'license': note.license if hasattr(note, 'license') else 'CC BY 4.0'
            }
            
            accepted_data[note.forum] = obj
            download_pdf(client, note.forum, note.id, paths.raw_data_dir / "accepted")
            

        print("\n=================== RUN ANALYSIS DESK REJECTS ===================")
        print(f"[DEBUG] Total varied desk reject dataset entries gathered: {len(desk_rej_data)}")
        print("[DEBUG] Categorization Index Breakdown:")
        for violation in desk_rej_violations:
            idx = violation_to_idx[violation]
            print(f"  - {violation}: {dp_arr[idx]} papers saved")
        print("===================================================\n")

        json_dumps_custom(DESK_REJECTS_FILE, desk_rej_data)
        print("[DEBUG] Ingestion execution completed successfully.\n")

        print("\n=================== CONTROL GROUP ANALYSIS ===================")
        print(f"[DEBUG] Total peer review rejected dataset entries gathered: {len(accepted_data)}")
        print("===================================================\n")
        
        json_dumps_custom(ACCEPTED_PAPERS_FILE, accepted_data)
        print("[DEBUG] Entire accepted-only ingestion pipeline execution finished successfully.\n")

        print(desk_rej_unique_dict)
        # json_dumps_custom(INVITATIONS_FILE,invitation_data)
        print("Ingestion complete. Desk rejects and accepted papers data have been saved.\n")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    run_ingestion(UNIQUE_FLAG=0)