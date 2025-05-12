import os
import openai
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

def sanitize_text(text):
    if text is None:
        return ""
    return text.encode('ascii', 'ignore').decode('ascii')

def sanitize_for_pdf(text):
    if text is None:
        return ""
    replacements = {
        '\u2013': '-', '\u2014': '--',
        '\u2018': "'", '\u2019': "'",
        '\u201C': '"', '\u201D': '"',
        '\u2026': '...'
    }
    for unicode_char, ascii_char in replacements.items():
        text = text.replace(unicode_char, ascii_char)
    return text

def summarize_text(text, topic):
    prompt = f"""Please provide a concise summary of the following article:
{text[:4000]}
Ensure the summary is highly relevant to the topic: {topic}. Include factual details, numbers, and examples if any."""
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Summarization error: {e}")
        return ""

def can_scrape_url(url, headers):
    """Test if a URL can be successfully scraped."""
    try:
        if not url.strip():
            return False
            
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
            
        response = requests.get(url, headers=headers, timeout=8)
        if response.status_code != 200:
            return False
            
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "html.parser")
        
        main_content = soup.find('article') or soup.find('div', class_='main-content') or soup.find('div', id='content')
        paragraphs = main_content.find_all("p") if main_content else soup.find_all("p")
        
        content = " ".join([p.get_text() for p in paragraphs])
        if len(content) < 200:
            return False
            
        return True
    except Exception:
        return False

def extract_and_summarize_content(links, topic=""):
    """
    Extract and summarize content from multiple links.
    Since these links have already been validated as scrapable, we should have higher success rate.
    
    Returns a list of successful extractions, handling failures gracefully.
    """
    print("Extracting and summarizing content from previously validated links...")
    all_research_data = []
    successful_links = 0
    failed_links = []

    for link in links:
        try:
            # Process each link individually
            link_data = extract_content_from_link(link, topic)
            
            # Only add valid data
            if validate_research_data(link_data):
                all_research_data.extend(link_data)
                successful_links += 1
                print(f"Valid research data obtained from {link}")
            else:
                failed_links.append(link)
                print(f"Invalid research data structure from {link}")
        except Exception as e:
            failed_links.append(link)
            print(f"Exception processing {link}: {e}")
    
    # Add fallback content if everything failed
    if not all_research_data and topic:
        try:
            # Generate some basic content about the topic if all extractions failed
            print("All links failed, generating fallback content")
            fallback_text = f"""No content could be extracted from the provided links. 
            Here's some general information about {topic} that might be helpful for your content generation."""
            
            all_research_data.append({
                "title": f"Fallback Information: {topic}",
                "link": "",
                "summarized_text": fallback_text
            })
        except Exception:
            pass
    
    print(f"Processed {len(links)} links: {successful_links} successful, {len(failed_links)} failed")
    return all_research_data

def get_scrapable_urls(topic, requested_num=5, max_attempts=15):
    """
    Find exactly the requested number of URLs that can be successfully scraped.
    
    Args:
        topic: The search topic
        requested_num: Number of scrapable URLs requested
        max_attempts: Maximum number of search results to try
        
    Returns:
        List of scrapable URLs of the requested length or as many as could be found
    """
    from utils.search_engine import get_final_result
    
    # Get more search results than needed since some might not be scrapable
    extra_results = max(requested_num * 2, max_attempts)
    all_results = get_final_result(topic, num_results=extra_results)
    
    if not all_results:
        return []
    
    # Sort results by quality score
    sorted_results = sorted(all_results, key=lambda x: x.get('quality_score', 0), reverse=True)
    
    # Headers for scraping test
    headers = {
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                     'AppleWebKit/537.36 (KHTML, like Gecko) '
                     'Chrome/91.0.4472.124 Safari/537.36')
    }
    
    # Test each URL until we have enough scrapable ones
    scrapable_urls = []
    for result in sorted_results:
        url = result.get('href', '')
        print(f"Testing URL: {url}")
        
        # Do a more thorough test by actually extracting content
        test_data = extract_content_from_link(url, topic)
        
        # Only include URLs that can be successfully scraped
        if test_data and validate_research_data(test_data):
            scrapable_urls.append(result)
            print(f"✅ Found fully scrapable URL: {url}")
            
            if len(scrapable_urls) >= requested_num:
                break
        else:
            print(f"❌ Skipping non-scrapable URL: {url}")
    
    print(f"Found {len(scrapable_urls)} scrapable URLs out of {len(sorted_results)} tested")
    return scrapable_urls

# Update to utils/web_scrapping.py - Add this function

def validate_url_for_scraping(url, headers=None):
    """Validate if a URL is suitable for scraping."""
    if not headers:
        headers = {
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/91.0.4472.124 Safari/537.36')
        }
    
    try:
        # Skip empty URLs
        if not url or not url.strip():
            return False
            
        # Add https:// if missing
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
            
        # Try to fetch the URL with a reasonable timeout
        response = requests.get(url, headers=headers, timeout=10)
        
        # Check if the response is successful
        if response.status_code != 200:
            return False
            
        # Check content type to make sure it's HTML
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type:
            return False
            
        # Try to parse the content
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Check if we can find the main content
        main_content = soup.find('article') or soup.find('div', class_='main-content') or soup.find('div', id='content')
        paragraphs = main_content.find_all("p") if main_content else soup.find_all("p")
        
        # Extract text content
        content = " ".join([p.get_text() for p in paragraphs])
        
        # Check if there's enough content
        return len(content) >= 200
        
    except Exception as e:
        print(f"URL validation error for {url}: {e}")
        return False

def validate_research_data(data):
    """
    Validates that research data has the expected structure.
    Returns True if the data is valid, False otherwise.
    """
    if not isinstance(data, list):
        print("Research data is not a list")
        return False
    
    if not data:
        print("Research data is empty")
        return False
    
    for item in data:
        if not isinstance(item, dict):
            print("Research data item is not a dictionary")
            return False
        
        if not all(key in item for key in ["title", "link", "summarized_text"]):
            print("Research data item missing required keys")
            return False
            
        if not item["summarized_text"]:
            print("Research data item has empty summarized text")
            return False
    
    return True

def extract_content_from_link(link, topic=""):
    """Extract content from a single link and return the data."""
    print(f"Attempting extraction from: {link}")
    research_data = []
    
    headers = {
        'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                       'AppleWebKit/537.36 (KHTML, like Gecko) '
                       'Chrome/91.0.4472.124 Safari/537.36')
    }
    
    if not link or not link.strip():
        return []
        
    if not link.startswith(("http://", "https://")):
        link = f"https://{link}"

    try:
        # Use a shorter timeout for testing scrapeability
        response = requests.get(link, headers=headers, timeout=7)
        if response.status_code != 200:
            print(f"Failed to access {link}: HTTP {response.status_code}")
            return []
            
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string if soup.title else "No Title"
        title = sanitize_text(title)

        main_content = soup.find('article') or soup.find('div', class_='main-content') or soup.find('div', id='content')
        paragraphs = main_content.find_all("p") if main_content else soup.find_all("p")

        content = " ".join([p.get_text() for p in paragraphs])
        content = sanitize_text(content)

        if len(content) < 200:
            print(f"Content too short from {link}: {len(content)} chars")
            return []

        summarized_text = summarize_text(content, topic)
        if not summarized_text:
            print(f"Failed to summarize content from {link}")
            return []

        research_data.append({
            "title": title,
            "link": link,
            "summarized_text": summarized_text
        })
        print(f"Successfully extracted content from {link}")
        
    except Exception as e:
        print(f"Failed to process {link}: {e}")
        return []
        
    return research_data

