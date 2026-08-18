# import streamlit as st
# import json

# # This line magically imports the heavy lifting functions from your app.py file!
# from app import extract_artist_info, get_real_instagram_data, analyze_artists, standardize_locations

# # --- 1. PAGE SETUP ---
# st.set_page_config(page_title="Tattoo Nomad Tracker", page_icon="🌍", layout="wide")

# # --- 2. THE HEADER ---
# st.title("🌍 Tattoo Nomad Tracker")
# st.markdown("Track your favorite artists. Find out where they are tattooing right now.")

# # --- 3. THE INPUTS (The Sidebar) ---
# st.sidebar.header("🔍 Search Artists")
# user_input = st.sidebar.text_area("Enter Instagram usernames (no @ symbol, comma separated):", 
#                                   placeholder="e.g., rice_c00k, emoboobie, solarist.midopoke")

# # The big button
# track_button = st.sidebar.button("🚀 Track Artists")

# # --- 4. WHAT HAPPENS WHEN YOU CLICK THE BUTTON ---
# if track_button:
#     # Clean up the text input
#     usernames = [name.strip() for name in user_input.split(",") if name.strip()]
    
#     if not usernames:
#         st.warning("Please enter at least one username.")
#     else:
#         # This creates a beautiful loading animation so the user knows it's working!
#         with st.spinner(f"Agent is scouring Instagram for {len(usernames)} artists... This takes ~30-60 seconds per artist."):
#             try:
#                 # Step 1: Get the data from Apify
#                 raw_data = get_real_instagram_data(usernames)

#                 # Step 2: Extract artist info
#                 filtered_data = extract_artist_info(raw_data)

#                   # --- DEBUG MODE: SHOW RAW DATA ---
#                 # st.subheader("🐛 Debug Mode: What the AI sees")
#                 # st.write("Here is the exact text pulled from Instagram before the AI touches it:")
#                 # st.json(filtered_data)
#                 # -----------------------------------
                
#                 # Step 2: Run the AI extraction
#                 ai_result = analyze_artists(filtered_data)
                
#                 # Step 3: Clean the geography data
#                 final_data = standardize_locations(ai_result)
                
#                 # Show success!
#                 st.success("Tracking Complete! Agent found the following data:")
                
#                 # Display the final JSON beautifully on the website
#                 st.json(final_data)
                
#             except Exception as e:
#                 # If something breaks (like an API key error), show it here instead of crashing
#                 st.error(f"Oops! The agent ran into an error: {e}")



import streamlit as st
import json
import pandas as pd
import pydeck as pdk
from geopy.geocoders import Nominatim
from functools import lru_cache

# Import your heavy lifting functions
from app import extract_artist_info, filter_past_locations, get_real_instagram_data, analyze_artists, standardize_locations

# --- 1. MAGIC GEOCODER ---
# This turns "Copenhagen, Denmark" into GPS coordinates. 
# @lru_cache saves coordinates so we don't look up the same city twice.
geolocator = Nominatim(user_agent="tattoo_nomad_tracker")

@lru_cache(maxsize=100)
def get_coordinates(location_string):
    if not location_string or location_string == "Unknown":
        return None, None
    try:
        location = geolocator.geocode(location_string)
        if location:
            return location.latitude, location.longitude
    except:
        pass
    return None, None

# --- 2. PAGE SETUP ---
st.set_page_config(page_title="Tattoo Nomad Tracker", page_icon="🌍", layout="wide")

# --- 3. SESSION STATE ---
# This tells Streamlit to remember your data even when you click buttons
if 'final_data' not in st.session_state:
    st.session_state.final_data = None

# --- 4. THE HEADER ---
st.title("🌍 Tattoo Nomad Tracker")
st.markdown("Track your favorite artists. Find out where they are tattooing right now.")

# --- 5. THE INPUTS (The Sidebar) ---
with st.sidebar:
    st.header("🔍 Add Artists")
    user_input = st.text_area("Enter IG usernames (no @, comma separated):", 
                              placeholder="e.g., rice_c00k, emoboobie, solarist.midopoke")
    track_button = st.button("🚀 Track Artists")

# --- 6. WHAT HAPPENS WHEN YOU CLICK THE BUTTON ---
if track_button:
    usernames = [name.strip() for name in user_input.split(",") if name.strip()]
    if not usernames:
        st.warning("Please enter at least one username.")
    else:
        with st.spinner(f"Agent is scouring Instagram for {len(usernames)} artists..."):
            try:
                raw_data = get_real_instagram_data(usernames)
                filtered_data = extract_artist_info(raw_data)
                ai_result = analyze_artists(filtered_data)
                   # Step 2.5: POST-PROCESSING - Filter out past dates using strict Python logic
                ai_result = filter_past_locations(ai_result)
                
                # SAVE TO SESSION STATE
                st.session_state.final_data = standardize_locations(ai_result)
                st.success("Tracking Complete!")
                
            except Exception as e:
                st.error(f"Error: {e}")

# --- 7. THE MAP INTERFACE (Only shows if we have data) ---
if st.session_state.final_data:
    data = st.session_state.final_data['artists']
    
    # Prepare a list to hold our map pins
    map_data = []
    
    for artist in data:
        handle = artist.get('artist_handle', 'Unknown')
        status = artist.get('tracking_status', '')
        
        # Determine pin color based on how we found it
        if status == "TRACKED_VIA_STUDIO":
            color = [255, 200, 0, 200] # Yellow for guessed/inferred
        else:
            color = [0, 255, 100, 200] # Green for confirmed/direct
        
        # 1. Add Home Base Pin
        home = artist.get('home_base')
        if home and home != "Unknown":
            lat, lon = get_coordinates(home)
            if lat:
                map_data.append({
                    "handle": handle,
                    "coords": [lon, lat], # Note: Pydeck uses [Longitude, Latitude] order!
                    "type": "Home Base",
                    "dates": "Permanent",
                    "city_name": home,
                    "color": color
                })
        
        # 2. Add Guest Spot Pins
        for spot in artist.get('locations', []):
            loc = spot.get('location')
            dates = spot.get('dates', 'Unknown')
            if loc and loc != "Unknown":
                lat, lon = get_coordinates(loc)
                if lat:
                    map_data.append({
                        "handle": handle,
                        "coords": [lon, lat],
                        "type": "Guest Spot",
                        "dates": dates,
                    
                        "city_name": loc,
                        "color": color
                    })
    
    # If we successfully found coordinates, draw the map!
    if map_data:
        df = pd.DataFrame(map_data)
        
        # Create the Pydeck 3D Globe Layer
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position="coords",
            get_color="color",
            radiusMinPixels=4,  # Smallest the dot gets when fully zoomed in
            radiusMaxPixels=15, # Largest the dot gets when fully zoomed out
            pickable=True 
        )
        
        # Set up the globe view
        view_state = pdk.ViewState(
            latitude=20, 
            longitude=0, 
            zoom=0, # Zoom 0 shows the whole globe
            pitch=0
        )
        
        # Render the map!
        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            tooltip={
                "html": "<b>📍 {city_name}</b><br/>Artist: @{handle}<br/>Type: {type}<br/>Dates: {dates}",
                "style": {
                    "backgroundColor": "rgba(0, 0, 0, 0.8)", # Slightly transparent black
                    "color": "white",
                    "fontFamily": "Arial",
                    "padding": "10px",
                    "borderRadius": "5px"
                }
            }
        ))
        
        # Little legend at the bottom
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("🟢 **Direct Mention** (Caption/Bio)")
        with col2:
            st.markdown("🟡 **Inferred** (Via Studio Link)")
            
    else:
        st.info("Data found, but the AI couldn't resolve any of the locations to real cities on the map.")