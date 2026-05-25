from dotenv import load_dotenv
import os
import openreview
import json

# this code was partially generated with the assistance of GitHub Copilot and Google Gemini

script_dir = os.path.dirname(__file__)

dotenv_path = os.path.join(script_dir, '..', '.env')

load_dotenv(dotenv_path)

username = os.getenv("OPEN_REVIEW_USERNAME")
pw = os.getenv("OPEN_REVIEW_PASSWORD")

client = openreview.api.OpenReviewClient(
    baseurl='https://api2.openreview.net',
    username='karim.keraani@tum.de',
    password=pw
)

try:

    all_venues_file = "venues.json"
    invitations_file = "invitations.json"
    desk_rejects_file = "desk_rejects.json"
    accepted_papers_file ="accepted_papers.json"
    

    

    all_venues = openreview.tools.get_all_venues(client)
    with open(all_venues_file, 'w', encoding='utf-8') as f:
        json.dump(all_venues, f, ensure_ascii=False, indent=4)


    venue_id = 'ICLR.cc/2026/Conference'
    
    invitations = client.get_invitations(
        prefix=venue_id,
        type='note'
    )

    invitation_data = []
    desk_reject_data = []
    decision_data = []
    unique_reasons = {}
    for (index, invitation) in enumerate(invitations):
        invitation_data.append({
            'id': invitation.id,
            'content': invitation.content,
            'signatures': invitation.signatures,
            'writers': invitation.writers,
            'readers': invitation.readers,
            'invitees': invitation.invitees
        })

        if invitation.id.endswith('/-/Desk_Rejection_Reversion'):
            new_id = invitation.id.replace('/-/Desk_Rejection_Reversion', '/-/Desk_Rejection')  
            desk_rejects = client.get_all_notes(invitation=new_id)

            for(index, desk_rej_note) in enumerate(desk_rejects):
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
                if reason_key not in unique_reasons and len(unique_reasons) < 10:
                    unique_reasons[reason_key] = obj
                desk_reject_data.append(obj)

        # elif invitation.id.endswith('/-/Public_Comment'):
        #     new_id = invitation.id.replace('/-/Public_Comment', '/-/Decision')  
        #     decision_notes = client.get_all_notes(invitation=new_id)
        #     for decision_note in decision_notes:
        #         if "accept" in decision_note.content['decision']['value'].lower():
        #             decision_data.append({
        #                 'id': decision_note.id,
        #                 'title': decision_note.content.get('title', {}).get('value', 'No Title'),
        #                 'decision': decision_note.content.get('decision', {}).get('value', 'No Decision'),
        #                 'comment': decision_note.content.get('comment', {}).get('value', 'No Comment'),
        #                 'forum_id': decision_note.forum,
        #                 'submission_id': decision_note.replyto,
        #                 'program_chairs': decision_note.signatures,
        #                 'readers': decision_note.readers,
        #                 'last_modified': decision_note.tmdate,
        #                 'created_date': decision_note.cdate,
        #                 'license': decision_note.license
        #             })
                
            

        


    with open(invitations_file, 'w', encoding='utf-8') as f:
        json.dump(invitation_data, f, ensure_ascii=False, indent=4)
    with open(desk_rejects_file, 'w', encoding='utf-8') as f:
        # json.dump(desk_reject_data, f, ensure_ascii=False, indent=4)
        json.dump(unique_reasons, f, ensure_ascii=False, indent=4)
    with open(accepted_papers_file, 'w', encoding='utf-8') as f:
        json.dump(decision_data, f, ensure_ascii=False, indent=4)



except Exception as e:
    print(f"An error occurred: {e}")