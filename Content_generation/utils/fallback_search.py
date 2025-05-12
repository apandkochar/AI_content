# utils/fallback_search.py

import requests
import re
import random
import time
from bs4 import BeautifulSoup

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
]

def get_random_user_agent():
    return random.choice(USER_AGENTS)

def test_url_scrapability(url, timeout=8):
    """Test if a URL can be scraped successfully."""
    try:
        if not url or not url.strip():
            return False
            
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
            
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=timeout)
        if response.status_code != 200:
            return False
            
        content_type = response.headers.get('Content-Type', '').lower()
        if 'text/html' not in content_type:
            return False
            
        # Check if there's readable content
        soup = BeautifulSoup(response.text, 'html.parser')
        main_content = soup.find('article') or soup.find('div', class_='main-content') or soup.find('div', id='content')
        paragraphs = main_content.find_all("p") if main_content else soup.find_all("p")
        
        text_content = " ".join([p.get_text() for p in paragraphs])
        
        # Return true if there's enough content
        return len(text_content) >= 200
        
    except Exception:
        return False


def fallback_search(query, num_results=10, test_scrapability=True):
    """
    Perform a Google search without using the Google API.
    
    Args:
        query: Search query
        num_results: Number of results to return
        test_scrapability: Whether to test if the URL can be scraped
        
    Returns:
        List of SearchResult objects with title, url, and description
    """
    results = []
    query = query.replace(' ', '+')
    
    # Need to get more results than requested since some might not be scrapable
    pages_to_fetch = (num_results // 10) + 1
    
    for page in range(pages_to_fetch):
        if len(results) >= num_results:
            break
            
        start_index = page * 10
        search_url = f"https://www.google.com/search?q={query}&start={start_index}"
        
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        try:
            response = requests.get(search_url, headers=headers, timeout=10)
            if response.status_code != 200:
                print(f"Warning: Got status code {response.status_code} from Google")
                # Add delay before trying next page to avoid getting blocked
                time.sleep(random.uniform(5, 10))
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract search results
            search_divs = soup.find_all('div', class_='tF2Cxc')
            if not search_divs:  # Try alternative class
                search_divs = soup.find_all('div', class_='g')
            
            for div in search_divs:
                # Extract the URL
                link_element = div.find('a')
                if not link_element:
                    continue
                    
                url = link_element.get('href')
                if not url or not url.startswith('http'):
                    continue
                
                # Extract the title
                title_element = div.find('h3')
                title = title_element.get_text() if title_element else "No title"
                
                # Extract the description
                desc_element = div.find('div', class_='VwiC3b')
                description = desc_element.get_text() if desc_element else ""
                
                # Skip if URL already in results
                if any(r['url'] == url for r in results):
                    continue
                
                # Test if URL is scrapable if requested
                if test_scrapability and not test_url_scrapability(url):
                    print(f"Skipping non-scrapable URL: {url}")
                    continue
                
                # Add result to our list
                results.append({
                    'title': title,
                    'url': url,
                    'description': description
                })
                
                # Break if we have enough results
                if len(results) >= num_results:
                    break
            
            # Add random delay between page fetches
            time.sleep(random.uniform(3, 7))
            
        except Exception as e:
            print(f"Error during fallback search: {e}")
            time.sleep(random.uniform(5, 10))
    
    return results[:num_results]