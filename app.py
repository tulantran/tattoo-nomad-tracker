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

# # 3. THE "DEEP DIVE" EYES - Checking studio bios
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
    ACTOR_ID = "apify/instagram-profile-scraper"

    # Prepare the Actor input
    run_input = {
        "usernames": artist_usernames, # <--- REPLACE TARGET USERNAME
        "resultsLimit": 10,
    }

    print("Starting scraper... this might take a minute.")
    # Run the Actor
    run = apify_client.actor(ACTOR_ID).call(run_input=run_input)

    # Fetch the results
    dataset = apify_client.dataset(run["defaultDatasetId"])

    # Grab ALL the raw data and put it into a Python list
    all_raw_data = list(dataset.iterate_items())

    # # Create a file and dump the raw JSON data into it
    # filename = "raw_instagram_data.json"
    # with open(filename, "w", encoding="utf-8") as file:
    #     # indent=4 makes it readable, ensure_ascii=False keeps emojis intact
    #     json.dump(all_raw_data, file, indent=4, ensure_ascii=False)

    # print(f"\nDone! Saved {len(all_raw_data)} items to '{filename}'")

    return all_raw_data

# 5. THE UPGRADED AI BRAIN (With Hierarchy Instructions)
SYSTEM_PROMPT = """
You are an intelligence-gathering assistant for a tattoo artist. Your job is to analyze Instagram bios and recent post captions to determine current physical location and upcoming travel.

CRITICAL HIERARCHY FOR FINDING LOCATIONS:
1. Look for direct City/Country names in bio and captions. 
2. Look for Google Maps links or physical street addresses. Extract the City and Country.
3. If neither is found, look for @mentions of studios.

Task: Read the provided data and extract the following. You MUST be able to handle MULTIPLE guest spots.

Output a JSON object with an "artists" array containing:
1. artist_handle
2. locations (An ARRAY/LIST of objects. Format: [{"location": "City", "dates": "Aug 10-13"}]. Only record locations in future dates, no past dates. If they just say "City Month", put the month in the dates field. If none, empty array [].)
3. home_base (If you can find a home base city, put it here. Infer to your best ability which is the resident city. Otherwise "Unknown")
4. tracking_status ("TRACKED" if you found a location, "UNTRACKED" if completely unknown)
5. needs_deep_dive (Set to "TRUE" if tracking_status is UNTRACKED, but you see an "@username" in the bio. Otherwise "FALSE").


Rules:
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
        # Notice we changed this to 'locations' to match your new prompt!
        for spot in artist.get('locations', []):
            if spot.get('location') and spot['location'] != 'Unknown':
                unique_locations.add(spot['location'])
    
    if not unique_locations:
        return data # Nothing to clean

    # 2. Ask the AI to map messy names to standard "City, Country"
    cleaning_prompt = f"""
    You are a geography expert. Standardize this list of messy location names into a uniform "City, Country" format.
    Handle aliases (e.g., Saigon, HCMC, Ho Chi Minh all become "Ho Chi Minh City, Vietnam").
    If a US state is given (e.g., "Baltimore, MD"), format as "Baltimore, USA".
    If just a city is given (e.g., "Copenhagen"), add the country (e.g., "Copenhagen, Denmark").
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
        for spot in artist.get('locations', []):
            if spot.get('location') in mapping:
                spot['location'] = mapping[spot['location']]
                
    return data

import json

def extract_artist_info(data):
    """Extract bio, URLs, and captions (with locations) from multiple artist Instagram profiles."""
    
    # Handle both single artists and lists of artists
    artists = data if isinstance(data, list) else [data]
    extracted = []
    
    for artist in artists:
        artist_data = {
            "username": artist.get("username", ""),
            "display_name": artist.get("fullName", ""),
            "bio": artist.get("biography", ""),
            "urls": [
                {"title": u.get("title", ""), "url": u.get("url", "")}
                for u in artist.get("externalUrls", [])
            ],
            "posts": []
        }
        
        # Add primary URL if not already included
        primary = artist.get("externalUrl", "")
        if primary and not any(u["url"] == primary for u in artist_data["urls"]):
            artist_data["urls"].append({"title": "Primary Link", "url": primary})
        
        # Process posts
        for post in artist.get("latestPosts", []):
            post_data = {
                #"short_code": post.get("shortCode", ""),
                "caption": post.get("caption", ""),
                "timestamp": post.get("timestamp", ""),
                #"likes": post.get("likesCount", 0),
                #"comments": post.get("commentsCount", 0),
                # Location fields - ADDED
                "location": post.get("locationName", ""),
                #"location_id": post.get("locationId", "")
            }
            
            # Extract child captions from Sidecar posts
            if post.get("type") == "Sidecar":
                child_captions = [
                    c.get("caption", "")
                    for c in post.get("childPosts", [])
                    if c.get("caption", "")
                ]
                if child_captions:
                    post_data["child_captions"] = child_captions
            
            # Only keep posts with content
            if post_data["caption"] or post_data.get("child_captions"):
                artist_data["posts"].append(post_data)
        
        extracted.append(artist_data)
    
    return extracted

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

    filtered_data = extract_artist_info(raw_data)

    # Step B: First AI Pass
    ai_result = analyze_artists(filtered_data)
    
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
    