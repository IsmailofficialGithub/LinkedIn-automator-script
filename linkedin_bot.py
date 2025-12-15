import os
import time
import random
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import csv
import urllib.parse
import pickle

# Load environment variables
load_dotenv()

class LinkedInBot:
    def __init__(self):
        self.email = os.getenv("LINKEDIN_EMAIL")
        self.password = os.getenv("LINKEDIN_PASSWORD")
        # Ensure message is handled even if not set in .env
        self.message_template = os.getenv("LINKEDIN_MESSAGE", "Hi {first_name}, I hope this finds you well.") 
        self.message_subject = os.getenv("LINKEDIN_SUBJECT", "Hello")
        self.env_search_url = os.getenv("LINKEDIN_SEARCH_URL")
        
        if not self.email or not self.password:
            raise ValueError("Please set LINKEDIN_EMAIL and LINKEDIN_PASSWORD in .env file")
        
        self.setup_driver()

    def setup_driver(self):
        chrome_options = Options()
        # chrome_options.add_argument("--headless") # Comment out to see the browser
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-notifications")
        
        # Use ChromeDriverManager to automatically handle the driver
        self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        self.wait = WebDriverWait(self.driver, 15)

    def random_sleep(self, min_seconds=2, max_seconds=5):
        time.sleep(random.uniform(min_seconds, max_seconds))

    def save_session(self, filename="cookies.pkl"):
        """Save cookies to a file"""
        pickle.dump(self.driver.get_cookies(), open(filename, "wb"))
        print("Session cookies saved.")

    def load_session(self, filename="cookies.pkl"):
        """Load cookies from a file"""
        if os.path.exists(filename):
            cookies = pickle.load(open(filename, "rb"))
            # We need to be on the domain to set cookies
            self.driver.get("https://www.linkedin.com")
            for cookie in cookies:
                # Filter out 'expiry' that is not a valid date format, which can cause issues
                if 'expiry' in cookie and not isinstance(cookie['expiry'], int):
                     del cookie['expiry']
                try:
                    self.driver.add_cookie(cookie)
                except Exception as e:
                    # Some cookies might fail if domain doesn't match exactly, ignore
                    pass
            print("Session cookies loaded.")
            self.driver.refresh()
            return True
        return False

    def login(self):
        print("Checking for existing session...")
        if self.load_session():
            self.random_sleep(2, 4)
            # Verify if we are actually logged in by checking for a known element like the home feed (or 'feed')
            if "feed" in self.driver.current_url or "global-nav" in self.driver.page_source:
                print("Restored session successfully.")
                return

        print("Logging in with credentials...")
        self.driver.get("https://www.linkedin.com/login")
        self.random_sleep()

        try:
            email_input = self.wait.until(EC.presence_of_element_located((By.ID, "username")))
            email_input.clear()
            email_input.send_keys(self.email)
            self.random_sleep(1, 2)

            password_input = self.driver.find_element(By.ID, "password")
            password_input.clear()
            password_input.send_keys(self.password)
            self.random_sleep(1, 2)

            password_input.send_keys(Keys.RETURN)
            
            # Wait for home page or verification
            self.wait.until(EC.presence_of_element_located((By.ID, "global-nav")))
            print("Login successful.")
            self.save_session()
        except Exception as e:
            print(f"Login might have failed or verify needed. Check browser. Error: {e}")
            input("Press Enter to continue if you handled captcha manually...")
            # Save session assuming user fixed it manually
            self.save_session()

    def scrape_profile(self, profile_url):
        print(f"Navigating to {profile_url} to scrape data...")
        self.driver.get(profile_url)
        self.random_sleep(3, 6)

        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        
        data = {}
        
        # Try to find name (This selector might change, using generic reliable ones)
        try:
            # New profile layout selector
            name_tag = soup.find("h1", {"class": "text-heading-xlarge"})
            if not name_tag:
                 # Fallback for older layouts
                 name_tag = soup.find("h1")

            data['name'] = name_tag.get_text(strip=True).split("\n")[0].strip() if name_tag else "Unknown"
        except:
            data['name'] = "Unknown"

        # headline
        try:
            # Look for div with text-body-medium class
            headline_tag = soup.find("div", {"class": "text-body-medium"})
            data['headline'] = headline_tag.get_text(strip=True) if headline_tag else "No Headline"
        except:
            data['headline'] = "No Headline"
            
        print(f"Scraped Data: {data}")
        return data

    def send_connection_request(self, profile_url, message_note=None):
        """
        Tries to connect. If message_note is provided, adds a note.
        """
        # Ensure we are on the page
        if self.driver.current_url != profile_url:
            self.driver.get(profile_url)
            self.random_sleep(3, 5)

        try:
            # Look for "Connect" button
            connect_button = None
            
            # 1. Try primary buttons
            buttons = self.driver.find_elements(By.XPATH, "//button[span[text()='Connect']]")
            if buttons:
                connect_button = buttons[0]
            else:
                # 2. Check "More" menu
                print("Connect button not found in primary actions, checking 'More' menu...")
                # Search for 'More actions' or similar accessibility label
                more_buttons = self.driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'More actions')]")
                if more_buttons:
                    more_buttons[0].click()
                    self.random_sleep(1, 2)
                    # Check the dropdown for the connect button
                    dropdown_connect = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'artdeco-dropdown')]//div[span[text()='Connect']]")
                    if dropdown_connect:
                        connect_button = dropdown_connect[0]
            
            if connect_button:
                connect_button.click()
                self.random_sleep(1, 2)
                
                # Wait for modal to appear
                modal_title = self.wait.until(EC.presence_of_element_located((By.XPATH, "//h2[contains(@class, 'artdeco-modal__header')]")))
                print(f"Modal opened: {modal_title.text}")

                # Check for "Add a note" button
                add_note_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[span[text()='Add a note']]")))
                
                if message_note:
                    print("Adding a note...")
                    add_note_button.click()
                    self.random_sleep(1, 2)
                    
                    # Target the custom message text area
                    text_area = self.driver.find_element(By.ID, "custom-message")
                    text_area.send_keys(message_note)
                    self.random_sleep(1, 2)
                    
                    # The Send button in the modal
                    send_button = self.driver.find_element(By.XPATH, "//button[span[text()='Send']]")
                    # send_button.click() # UI Only: Uncomment to actually send
                    print(f"Would have clicked 'Send' with note: {message_note}")
                    print("SECURITY: Not actually clicking send in demo mode. Uncomment line in code.")
                    # Close modal manually for demo (or click send)
                    self.driver.find_element(By.XPATH, "//button[contains(@class, 'artdeco-modal__dismiss')]").click()

                else:
                    # Send without note
                    send_button = self.driver.find_element(By.XPATH, "//button[span[text()='Send without a note']]")
                    # send_button.click()
                    print("Would have clicked 'Send without note'")
                
                return True
            else:
                print("Could not find Connect button. Already connected or button hidden?")
                return False

        except Exception as e:
            print(f"Error sending connection request: {e}")
            return False

    def send_message(self, profile_url, message):
        """
        Sends a message to an existing connection.
        """
        if self.driver.current_url != profile_url:
            self.driver.get(profile_url)
            self.random_sleep(3, 5)

        try:
            # Look for "Message" button
            message_button = self.driver.find_elements(By.XPATH, "//button[span[text()='Message']]")
            if message_button: # Usually primary action if connected
                message_button[0].click()
                self.random_sleep(2, 4)
                
                # Wait for the chat window's message box
                msg_box = self.wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='textbox' and @contenteditable='true']")))
                
                msg_box.click()
                msg_box.send_keys(message)
                self.random_sleep(1, 2)
                
                # Find the Send button in the chat overlay
                send_btn = self.driver.find_element(By.XPATH, "//button[text()='Send']")
                # send_btn.click() # UI Only
                print(f"Would have sent message: {message}")
                print("SECURITY: Not actually clicking send in demo mode.")
                
                # Close chat to clean up?
                try:
                    close_icon = self.driver.find_element(By.XPATH, "//button[contains(@class, 'msg-overlay-bubble-header__control--close-btn')]")
                    close_icon.click()
                except:
                    pass

                return True
            else:
                print("Message button not found.")
                return False
                
        except Exception as e:
            print(f"Error sending message: {e}")
            return False

    def send_premium_message(self, profile_url, message_body, subject=None):
        """
        Tries to send a direct message (Premium/InMail).
        Supports Standard LinkedIn and Sales Navigator.
        """
        if self.driver.current_url != profile_url:
            self.driver.get(profile_url)
            self.random_sleep(3, 5)

        try:
            is_sales_nav = "sales/people" in self.driver.current_url or "sales/profile" in self.driver.current_url

            message_button = None
            
            # --- Button Strategy 1: Text Match (Universal) ---
            # Search for any button containing "Message"
            buttons = self.driver.find_elements(By.XPATH, "//button[contains(., 'Message')]")
            for btn in buttons:
                if btn.is_displayed():
                    message_button = btn
                    break

            # --- Button Strategy 2: "More" Menu (Standard LinkedIn) ---
            if not message_button and not is_sales_nav:
                # Check inside More menu just in case
                more_bg = self.driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'More actions')]")
                if more_bg:
                    more_bg[0].click()
                    self.random_sleep(1, 2)
                    dropdown_msg = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'artdeco-dropdown')]//div[span[text()='Message']]")
                    if dropdown_msg:
                        message_button = dropdown_msg[0]

            if not message_button:
                print("No 'Message' button found on profile.")
                return False

            print("Clicking Message button...")
            message_button.click()
            self.random_sleep(3, 5)
            
            # 2. Check for Subject Line (InMail)
            try:
                # Wait for the modal/panel to appear, looking for subject input as indicator
                subject_input = self.wait.until(EC.presence_of_element_located((By.XPATH, "//input[@name='subject']")))
                if subject:
                    print(f"InMail detected. Setting subject: {subject}")
                    subject_input.clear()
                    subject_input.send_keys(subject)
                    self.random_sleep(1)
            except:
                 # Standard message/Sales Nav message does not always have a subject field
                 print("No subject input detected (might be a standard message or sales nav).")
                 pass

            # 3. Enter Message Body
            try:
                # Try contenteditable div first (Standard + some Sales Nav)
                msg_box = self.wait.until(EC.presence_of_element_located((By.XPATH, "//div[@role='textbox' and @contenteditable='true'] | //textarea[@name='message']")))

                # Clear and Send Keys
                if msg_box.tag_name == 'textarea':
                    msg_box.clear()
                    msg_box.send_keys(message_body)
                else: # contenteditable div
                    msg_box.click()
                    msg_box.send_keys(message_body)
                
                self.random_sleep(2, 3)

                # 4. click Send
                send_btns = self.driver.find_elements(By.XPATH, "//button[text()='Send' or span[text()='Send']]") # Handles both button types

                if send_btns and send_btns[0].is_enabled():
                    # send_btns[0].click() # Security: Commented out
                    print("Would have clicked Send (Premium Message).")
                else:
                    print("Send button disabled or not found?")
                
                # Cleanup: Close chat window/modal
                try:
                    # Try to find both chat bubble close and standard modal close
                    close_icon = self.driver.find_element(By.XPATH, "//button[contains(@class, 'msg-overlay-bubble-header__control--close-btn') or contains(@class, 'artdeco-modal__dismiss')]")
                    close_icon.click()
                except:
                    pass
                
                return True

            except Exception as e:
                print(f"Error interacting with message box: {e}")
                return False

        except Exception as e:
            print(f"Error in send_premium_message: {e}")
            return False

    def scrape_search_results(self, search_url, output_file="data.csv"):
        print(f"Starting scrape and outreach: {search_url}")
        self.driver.get(search_url)
        self.random_sleep(3, 5)

        is_sales_nav = "sales" in search_url
        if is_sales_nav:
            print("Sales Navigator detected.")
        else:
            print("Standard LinkedIn detected.")

        page_count = 0
        
        # Open file once outside the loop
        with open(output_file, mode='w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Name', 'Profile URL', 'Headline', 'Location', 'Status'])

            while True:
                page_count += 1
                print(f"\nProcessing page {page_count}...")
                
                # Scroll down to load all results
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                self.random_sleep(3, 5)

                profiles_on_page = []

                # --- Unified Scraping Logic ---
                print("Waiting for results to render (skipping skeletons)...")
                try:
                    # Wait for ACTUAL content to load, not just the container skeletons
                    # We wait for at least one profile link to appear
                    WebDriverWait(self.driver, 15).until(
                        lambda d: d.find_elements(By.XPATH, "//a[contains(@href, '/in/') and not(contains(@href, 'linkedin.com/in/'))]") or # Standard internal links
                                  d.find_elements(By.XPATH, "//a[contains(@href, '/sales/people')]") or # Sales Nav links
                                  d.find_elements(By.CSS_SELECTOR, "[data-view-name='search-result-lockup-title']") # New UI
                    )
                except Exception:
                    print("Timeout waiting for actual profile data. Proceeding with page source check...")

                # Re-parse page after wait
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                
                # Waterfall Strategy: Try most specific/modern structures first
                # 1. New UI / SDUI (Standard & Hybrid)
                results = soup.find_all("div", {"data-view-name": "people-search-result"})
                
                # 2. Classic Standard UI
                if not results:
                    results = soup.find_all("li", {"class": "reusable-search__result-container"})
                
                # 3. Classic Sales Navigator (using lambda to check class substring)
                if not results:
                    results = soup.find_all("li", {"class": lambda x: x and "artdeco-list__item" in x})
                
                # 4. Generic Fallback
                if not results:
                    results = soup.find_all("div", {"role": "listitem"})

                print(f"DEBUG: Scraped {len(results)} raw containers.")

                if not results:
                    print("No results found. Saving debug info...")
                    with open("debug_page_source.html", "w", encoding="utf-8") as debug_f:
                        debug_f.write(self.driver.page_source)
                    break # End loop if no results found

                for i, result in enumerate(results):
                    try:
                        print(f"--- Parsing Item {i+1} ---")
                        name = "Unknown"
                        profile_url = "N/A"
                        headline = "No Headline"
                        location = "No Location"
                        
                        # --- Name & URL Extraction ---
                        name_tag = None
                        
                        # Priority 1: New UI Title (Standard & Sales Nav Hybrid)
                        name_tag = result.find("a", {"data-view-name": "search-result-lockup-title"})
                        if name_tag: print("Found name via Priority 1 (search-result-lockup-title)")
                        
                        # Priority 2: Standard/Sales Name Link (app-aware-link)
                        if not name_tag:
                            # Search for the main profile link
                            all_links = result.find_all("a")
                            for link in all_links:
                                href = link.get("href", "")
                                text = link.get_text(strip=True)
                                # Heuristic: Name links are usually not empty and link to profile
                                if len(text) > 2 and ("/in/" in href or "/sales/people" in href):
                                    # Avoid buttons/images
                                    if "Connect" not in text and "Message" not in text:
                                        name_tag = link
                                        print(f"Found name via Priority 2 (Heuristic link): {text}")
                                        break
                        
                        # Debugging if no name found
                        if not name_tag:
                            print("FAILED to find name tag in this item.")
                            if i == 0:
                                with open("debug_extraction_fail.html", "w", encoding="utf-8") as f:
                                    f.write(result.prettify())
                                print("Saved failed item HTML to debug_extraction_fail.html")

                        if name_tag:
                            # Clean up name
                            name = name_tag.get_text(strip=True).split("\n")[0].strip() 
                            href = name_tag.get("href")
                            
                            if href.startswith("/"):
                                profile_url = f"https://www.linkedin.com{href.split('?')[0]}"
                            else:
                                profile_url = href.split('?')[0] if href else "N/A"
                            
                            # --- Headline & Location Extraction ---
                            try:
                                headline_tag = result.find("div", {"class": lambda x: x and ("entity-result__headline" in x or "search-result__snippet" in x)})
                                if not headline_tag:
                                     text_blocks = list(result.stripped_strings)
                                     if len(text_blocks) > 2:
                                         headline = text_blocks[2]
                                else:
                                    headline = headline_tag.get_text(strip=True)
                            except:
                                pass
                            
                            try:
                                location_tag = result.find("div", {"class": lambda x: x and "entity-result__secondary-subtitle" in x})
                                if not location_tag:
                                     text_blocks = list(result.stripped_strings)
                                     if len(text_blocks) > 3:
                                         location = text_blocks[3]
                                else:
                                    location = location_tag.get_text(strip=True)
                            except:
                                pass
                            
                            print(f"Extracted: {name} | {profile_url}")
                            if profile_url != "N/A":
                                profiles_on_page.append({
                                    "name": name,
                                    "url": profile_url,
                                    "headline": headline,
                                    "location": location
                                })
                    except Exception as e:
                        print(f"Error parsing item {i+1} on page {page_count}: {e}")


                print(f"Found {len(profiles_on_page)} profiles. Starting interaction...")

                # Process each profile
                for p in profiles_on_page:
                    status = "Skipped"
                    if p['url'] and p['url'] != "N/A":
                        # Open in new tab
                        self.driver.execute_script(f"window.open('{p['url']}', '_blank');")
                        self.driver.switch_to.window(self.driver.window_handles[-1])
                        self.random_sleep(3, 5)
                        
                        # Format message
                        msg = self.message_template
                        first_name = p['name'].split()[0] if p['name'] else "there"
                        msg = msg.format(first_name=first_name)
                        
                        print(f"visiting {p['name']}...")
                        
                        # Use updated sender which handles both Sales Nav and Standard
                        sent_msg = self.send_premium_message(p['url'], message_body=msg, subject=self.message_subject)
                        
                        if sent_msg:
                            status = "Premium Message Sent"
                        else:
                            # Fallback to connection request if message failed and profile URL suggests connection is possible
                            # Note: This is an advanced fallback. For simplicity and safety, we mark as failed.
                            status = "Message Failed / Connect Skipped"
                        
                        # Close current tab and switch back to search results
                        self.driver.close()
                        self.driver.switch_to.window(self.driver.window_handles[0])
                        self.random_sleep(1, 3)
                    
                    # Write result to CSV
                    writer.writerow([p['name'], p['url'], p['headline'], p['location'], status])
                    f.flush()
                
                # Check for Next Button
                try:
                    next_button = None
                    if is_sales_nav:
                        # Sales Nav next button often has class 'search-results__pagination-next-button'
                        pagination = self.driver.find_elements(By.XPATH, "//button[contains(@class, 'search-results__pagination-next-button')]")
                        if pagination: next_button = pagination[0]
                    else:
                        # Standard
                        # Note: Look for the button with aria-label='Next' for general navigation
                        next_button = self.driver.find_element(By.XPATH, "//button[@aria-label='Next']")

                    if next_button and next_button.is_enabled():
                        next_button.click()
                        self.random_sleep(3, 6)
                    else:
                        print("Reached last page.")
                        break
                except:
                    print("No 'Next' button found, ending scrape.")
                    break
        
        print(f"Batch complete. Data saved to {output_file}")


    def close(self):
        self.driver.quit()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="LinkedIn Automation Bot")
    parser.add_argument("--url", help="Target Profile URL or Search Results URL")
    parser.add_argument("--message", help="Connection Note / Initial Message")
    parser.add_argument("--followup", help="Follow-up Message (if already connected)")
    
    args = parser.parse_args()

    bot = LinkedInBot()
    try:
        bot.login()
        
        default_url = bot.env_search_url if bot.env_search_url else ""
        if default_url:
            print(f"Found LINKEDIN_SEARCH_URL in .env: {default_url}")

        if args.url:
            target_url = args.url
        elif default_url:
            use_env = input(f"Use Search URL from .env? (y/n) [y]: ").lower()
            if use_env == '' or use_env == 'y':
                target_url = default_url
            else:
                target_url = input("Enter the LinkedIn URL (Profile OR Search Results): ")
        else:
            target_url = input("Enter the LinkedIn URL (Profile OR Search Results): ")
        
        # Check if it is a Search URL or a Profile URL
        if "linkedin.com/search/results" in target_url or "linkedin.com/sales/search" in target_url:
            print("Detected Search URL. Switching to Search Scraping Mode.")
            bot.scrape_search_results(target_url, output_file="data.csv")
        else:
            # Assume it's a single profile interaction
            initial_message = args.message if args.message else input("Enter the connection note message: ")
            
            # Scrape
            data = bot.scrape_profile(target_url)
            
            # Connect
            connected = bot.send_connection_request(target_url, initial_message)
            
            if not connected:
                print("Could not connect (maybe already connected?). Attempting to send message directly...")
                followup = args.followup if args.followup else input("Enter follow-up message (or press Enter to skip): ")
                if followup:
                    bot.send_message(target_url, followup)
            
    except ValueError as e:
        print(f"Configuration Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        bot.close() # Now safely quitting the browser
        print("Done. Driver has been closed.")