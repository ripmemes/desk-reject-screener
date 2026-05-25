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

    

    all_venues = openreview.tools.get_all_venues(client)
    with open(all_venues_file, 'w', encoding='utf-8') as f:
        json.dump(all_venues, f, ensure_ascii=False, indent=4)


    venue_id = 'ICLR.cc/2026/Conference'
    
    invitations = client.get_invitations(
        prefix=venue_id,
        type='note'
    )

    data_to_save = []
    for (index, invitation) in enumerate(invitations):
        data_to_save.append({
            'id': invitation.id,
            'content': invitation.content,
            'signatures': invitation.signatures,
            'writers': invitation.writers,
            'readers': invitation.readers,
            'invitees': invitation.invitees
        })

    with open(invitations_file, 'w', encoding='utf-8') as f:
        json.dump(data_to_save, f, ensure_ascii=False, indent=4)


except Exception as e:
    print(f"An error occurred: {e}")