import os
import re
import requests
from bs4 import BeautifulSoup
import numpy as np
import openai
from googleapiclient.discovery import build
from dotenv import load_dotenv
load_dotenv()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
GOOGLE_CX = os.environ.get("GOOGLE_CX")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai.api_key = os.getenv("OPENAI_API_KEY", OPENAI_API_KEY)


def clean_query(query: str) -> str:
    """Google-optimized query cleaning"""
    query = re.sub(r'["""\']', '', query)  # Remove quotes
    query = re.sub(r'\b(OR|AND|NOT)\b', '', query)  # Remove boolean operators
    return re.sub(r'\s+', ' ', query).strip()


def generate_search_query(topic: str) -> list:
    """Generate search queries without quotes"""
    prompt = f"""
    Generate 5 search queries for technical content about: {topic} 
    that focus on the latest, real-time, and factual information.
    The queries should target highly relevant blogs, articles,interviews and news.
    """
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3
    )
    queries_text = response.choices[0].message.content
    raw_queries = [re.sub(r'^\d+\.\s*', '', q.strip()) 
                   for q in queries_text.splitlines() if q.strip()]
    return [clean_query(q.replace('"', '')) for q in raw_queries]


def google_search(query: str, num_results: int = 10) -> list:
    """Returns list of search results (empty list on failure)"""
    try:
        query = clean_query(query)
        service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
        
        # Google Custom Search API has a maximum of 10 results per request
        num_results = min(10, num_results)
        
        result = service.cse().list(
            q=query,
            cx=GOOGLE_CX,
            num=num_results
        ).execute()
        
        formatted_results = []
        for item in result.get("items", []):
            formatted_results.append({
                "title": item.get("title", "No title"),
                "href": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "date": item.get("pagemap", {}).get("metatags", [{}])[0].get("article:published_time", "")
            })
        return formatted_results
        
    except Exception as err:
        print(f"Google Search error: {err}")
        return []
    

def filter_by_relevance(results: list, topic: str, threshold: float = 0.7) -> list:
    """Filters search results based on semantic similarity"""
    def get_embedding(text: str) -> np.ndarray:
        response = openai.Embedding.create(
            model="text-embedding-ada-002",
            input=text
        )
        return np.array(response["data"][0]["embedding"])
    
    topic_embedding = get_embedding(topic)
    filtered = []
    
    for r in results:
        combined_text = f"{r.get('title', '')} {r.get('snippet', '')}"
        text_embedding = get_embedding(combined_text)
        similarity = np.dot(topic_embedding, text_embedding) / (
            np.linalg.norm(topic_embedding) * np.linalg.norm(text_embedding)
        )
        if similarity > threshold:
            r['similarity_score'] = similarity
            filtered.append(r)
            
    return filtered


def assess_content_quality(text: str) -> float:
    """Uses GPT-4 to assess technical quality (0-10)"""
    prompt = f"""
    Rate the technical quality (0-10) of this content excerpt:
    - 10: Highly technical, data-rich, authoritative
    - 5: Some technical details, general audience
    - 0: Non-technical, promotional, irrelevant
    
    Excerpt: {text[:1500]}
    """
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1
    )
    try:
        return float(response.choices[0].message.content.strip())
    except:
        return 0.0

class SearchAgent:
    def __init__(self):
        from utils.web_scrapping import extract_content_from_link
        self.extract_content_from_link = extract_content_from_link
        self.seen_urls = set()  # Track all URLs we've seen across searches

    def google_search_with_exclusions(self, query: str, num_results: int = 10) -> list:
        """Performs Google search while excluding already seen URLs"""
        try:
            query = clean_query(query)
            
            # If we have seen URLs, add exclusions to the query
            if self.seen_urls:
                # Add site exclusions to the query (up to 30 exclusions to keep query length reasonable)
                exclusions = ' '.join([f'-site:{url.split("/")[2]}' for url in list(self.seen_urls)[:30]])
                query = f"{query} {exclusions}"
            
            service = build("customsearch", "v1", developerKey=GOOGLE_API_KEY)
            result = service.cse().list(
                q=query,
                cx=GOOGLE_CX,
                num=min(10, num_results)
            ).execute()
            
            formatted_results = []
            for item in result.get("items", []):
                url = item.get("link", "")
                if url not in self.seen_urls:  # Double check we're not getting duplicates
                    self.seen_urls.add(url)  # Track this URL
                    formatted_results.append({
                        "title": item.get("title", "No title"),
                        "href": url,
                        "snippet": item.get("snippet", ""),
                        "date": item.get("pagemap", {}).get("metatags", [{}])[0].get("article:published_time", "")
                    })
            return formatted_results
            
        except Exception as err:
            print(f"Google Search error: {err}")
            return []

    def search(self, topic: str, num_results: int = 5, max_search_iterations: int = 3) -> list:
        """Returns list of results with multiple search iterations if needed"""
        try:
            scrapeable_results = []
            search_iteration = 0
            
            while (len(scrapeable_results) < num_results and 
                   search_iteration < max_search_iterations):
                
                search_iteration += 1
                print(f"\nStarting search iteration {search_iteration}/{max_search_iterations}")
                
                # Generate fresh queries for each iteration
                queries = generate_search_query(topic)
                iteration_results = []
                
                # Search with each query
                for query in queries:
                    try:
                        results = self.google_search_with_exclusions(query, num_results=10)
                        iteration_results.extend(results)
                        print(f"Found {len(results)} new results for query: {query}")
                    except Exception as e:
                        print(f"Search failed for query '{query}': {str(e)}")
                        continue

                if not iteration_results:
                    print(f"No new results found in iteration {search_iteration}")
                    break

                # Test scrapeability
                for result in iteration_results:
                    if len(scrapeable_results) >= num_results:
                        break
                        
                    try:
                        url = result.get("href", "")
                        print(f"Testing scrapeability of: {url}")
                        
                        # Try to extract content to verify scrapeability
                        content = self.extract_content_from_link(url, topic)
                        if content:  # If content extraction succeeded
                            result['is_scrapeable'] = True
                            # Check relevance before adding
                            relevant_results = filter_by_relevance([result], topic)
                            if relevant_results:
                                # Add quality score
                                quality = assess_content_quality(result.get("snippet", ""))
                                result['quality_score'] = quality
                                scrapeable_results.append(result)
                                print(f"✅ Found scrapeable and relevant URL: {url}")
                    except Exception as e:
                        print(f"❌ Scraping test failed for {url}: {str(e)}")
                        continue

                print(f"End of iteration {search_iteration}. "
                      f"Found {len(scrapeable_results)}/{num_results} scrapeable results")
                
                if not iteration_results:  # If we got no new results, stop searching
                    break

            # Final sorting of all results by quality score
            final_results = sorted(
                scrapeable_results,
                key=lambda x: x.get('quality_score', 0),
                reverse=True
            )[:num_results]
            
            print(f"\nSearch completed. Found {len(final_results)} scrapeable and relevant results "
                  f"after {search_iteration} iterations")
            
            return final_results
            
        except Exception as e:
            print(f"Search error: {str(e)}")
            return []

def get_final_result(topic: str, num_results: int = 5) -> list:
    """
    Returns list of results with consistent structure:
    [
        {
            "title": str,
            "href": str,
            "quality_score": float,
            "similarity_score": float (optional)
        },
        ...
    ]
    """
    try:
        agent = SearchAgent()
        results = agent.search(topic, num_results=num_results)
        
        # Ensure consistent output format
        formatted_results = []
        for result in results:
            formatted_results.append({
                "title": result.get("title", "No title"),
                "href": result.get("href", ""),
                "quality_score": result.get("quality_score", 0),
                "similarity_score": result.get("similarity_score", 0)
            })
            
        return formatted_results
        
    except Exception as e:
        print(f"Final result error: {str(e)}")
        return []
