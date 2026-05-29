from dotenv import load_dotenv
import os
import openreview
import json

# this code was partially generated with the assistance of GitHub Copilot and Google Gemini, and thoroughly reviewed by me

def parse_existing_data(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    else:
        return {}
    
def download_pdf(client,note,target_dir):
    try :
        f = client.get_pdf(id=note.forum)
        file_path = f"{target_dir}/{note.forum}.pdf"
        os.makedirs(target_dir, exist_ok=True)
        with open(file_path,'wb') as op:
            op.write(f)
    except Exception as e:
        print(f"Failed to download paper {note.id}: {e}")

def json_dumps_custom(file,data):
    try :
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e :
        print(f"An error occurred in json_dumps_custom: {e}")


def run_ingestion():
    script_dir = os.path.dirname(__file__)

    dotenv_path = os.path.join(script_dir, '..', '.env')

    load_dotenv(dotenv_path)

    username = os.getenv("OPEN_REVIEW_USERNAME")
    pw = os.getenv("OPEN_REVIEW_PASSWORD")

    client = openreview.api.OpenReviewClient(
        baseurl='https://api2.openreview.net',
        username=username,
        password=pw
    )

    try:
        ALL_VENUES_FILE = "venues.json"
        INVITATIONS_FILE = "invitations.json"
        DESK_REJECTS_FILE = os.path.join(script_dir,"..", "data","raw","desk-rejects","desk_rejects.json")
        ACCEPTED_PAPERS_FILE = os.path.join(script_dir,"..","data","raw","accepted", "accepted_papers.json")
        all_venues = openreview.tools.get_all_venues(client)
        with open(ALL_VENUES_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_venues, f, ensure_ascii=False, indent=4)


        venue_id = 'ICLR.cc/2026/Conference'
        
        invitations = client.get_invitations(
            prefix=venue_id,
            type='note'
        )

        invitation_data = parse_existing_data(INVITATIONS_FILE)
        accepted_data = parse_existing_data(ACCEPTED_PAPERS_FILE)
        unique_reasons = parse_existing_data(DESK_REJECTS_FILE)
        for (index, invitation) in enumerate(invitations):
            if len(unique_reasons) >= 10 and len(accepted_data) >= 10 :
                break


            invitation_data[invitation.id] = {
                'id': invitation.id,
                'content': invitation.content,
                'signatures': invitation.signatures,
                'writers': invitation.writers,
                'readers': invitation.readers,
                'invitees': invitation.invitees
            }
            

            if invitation.id.endswith('/-/Desk_Rejection_Reversion') :
                new_id = invitation.id.replace('/-/Desk_Rejection_Reversion', '/-/Desk_Rejection')  
                desk_rejects = client.get_all_notes(invitation=new_id)

                # for(_, desk_rej_note) in enumerate(desk_rejects):
                for desk_rej_note in desk_rejects :
                    if len(unique_reasons) >= 10 :
                        break
                    comments = desk_rej_note.content.get('desk_reject_comments', {}).get('value', 'No Comments')
                    reason_key = comments.split(':')[0].strip() if ':' in comments else comments.split('.')[0].strip()
                    obj ={
                        'id': desk_rej_note.id,
                        'title': desk_rej_note.content.get('title', {}).get('value', 'No Title'),
                        'comments': comments,
                        'forum_id': desk_rej_note.forum,
                        'submission_id': desk_rej_note.replyto,
                        'program_chairs': desk_rej_note.signatures,
                        'readers': desk_rej_note.readers,
                        'last_modified': desk_rej_note.tmdate,
                        'created_date': desk_rej_note.cdate,
                        'license': desk_rej_note.license
                    }
                    if reason_key not in unique_reasons :
                        unique_reasons[reason_key] = obj

                        target_dir = os.path.join(script_dir, "..", "data", "raw", "desk-rejects")
                        download_pdf(client, desk_rej_note,target_dir)

            elif invitation.id.endswith('/-/Public_Comment'):
                new_id = invitation.id.replace('/-/Public_Comment', '/-/Decision')  
                decision_notes = client.get_all_notes(invitation=new_id)
                for decision_note in decision_notes:
                    if len(accepted_data) >= 10 :
                        break
                    if "accept" in decision_note.content['decision']['value'].lower():
                        obj = {
                            'id': decision_note.id,
                            'title': decision_note.content.get('title', {}).get('value', 'No Title'),
                            'decision': decision_note.content.get('decision', {}).get('value', 'No Decision'),
                            'comment': decision_note.content.get('comment', {}).get('value', 'No Comment'),
                            'forum_id': decision_note.forum,
                            'submission_id': decision_note.replyto,
                            'program_chairs': decision_note.signatures,
                            'readers': decision_note.readers,
                            'last_modified': decision_note.tmdate,
                            'created_date': decision_note.cdate,
                            'license': decision_note.license
                        }
                        accepted_data[decision_note.id] = obj
                        target_dir = os.path.join(script_dir, "..", "data", "raw", "accepted")
                        download_pdf(client,decision_note,target_dir)


        json_dumps_custom(INVITATIONS_FILE,invitation_data)
        json_dumps_custom(DESK_REJECTS_FILE,unique_reasons)
        json_dumps_custom(ACCEPTED_PAPERS_FILE,accepted_data,)

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    run_ingestion()