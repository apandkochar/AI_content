import os
import logging
import requests
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from dotenv import load_dotenv
import openai

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_CX = os.getenv('GOOGLE_CX')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleSearcher:
    def __init__(self):
        """Initialize the search components."""
        if not all([GOOGLE_API_KEY, GOOGLE_CX, OPENAI_API_KEY]):
            raise ValueError("Missing required API keys in environment variables")
        
        self.service = build('customsearch', 'v1', developerKey=GOOGLE_API_KEY)
        self.cx = GOOGLE_CX
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def generate_search_queries(self, topic: str) -> List[str]:
        """Generate optimized search queries using GPT-4."""
        prompt = f"""Generate 3 specific search queries for researching the topic: "{topic}"

        Requirements:
        1. First query should focus on finding recent blog posts and articles
        2. Second query should target use cases and implementation examples
        3. Third query should look for case studies and technical documentation
        
        Make the queries specific and include:
        - Content type indicators (e.g., "blog post", "use case", "case study")
        - Time indicators (e.g., "2024", "recent")
        - Industry-specific terminology
        
        Format: Return only the queries as a Python list of strings.
        Example: ["query 1", "query 2", "query 3"]"""

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            queries = eval(response.choices[0].message.content)
            logger.info(f"Generated queries: {queries}")
            return queries
        except Exception as e:
            logger.error(f"Error generating queries: {str(e)}")
            # Fallback queries if GPT fails
            return [
                f"{topic} blog post 2024",
                f"{topic} use case implementation",
                f"{topic} case study technical documentation"
            ]

    def search(self, topic: str, num_results: int = 10) -> List[Dict]:
        """Perform the search and return accessible results."""
        queries = self.generate_search_queries(topic)
        all_results = []

        for query in queries:
            try:
                # Perform Google search
                results = self.service.cse().list(
                    q=query,
                    cx=self.cx,
                    num=10
                ).execute()

                # Process each result
                for item in results.get('items', []):
                    url = item.get('link')
                    if not url:
                        continue

                    # Check if content is accessible
                    if self._is_accessible(url):
                        result = {
                            'title': item.get('title', ''),
                            'url': url,
                            'snippet': item.get('snippet', ''),
                            'source_query': query
                        }
                        all_results.append(result)
                        logger.info(f"Found accessible content: {url}")

            except Exception as e:
                logger.error(f"Error searching for query '{query}': {str(e)}")
                continue

        # Remove duplicates based on URL
        seen_urls = set()
        unique_results = []
        for result in all_results:
            if result['url'] not in seen_urls:
                seen_urls.add(result['url'])
                unique_results.append(result)

        return unique_results[:num_results]

    def _is_accessible(self, url: str) -> bool:
        """Check if the content at the URL is accessible and not paywalled."""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                return False

            # Check for common paywall indicators
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text().lower()
            
            paywall_indicators = [
                'subscribe', 'sign in', 'log in', 'paywall',
                'premium content', 'members only', 'subscription required'
            ]
            
            if any(indicator in text for indicator in paywall_indicators):
                return False

            # Check if there's enough content
            content_length = len(soup.get_text())
            if content_length < 500:  # Minimum content length threshold
                return False

            return True

        except Exception as e:
            logger.error(f"Error checking accessibility for {url}: {str(e)}")
            return False

def search_topic(topic: str, num_results: int = 10) -> List[Dict]:
    """
    Main function to search for content about a topic.
    
    Args:
        topic (str): The topic to search for
        num_results (int): Maximum number of results to return
        
    Returns:
        List[Dict]: List of search results with title, URL, and snippet
    """
    try:
        searcher = SimpleSearcher()
        results = searcher.search(topic, num_results)
        return results
    except Exception as e:
        logger.error(f"Error in search_topic: {str(e)}")
        return [] 