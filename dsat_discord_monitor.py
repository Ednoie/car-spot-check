import time
import re
import requests
from bs4 import BeautifulSoup, Comment
from config import CHECK_INTERVAL, DISCORD_WEBHOOK_URL, DISPLAY_NAME, LIVE_URL, UPTIME_KUMA_URL


was_available = False

def send_discord_notification(carpark_name, spots_available):
    """Sends a richly formatted message to your Discord channel via Webhook, dynamically styled based on availability."""
    
    # Dynamically change the look and feel depending on the spot count
    if spots_available > 0:
        title = "🚨 Parking Spot Available!"
        description = f"Good news! **{carpark_name}** has available spaces."
        color = 3066993  # Green accent color
        spots_value = f"**{spots_available}** spots left"
    else:
        title = "🛑 Car Park is Full!"
        description = f"Bad news... **{carpark_name}** is now completely full."
        color = 15158332  # Crimson Red accent color
        spots_value = "🔴 **0** spots left"

    payload = {
        "username": "DSAT Parking Bot",
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "fields": [
                    {
                        "name": "🚗 Light Vehicle Spots (輕型車輛)",
                        "value": spots_value,
                        "inline": True
                    },
                    {
                        "name": "🔗 Live Status",
                        "value": f"[Click here to view DSAT page]({LIVE_URL})",
                        "inline": True
                    }
                ],
                "footer": {
                    "text": "DSAT Real-time Monitor"
                },
                "timestamp": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            }
        ]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if response.status_code == 204:
            print(f"Discord notification sent successfully for {carpark_name}!")
        else:
            print(f"Failed to send Discord message. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error connecting to Discord: {e}")

def check_parking():
    """Scrapes DSAT standard HTML structure to pull car park status metrics."""
    global was_available
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(LIVE_URL, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"Failed to fetch data. HTTP Status: {response.status_code}")
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. Find the <div> that explicitly contains the car park display name
        name_div = soup.find('div', string=lambda text: text and DISPLAY_NAME in text)
        
        if not name_div:
            print(f"❌ Could not find car park with name: {DISPLAY_NAME}")
            return
            
        # 2. Get the parent row (<tr>) containing all the data for this car park
        target_row = name_div.find_parent('tr')
        if not target_row:
            print(f"❌ Could not isolate the table row for: {DISPLAY_NAME}")
            return
            
        # 3. Target the image corresponding to light vehicles (carpark_car.png)
        car_img = target_row.find('img', src=re.compile(r'carpark_car\.png'))
        if not car_img:
            print("❌ Could not locate the light vehicle data slot.")
            return
            
        # 4. Get the text sitting right next to the image inside its parent div
        # Using .get_text(strip=True) isolates the numerical digits
        car_div = car_img.parent
        spots_text = car_div.get_text(strip=True)
        
        try:
            spots_available = int(spots_text)
        except ValueError:
            print(f"⚠️ Spots content code is non-numeric or unavailable: '{spots_text}'")
            spots_available = 0

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {DISPLAY_NAME}: {spots_available} spots available.")

        currently_available = spots_available > 0

        # STATE CHANGE 1: It was full, but now a spot just opened up!
        if currently_available and not was_available:
            print(f"🎯 State Change! Spots found: {spots_available}. Dispatching alert.")
            send_discord_notification(DISPLAY_NAME, spots_available)
            was_available = True

        # STATE CHANGE 2: It had spots, but now it just filled up completely!
        elif not currently_available and carpark_was_available:
            print("🔴 State Change! Car park is now full.")
            send_discord_notification(DISPLAY_NAME, spots_available)
            was_available = False
                
    except Exception as e:
        print(f"An error occurred while monitoring: {e}")


if __name__ == "__main__":
    print(f"Starting Scraper for: {DISPLAY_NAME}...")
    
    if not UPTIME_KUMA_URL:
        print("⚠️ WARNING: UPTIME_KUMA_URL is not configured. External health monitoring is disabled.")
    else:
        print("ℹ️ External health monitoring enabled via Uptime Kuma.")

    while True:
        try:
            # 1. Run the primary scraper logic
            check_parking()
            
            # 2. Ping Uptime Kuma if configured
            if UPTIME_KUMA_URL:
                try:
                    requests.get(UPTIME_KUMA_URL, timeout=5)
                    print("💚 Health check ping sent to Uptime Kuma.")
                except requests.RequestException as e:
                    print(f"⚠️ Failed to ping Uptime Kuma: {e}")
                    
            # 3. Rest until the next interval cycle
            time.sleep(CHECK_INTERVAL)

        except KeyboardInterrupt:
            # This is intentional. The user wants to turn off the bot.
            print("\n🛑 Monitor stopped manually via user interrupt. Exiting gracefully...")
            break  # Breaks the 'while True' loop and exits cleanly
            
        except Exception as runtime_error:
            # This handles unexpected crashes (network down, site formatting changed, etc.)
            print(f"\n💥 CRITICAL RUNTIME ERROR: {runtime_error}")
            print("🔄 Attempting to recover... Retrying in 60 seconds.")
            
            # Optional: Send a quick SOS to your Discord so you know it's acting up
            # send_discord_notification(DISPLAY_NAME, "⚠️ Bot encountered an error but is retrying...")
            
            # Wait a buffer period before trying again so you don't spam requests in a broken state
            time.sleep(CHECK_INTERVAL)