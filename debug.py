import streamlit as st
import json
from datetime import datetime
# This line magically imports the heavy lifting functions from your app.py file!
from app import *
st.set_page_config(page_title="Tattoo Nomad Tracker", page_icon="🌍", layout="wide")

# --- 2. THE HEADER ---
st.title("🌍 Tattoo Nomad Tracker")
st.markdown("Track your favorite artists. Find out where they are tattooing right now.")

# --- 3. THE INPUTS (The Sidebar) ---
st.sidebar.header("🔍 Search Artists")
user_input = st.sidebar.text_area("Enter Instagram usernames (no @ symbol, comma separated):", 
                                  placeholder="e.g., rice_c00k, emoboobie, solarist.midopoke")

# The big button
track_button = st.sidebar.button("🚀 Track Artists")
TODAY_STR = datetime.now().strftime("%B %d, %Y")
# --- 4. WHAT HAPPENS WHEN YOU CLICK THE BUTTON ---
if track_button:
    # Clean up the text input
    usernames = [name.strip() for name in user_input.split(",") if name.strip()]
    
    if not usernames:
        st.warning("Please enter at least one username.")
    else:
        # This creates a beautiful loading animation so the user knows it's working!
        with st.spinner(f"Agent is scouring Instagram for {len(usernames)} artists... This takes ~30-60 seconds per artist.{TODAY_STR}"):
            try:
                # Step 1: Get the data from Apify
                raw_data = get_real_instagram_data(usernames)

                # Step 2: Extract artist info
                filtered_data = extract_artist_info(raw_data)

                  # --- DEBUG MODE: SHOW RAW DATA ---
                # st.subheader("🐛 Debug Mode: What the AI sees")
                # st.write("Here is the exact text pulled from Instagram before the AI touches it:")
                # st.json(filtered_data)
                # -----------------------------------
                
                # Step 2: Run the AI extraction
                ai_result = analyze_artists(filtered_data)


                 
                # Step 3: Clean the geography data
                final_data = filter_and_standardize_locations(ai_result)

                
                
                # Show success!
                st.success("Tracking Complete! Agent found the following data:")
                
                # Display the final JSON beautifully on the website
                st.json(final_data)
                
            except Exception as e:
                # If something breaks (like an API key error), show it here instead of crashing
                st.error(f"Oops! The agent ran into an error: {e}")
