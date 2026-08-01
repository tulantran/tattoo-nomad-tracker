import os
import json
import re
import requests
from openai import OpenAI
from apify_client import ApifyClient
from dotenv import load_dotenv

# 1. Load your secret keys
load_dotenv()
openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
apify_client = ApifyClient(os.getenv("APIFY_TOKEN"))

# 2. NEW: THE URL EXPANDER (Follows short links to get the real URL)
def expand_urls_in_text(text):
    # Find anything that looks like a URL
    urls = re.findall(r'(https?://[^\s]+)', text)
    for url in urls:
        try:
            # We tell the request to NOT actually download the whole page, 
            # just follow the redirects and give us the final URL
            response = requests.head(url, allow_redirects=True, timeout=5)
            final_url = response.url
            # Replace the short URL in the text with the full URL
            text = text.replace(url, final_url)
        except:
            pass # If it fails, just leave the original link
    return text

# 3. THE "DEEP DIVE" EYES - Checking studio bios
def scrape_studio_bio(studio_username):
    print(f"🔍 Deep Dive: Checking @{studio_username}'s bio for a location...")
    run_input = {"usernames": [studio_username], "resultsLimit": 1}
    run = apify_client.actor("apify/instagram-profile-scraper").call(run_input=run_input)
    
    for item in apify_client.dataset(run["defaultDatasetId"]).iterate_items():
        raw_bio = item.get('biography', 'Unknown')
        link_in_bio = item.get('externalUrl', '') # GETTING THE LINK BUTTON
        
        combined_text = f"{raw_bio}\nPROFILE_LINK: {link_in_bio}"
        
        # EXPAND URLs IN THE STUDIO BIO TOO!
        return expand_urls_in_text(combined_text)
    return "Unknown"

# 4. THE MAIN EYES - Getting real data
def get_real_instagram_data(artist_usernames):
    print(f"🔍 Apify is scraping real data for: {artist_usernames}...")
    print("(This might take 30-60 seconds per artist, please be patient!)\n")
    
    run_input = {
        "usernames": artist_usernames,
        "resultsLimit": 10,
    }

    run = apify_client.actor("apify/instagram-profile-scraper").call(run_input=run_input)
    real_data = []
    
    for item in apify_client.dataset(run["defaultDatasetId"]).iterate_items():
        handle = item.get('username')
        
        if not any(d['handle'] == f"@{handle}" for d in real_data):
            raw_bio = item.get('biography', 'Unknown')
            # EXPAND URLs IN THE MAIN BIO
            expanded_bio = expand_urls_in_text(raw_bio)
            
            real_data.append({
                "handle": f"@{handle}",
                "bio": expanded_bio,
                "recent_captions": []
            })
        
        for artist in real_data:
            if artist['handle'] == f"@{handle}":
                caption = item.get('caption')
                if caption and len(artist['recent_captions']) < 10:
                    artist['recent_captions'].append(caption)

    return real_data

# 5. THE UPGRADED AI BRAIN (With Hierarchy Instructions)
SYSTEM_PROMPT = """
You are an intelligence-gathering assistant for a tattoo artist. Your job is to analyze Instagram bios and recent post captions to determine current physical location and upcoming travel.

CRITICAL HIERARCHY FOR FINDING LOCATIONS:
1. Look for direct City/Country names.
2. Look for Google Maps links (they will be expanded full URLs like google.com/maps/place/Austin,+TX) or physical street addresses. Extract the City and State/Country from these links/addresses.
3. If neither is found, look for @mentions of studios.

Task: Read the provided data and extract the following. You MUST be able to handle MULTIPLE guest spots.

Output a JSON object with an "artists" array containing:
1. artist_handle
2. home_base (Where they live/work permanently)
3. current_location (Where they are right now)
4. guest_spots (An ARRAY/LIST of objects. Format: [{"location": "City", "dates": "Aug 10-13"}]. If none, empty array [])
5. booking_status (e.g., "Open", "Waitlist", "Unknown")
6. contact_info
7. tracking_status ("TRACKED" if you found a location, "UNTRACKED" if completely unknown)
8. needs_deep_dive (Set to "TRUE" if tracking_status is UNTRACKED, but you see an "@username" in the bio. Otherwise "FALSE").

Rules:
- Extract ALL guest spots mentioned in the bio or captions.
- Output ONLY valid JSON.
"""

def analyze_artists(artists_data):
    print("🧠 Sending real data to the AI Agent...")
    
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini", 
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": str(artists_data)}
        ],
        response_format={"type": "json_object"} 
    )
    
    return json.loads(response.choices[0].message.content)

# 5.5 THE GEOGRAPHY CLEANER (Data Standardization)
def standardize_locations(data):
    print("🧹 Cleaning and standardizing location data...")
    
    # 1. Gather all unique messy locations from the data
    unique_locations = set()
    for artist in data['artists']:
        if artist.get('current_location') and artist['current_location'] != 'Unknown':
            unique_locations.add(artist['current_location'])
        if artist.get('home_base') and artist['home_base'] != 'Unknown':
            unique_locations.add(artist['home_base'])
        for spot in artist.get('guest_spots', []):
            if spot.get('location') and spot['location'] != 'Unknown':
                unique_locations.add(spot['location'])
    
    if not unique_locations:
        return data # Nothing to clean

    # 2. Ask the AI to map messy names to standard "City, Country"
    cleaning_prompt = f"""
    You are a geography expert. Standardize this list of messy location names into a uniform "City, Country" format.
    Handle aliases (e.g., Saigon, HCMC, Ho Chi Minh all become "Ho Chi Minh City, Vietnam").
    If a US state is given (e.g., "Baltimore, MD"), format as "Baltimore, USA".
    Return ONLY a JSON object mapping the old messy name to the new standard name.
    Locations to clean: {list(unique_locations)}
    """
    
    response = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": cleaning_prompt}],
        response_format={"type": "json_object"}
    )
    
    mapping = json.loads(response.choices[0].message.content)
    
    # 3. Apply the mapping back to our original data
    for artist in data['artists']:
        if artist.get('current_location') in mapping:
            artist['current_location'] = mapping[artist['current_location']]
        if artist.get('home_base') in mapping:
            artist['home_base'] = mapping[artist['home_base']]
        for spot in artist.get('guest_spots', []):
            if spot.get('location') in mapping:
                spot['location'] = mapping[spot['location']]
                
    return data

# 6. RUN THE APP
if __name__ == "__main__":
    artists_to_track = [
        "solarist.midopoke",
        "emoboobie",
        "rice_c00k"
    ]
    
    print("🚀 Starting Tattoo Nomad Tracker (LIVE VERSION - V3)...")
    
    # Step A: Get the real data (URLs are automatically expanded here)
    raw_data = get_real_instagram_data(artists_to_track)
    
    # Step B: First AI Pass
    ai_result = analyze_artists(raw_data)
    
    # Step C: Handle the "Deep Dive" for untracked artists
    for artist in ai_result['artists']:
        if artist['tracking_status'] == 'UNTRACKED' and artist.get('needs_deep_dive') == 'TRUE':
            print(f"\n🚨 @{artist['artist_handle'].replace('@','')} is untracked. Checking tagged studio...")
            
            original_bio = next((a['bio'] for a in raw_data if a['handle'] == artist['artist_handle']), "")
            mentions = re.findall(r'@([a-zA-Z0-9_.]+)', original_bio)
            
            if mentions:
                studio_to_check = mentions[0] 
                # Studio bio is ALREADY expanded by the scrape_studio_bio function
                studio_bio = scrape_studio_bio(studio_to_check)
                
                print(f"📝 Studio bio fetched (URLs expanded): {studio_bio}")
                
                deep_dive_prompt = f"""
                The artist {artist['artist_handle']} was untracked. 
                Their bio was: {original_bio}
                We looked up the studio they tagged (@{studio_to_check}) and their bio is: {studio_bio}
                
                Look at the studio bio. Is there a city name, physical address, or a Google Maps link containing a city? 
                Reply with ONLY a JSON object with the key 'deduced_location'. 
                If you still can't tell, set it to 'Unknown'.
                """
                
                deep_response = openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": deep_dive_prompt}],
                    response_format={"type": "json_object"}
                )
                
                deduced = json.loads(deep_response.choices[0].message.content)['deduced_location']
                
                if deduced != 'Unknown':
                    print(f"✅ Success! Deduced location from studio maps/link is: {deduced}")
                    artist['current_location'] = deduced
                    artist['tracking_status'] = 'TRACKED_VIA_STUDIO'
                else:
                    print(f"❌ Couldn't find location in studio bio either.")
                
        # Clean up the temporary key
        if 'needs_deep_dive' in artist:
            del artist['needs_deep_dive']

    # Step D: Clean the data
    ai_result = standardize_locations(ai_result)

    print("\n--- FINAL AI TRACKER RESULTS ---")
    print(json.dumps(ai_result, indent=4))

    print("\n--- FINAL AI TRACKER RESULTS ---")
    print(json.dumps(ai_result, indent=4))