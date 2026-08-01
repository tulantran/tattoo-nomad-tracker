import os
import json
from openai import OpenAI
from dotenv import load_dotenv

# 1. Load your secret API key from the .env file
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 2. THE FAKE INSTAGRAM DATA
# Later, we will replace this with real data scraped from Instagram.
# For now, this simulates what an artist's profile looks like.
fake_instagram_data = [
    {
        "handle": "@dr.woo",
        "bio": "Studio @hollywood.tattoo",
        "recent_captions": [
            "Back in LA for the rest of the month. Link in bio for waitlist.",
            "Amazing time in London, thanks @sevendoorslondon!"
        ]
    },
    {
        "handle": "@sarah_gaiger",
        "bio": "Based in Bristol, UK",
        "recent_captions": [
            "BOOKING OPEN: I will be guesting at @redtowerstattoo in Portland, OR from Nov 15th to Nov 20th. Email bookings@sarahgaiger.com to secure a spot!",
            "Working on some fresh flora designs today."
        ]
    },
    {
        "handle": "@mystery_artist",
        "bio": "Tattooer.",
        "recent_captions": [
            "New flash available.",
            "Thanks for the good times."
        ]
    }
]

# 3. THE AI PROMPT
SYSTEM_PROMPT = """
You are an intelligence-gathering assistant for a tattoo artist. Your job is to analyze Instagram bios and recent post captions to determine current physical location and upcoming travel.

Context: Tattoo artists travel for 'guest spots'. Bios are often out of date. Prioritize recent post captions over the bio.

Task: Read the provided data and extract the following into a JSON array:
1. artist_handle
2. current_location (City, State/Country)
3. upcoming_guest_spots (City, State/Country)
4. guest_spot_dates (e.g., "Nov 15-20")
5. booking_status (e.g., "Open", "Waitlist", "Unknown")
6. contact_info
7. tracking_status ("TRACKED" if you found a location, "UNTRACKED" if no location is mentioned)

Rules:
- If a post announces a guest spot, put the location under 'upcoming_guest_spots'.
- If you cannot find a specific data point, output "Unknown".
- Output ONLY valid JSON. Do not include markdown formatting like ```json.
"""

# 4. RUN THE AI AGENT
def analyze_artists(artists_data):
    print("Sending data to the AI Agent...")
    
    response = client.chat.completions.create(
        model="gpt-4o-mini", 
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": str(artists_data)}
        ],
        response_format={"type": "json_object"} 
    )
    
    return response.choices[0].message.content

if __name__ == "__main__":
    print("🚀 Starting Tattoo Nomad Tracker...")
    result = analyze_artists(fake_instagram_data)
    
    # This makes the output print nicely on your screen
    parsed_json = json.loads(result)
    print("\n--- TRACKER RESULTS ---")
    print(json.dumps(parsed_json, indent=4))
