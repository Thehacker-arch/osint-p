import json
import requests
from requests.exceptions import JSONDecodeError
from playwright.sync_api import sync_playwright # type: ignore
import re
from urllib.parse import urlparse

class SocialMediaCollector:
    def __init__(self):
        pass

    def resolve_person_id(self, username, github=None, insta=None, twitter=None, links=None):
        if github and github.get("username"):
            return f"github: {github.get('username')}"
        
        if insta and insta["username"]:
            return f"instagram: {insta['username']}"
        
        if twitter and twitter.get("username"):
            return f"twitter: {twitter.get('username')}"
        
        if links:
            for link in links:
                if "linkedin.com" in link:
                    return f"linkedin: {self.normalize_links(link)}"
        
        return f"username: {username}"

    def extract_links(self, text):
        if not text:
            return []
        return re.findall(r'(https?://[^\s]+)', text)
    
    def clean_int(val):
        if not val: return 0
        if isinstance(val, int): return val
        # Remove commas, dots, and whitespace
        cleaned = str(val).replace(',', '').replace('.', '').strip()
        return int(cleaned) if cleaned.isdigit() else 0
    
    def normalize_links(self, url: str) -> str:
        if not url:
            return ""
        url = url.strip().lower()

        if url.startswith("//"):
            url = "https:" + url
        elif not url.startswith("http"):
            url = "https://" + url
        
        parsed = urlparse(url)
        if not parsed.netloc or parsed.netloc == "":
            return ""
        
        clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

        # clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.parsed_path if hasattr(parsed, 'parsed_path') else parsed.path}"
        clean_url = clean_url.replace("www.", "")
        clean_url = clean_url.rstrip("/")

        if "linkedin.com" in clean_url:
            clean_url = clean_url.replace("/pub/", "/in/").replace("/profile/view?id=", "/in/")
        
        return clean_url

    def scrape_github_profile(self, username):
        links = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            try:
                page.goto(f"https://github.com/{username}", wait_until="networkidle")
                # page.wait_for_selector(".vcard-details")

                anchors = page.locator(".vcard-details a[href]").all()

                for a in anchors:
                    href = a.get_attribute("href")
                    if href and any(x in href for x in ["linkedin.com", "twitter.com", "http", "github.com"]):
                        links.append(self.normalize_links(href))
                    elif href.startswith('http') and "github.com" not in href:
                        links.append(self.normalize_links(href))
                        
            except Exception as e:
                print(f"Error scraping GitHub profile: {e}")

            finally:
                browser.close()

        print(f"Scraped GitHub profile for {username} and extracted links: {links}")
        return links

    def fetch_github(self, username):
        url = f"https://api.github.com/users/{username}".lower()
        res = requests.get(url)

        if res.status_code != 200:
            return None

        data = res.json()

        return {
            "platform": "github",
            "username": data.get("login"),
            "name": data.get("name"),
            "bio": data.get("bio"),
            "followers": data.get("followers"),
            "following": data.get("following"),
            "posts": data.get("public_repos"),
            "links": []

        }
    """
        a= list(filter(None, [
                data.get("blog"),
                f"https://twitter.com/{data.get('twitter_username')}" if data.get("twitter_username") else None
            ]))
    """
    
    def get_full_profile(self, username):
        data = self.fetch_github(username)
        if data:
            scraped_links = self.scrape_github_profile(username)
            data["links"] = list(set(data["links"] + scraped_links))
        return data

    def parse_instagram_bio(self, bio: str):
        pattern2 = r"([\d,]+)\s+Followers,\s+([\d,]+)\s+Following,\s+([\d,]+)\s+Posts\s+-\s+(.+?)\s+\(@(.+?)\)\s+on\s+Instagram:\s+\"([\s\S]+)\""
        match = re.search(pattern2, bio)   

        clean_int = lambda x: int(x.replace(',', ''))

        if match:
            description = match.group(6).strip() if match.group(6) else ""
            links_in_bio = self.extract_links(description)
            return {
            "followers": clean_int(match.group(1)),
            "following": clean_int(match.group(2)),
            "posts": clean_int(match.group(3)),
            "name": match.group(4),
            "username": match.group(5),
            "description": description,
            "platform": "instagram",
            "links": links_in_bio
        }
        
        pattern = r"([\d,]+)\s+Followers,\s+([\d,]+)\s+Following,\s+([\d,]+)\s+Posts\s+-\s+(.+?)\s+\(@(.+?)\)"
        match = re.search(pattern, bio)
        
        if match:
            return {
                "followers": clean_int(match.group(1)),
                "following": clean_int(match.group(2)),
                "posts": clean_int(match.group(3)),
                "name": match.group(4),
                "username": match.group(5),
                "description": "",
                "platform": "instagram",
                "links": []
            }
        
        pattern_no_name = r"([\d,]+)\s+Followers,\s+([\d,]+)\s+Following,\s+([\d,]+)\s+Posts\s+-\s+@(.+?)\s+on\s+Instagram"
        match = re.search(pattern_no_name, bio)
        
        if match:
            return {
                "followers": clean_int(match.group(1)),
                "following": clean_int(match.group(2)),
                "posts": clean_int(match.group(3)),
                "name": None,
                "username": match.group(4).strip(),
                "description": "",
                "platform": "instagram",
                "links": []
            }

        return None

    def fetch_instagram(self, username):
        with sync_playwright() as p:   
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            try:
                page.goto(f"https://www.instagram.com/{username}/", wait_until="networkidle")

                # page.wait_for_selector("body")
                locator = page.locator("meta[name='description']")
                if locator.count() > 0:
                    bio = locator.get_attribute("content")
                else:
                    print("Instagram bio meta tag not found")
                    bio = None
            except Exception as e:
                print(f"Error fetching Instagram profile: {e}")
                bio = None
            
            finally:
                browser.close()
            
            print(f"Scraped Instagram bio for {username}: {bio}")
            return bio
        


    def expand_url(self, url):
        if "t.co" in url:
            try:
                # allow_redirects=True will give us the final Vercel destination
                response = requests.head(url, allow_redirects=True, timeout=5)
                return response.url
            except Exception:
                return url
        return url
    

    def fetch_twitter(self, username):
        def parse_count(text):
            if not text: return 0
            # Handles '1,298' -> 1298 or '1.5K' -> 1500 (if you want to get fancy)
            text = text.replace(',', '').replace(' ', '')
            if 'K' in text:
                return int(float(text.replace('K', '')) * 1000)
            if 'M' in text:
                return int(float(text.replace('M', '')) * 1000000)
            return int(re.sub(r'\D', '', text) or 0)
            
        url = f"https://x.com/{username}"
        data = {
            "platform": "twitter",
            "username": username,
            "name": None,
            "bio": None,
            "location": None,
            "links": [],
            "followers": 0,
            "following": 0,
            "posts": 0
        }


        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            # Use a real User-Agent to avoid the "Login Wall"
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = context.new_page()
                
            try:
                page.goto(url, wait_until="domcontentloaded")
                # Wait for the main profile header to load
                page.wait_for_selector("div[data-testid='UserProfileHeader_Items']", timeout=7000)
                header_links = page.locator("div[data-testid='UserProfileHeader_Items'] a[href], div[data-testid='UserDescription'] a[href]").all()
                    
                # 1. Extract Display Name
                name_element = page.locator("div[data-testid='UserName'] span").first
                if name_element.count() > 0:
                    data["name"] = name_element.inner_text()

                # 2. Extract Bio Text
                bio_element = page.locator("div[data-testid='UserDescription']")
                if bio_element.count() > 0:
                    data["bio"] = bio_element.inner_text()
                    # Extract links found inside the bio text
                    data["links"].extend(self.expand_url(l) for l in self.extract_links(data["bio"]))

                # 3. Extract Location
                loc_element = page.locator("span[data-testid='UserLocation']")
                if loc_element.count() > 0:
                    data["location"] = loc_element.inner_text()


                # 4. Extract Links from Profile Header and Bio
                for link in header_links:
                    href = link.get_attribute("href")

                    if href:
                        resolved_url = self.expand_url(href)

                        if not any (x in resolved_url for x in ["twitter.com", "x.com"]):
                            data["links"].append(self.normalize_links(resolved_url))

                    # 4. Extract Website Link (The official link field)
                    # link_element = page.locator("a[data-testid='UserProfileHeader_Items_Url']")
                    # if link_element.count() > 0:
                    #     official_link = link_element.get_attribute("href")
                    #     if official_link:
                    #         data["links"].append(official_link)
                    #         print(f"Found official website link in Twitter profile: {data['links']}")

                    # 5. Extract Stats (Followers/Following)
                    # Note: These often require specific regex or nth-child selectors
                stats = page.locator("a[href$='/verified_followers'] span, a[href$='/following'] span").all()
                if len(stats) >= 2:
                        # Very basic mapping; Twitter UI changes often
                    data["following"] = parse_count(stats[0].inner_text())
                    data["followers"] = parse_count(stats[1].inner_text())

            except Exception as e:
                print(f"Error fetching Twitter profile: {e}")
                return None
            finally:
                browser.close()

            data["links"] = list(set(filter(None, data["links"])))
            return data