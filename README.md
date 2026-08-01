# Traveling Tattooer Tracker
AI agent and scraper used to track which city a tattoo artist is; noting guesting schedules and resident cities. It scrapes Instagram profiles, extracts messy location data from bios, captions, and hidden links, and outputs a clean, standardized JSON object of where artists are currently tattooing and where they are guesting.

## The Problem
I travel to places and then only afterward remember/ see on instagram that my favorite tattoo artist lives there and I missed an opportunity and now what I must return before I die and thus inefficient traveling ugh.

The modern tattoo industry has evolved into a highly nomadic culture, where traveling for guest spots and pop-ups is the standard. However, the tools to track these artists haven't caught up. Artists scatter their changing locations across Instagram in a chaotic mix of formats, whether buried in an outdated text bio, hidden as a raw Google Maps link, casually dropped in a post caption, or the even bio of a different user linked somewhere. Because their schedules are a constantly moving target, manually piecing together where artists are tattooing on any given week is a near-impossible nightmare. This tool is built specifically to adapt to this new industry reality, automatically hunting down and standardizing that fragmented data.


##  The Solution
This Python script acts as an automated research assistant using **Prompt Chaining** and smart web logic:
1. **The Eyes:** Scrapes bios and the last 10 post captions via Apify.
2. **The Link Expander:** Detects short URLs (like g.co/maps/...), follows the redirects, and grabs the full Google Maps URL containing the actual city name.
3. **Agent 1 (Extractor):** Reads the text to find home bases, guest spots, and dates. If an artist is "UNTRACKED" but tags a studio (e.g., @studio_name), it triggers a Deep Dive.
4. **The Deep Dive:** Automatically scrapes the tagged studio's bio/links to deduce the artist's location.
5. **Agent 2 (Standardizer):** Takes the raw, messy AI output and standardizes all geography into a uniform City, Country format.

## Tech Stack
* **Language:** Python 3
* **AI Engine:** OpenAI API (gpt-4o-mini for fast, cost-effective parsing)
* **Scraping:** Apify Client (Instagram Profile Scraper)
* **Web Logic:** requests library for HTTP redirect following

##  Example Output
{
    "artists": [
        {
            "artist_handle": "@rice_c00k",
            "home_base": "Ho Chi Minh City, Vietnam",
            "current_location": "Ho Chi Minh City, Vietnam",
            "guest_spots": [
                {
                    "location": "Hanoi, Vietnam",
                    "dates": "Aug 10-13"
                }
            ],
            "tracking_status": "TRACKED"
        }
    ]
}

##  Setup & Installation

1. **Clone the repo:**
   git clone https://github.com/YOUR_USERNAME/tattoo-nomad-tracker.git
   cd tattoo-nomad-tracker

2. **Install dependencies:**
   pip3 install openai apify-client requests python-dotenv

3. **Configure Environment Variables:**
   Create a .env file in the root directory and add your keys:
   OPENAI_API_KEY=sk-your-openai-key-here
   APIFY_TOKEN=your-apify-token-here
   
   Note: You will need a paid OpenAI account (even $5 is plenty) to use the API.

4. **Run the Tracker:**
   Edit the artists_to_track list at the bottom of app.py with the usernames you want to find, then run:
   python3 app.py

## Future Roadmap
- [ ] **Streamlit Web UI:** Move out of the terminal and into a visual web interface.
- [ ] **Interactive Map:** Mapbox integration to plot artists on a global map with confidence pins.
- [ ] **Date Slider:** Filter the map by specific dates to see who is where and for how long.
- [ ] **Database Integration:** Push tracked data to Notion or Airtable for permanent record keeping.
