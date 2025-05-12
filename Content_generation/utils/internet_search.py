import os
import re
import logging
import requests
import pdfplumber
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from dataclasses import dataclass, asdict
from typing import List, Dict, Set, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse
from datetime import datetime
from bs4 import BeautifulSoup

import openai
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
GOOGLE_CX = os.getenv('GOOGLE_CX')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    title: str
    href: str
    snippet: str
    published: Optional[str]
    quality_score: float = 0.0
    relevance_reasons: List[str] = None

class SeenURLStore:
    def __init__(self):
        self._seen: Set[str] = set()

    def _normalize(self, url: str) -> str:
        parsed = urlparse(url)
        qs = parse_qs(parsed.query, keep_blank_values=True)
        for key in list(qs):
            if key.lower().startswith(('utm_', 'ref', 'fbclid')):
                del qs[key]
        new_query = urlencode(qs, doseq=True)
        return urlunparse(parsed._replace(query=new_query))

    def add(self, url: str):
        self._seen.add(self._normalize(url))

    def contains(self, url: str) -> bool:
        return self._normalize(url) in self._seen

class LLMQueryGenerator:
    def __init__(self, model: str = 'gpt-4'):
        self.model = model
        self.domain_exclusions = [
            '-site:linkedin.com', '-site:quora.com', 
            '-site:youtube.com'
        ]

    def generate(self, topic: str) -> List[str]:
        prompt = f"""Generate 5 technical Google search queries for "{topic}".
        Include these elements:
        1. Expand acronyms (e.g., AR → Augmented Reality , AI → Artificial Intelligence)
        2. Specify content types: case study, Use case article ,blogs, technical report
        3. Include industry-specific terminology
        4. Focus on recent implementations (2019-2025)
        
        Format as: ["query 1", "query 2"]"""
        
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5
        )
        
        queries = self._parse_queries(response.choices[0].message.content)
        return [f'{q} {" ".join(self.domain_exclusions)} filetype:pdf|html' for q in queries]

    def _parse_queries(self, text: str) -> List[str]:
        try:
            return eval(text)
        except:
            return [line.strip(' "') for line in text.splitlines()[:5] if line.strip()]

class GoogleSearcher:
    def __init__(self, api_key: str, cx: str, seen_store: SeenURLStore):
        self.service = build('customsearch', 'v1', developerKey=api_key)
        self.cx = cx
        self.seen = seen_store
        self.content_indicators = {
            'case study', 'technical report', 'whitepaper',
            'implementation', 'research paper', 'analysis','use case'
        }

    def search(self, queries: List[str]) -> List[SearchResult]:
        params = {
            'cx': self.cx,
            'num': 10,
            'dateRestrict': 'y5',
            'fileType': 'pdf|html',
            'rights': 'cc_publicdomain',
            'sort': 'date',
            'siteSearch': ' '.join([
                'site:researchgate.net',
                'site:ieee.org',
                'site:springer.com'
            ])
        }

        results = []
        for query in queries:
            try:
                resp = self.service.cse().list(q=query, **params).execute()
                results.extend(self._process_response(resp))
            except Exception as e:
                logger.error(f"Search error: {str(e)[:100]}")
        return results

    def _process_response(self, resp: dict) -> List[SearchResult]:
        output = []
        for item in resp.get('items', []):
            if self._is_relevant(item):
                result = SearchResult(
                    title=item.get('title', ''),
                    href=item.get('link', ''),
                    snippet=item.get('snippet', ''),
                    published=item.get('pagemap', {}).get('metatags', [{}])[0].get('article:published_time'),
                    relevance_reasons=[]
                )
                if not self.seen.contains(result.href):
                    self.seen.add(result.href)
                    output.append(result)
        return output

    def _is_relevant(self, item: dict) -> bool:
        title = item.get('title', '').lower()
        return any(indicator in title for indicator in self.content_indicators)

class ContentAnalyzer:
    def __init__(self):
        self.headers = {'User-Agent': 'TechnicalResearchBot/1.0'}
        self.timeout = 10
        self.retries = 2

    def extract_content(self, url: str) -> Dict[str, Any]:
        content = {'success': False, 'content': '', 'published_date': None}
        
        try:
            if url.endswith('.pdf'):
                return self._process_pdf(url)
            return self._process_html(url)
        except Exception as e:
            logger.warning(f"Extraction failed: {str(e)[:100]}")
            return content

    def _process_pdf(self, url: str) -> Dict[str, Any]:
        content = {'success': False, 'content': ''}
        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            with pdfplumber.open(response.content) as pdf:
                content['content'] = '\n'.join(page.extract_text() for page in pdf.pages)
                content['success'] = len(content['content']) > 500
            return content
        except Exception as e:
            raise ValueError(f"PDF processing error: {str(e)}")

    def _process_html(self, url: str) -> Dict[str, Any]:
        content = {'success': False, 'content': ''}
        for _ in range(self.retries):
            try:
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
                if response.status_code != 200:
                    continue

                soup = BeautifulSoup(response.text, 'html.parser')
                main_content = soup.find(['article', 'main']) or soup.body
                text = main_content.get_text(separator='\n', strip=True)
                
                if any(s in text.lower() for s in ['sign in', 'subscribe']):
                    raise ValueError("Paywalled content detected")

                content['content'] = text
                content['success'] = len(text) > 1000
                return content
            except Exception as e:
                continue
        raise ValueError(f"HTML processing failed after {self.retries} attempts")

class RelevanceScorer:
    def __init__(self):
        self.tech_term_weight = 3
        self.keyword_weight = 2
        self.structure_bonus = 30
        self.recency_decay = 5  # Points lost per year

    def calculate_score(self, content: str, topic: str, publish_date: str) -> Tuple[float, List[str]]:
        analysis = self._analyze_topic(topic)
        reasons = []
        score = 0

        # Term-based scoring
        content_lower = content.lower()
        tech_matches = sum(content_lower.count(term) for term in analysis['technical_terms'])
        score += tech_matches * self.tech_term_weight
        if tech_matches > 0:
            reasons.append(f"Contains {tech_matches} technical terms")

        keyword_matches = sum(content_lower.count(term) for term in analysis['keywords'])
        score += keyword_matches * self.keyword_weight
        if keyword_matches > 0:
            reasons.append(f"Contains {keyword_matches} keywords")

        # Structural scoring
        structure_terms = {'methodology', 'implementation', 'results', 'conclusion'}
        if any(term in content_lower for term in structure_terms):
            score += self.structure_bonus
            reasons.append("Includes technical sections")

        # Recency scoring
        if publish_date:
            try:
                pub_year = datetime.fromisoformat(publish_date).year
                score -= (datetime.now().year - pub_year) * self.recency_decay
                reasons.append(f"Published in {pub_year}")
            except:
                pass

        return max(0, score), reasons

    def _analyze_topic(self, topic: str) -> Dict[str, list]:
        prompt = f"""Analyze technical components of: "{topic}"
        Output format:
        KEYWORDS: comma,separated,terms
        TECHNICAL_TERMS: comma,separated,terms"""
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}]
        )
        return self._parse_analysis(response.choices[0].message.content)

    def _parse_analysis(self, text: str) -> Dict[str, list]:
        return {
            'keywords': self._extract_section(text, 'KEYWORDS'),
            'technical_terms': self._extract_section(text, 'TECHNICAL_TERMS'),
        }

    def _extract_section(self, text: str, section: str) -> List[str]:
        match = re.search(fr"{section}:\s*(.+)", text)
        return [t.strip().lower() for t in match.group(1).split(',')] if match else []

class SearchCoordinator:
    def __init__(self, topic: str, num_results: int = 5):
        self.topic = topic
        self.num_results = num_results
        self.seen_store = SeenURLStore()
        self.query_generator = LLMQueryGenerator()
        self.searcher = GoogleSearcher(GOOGLE_API_KEY, GOOGLE_CX, self.seen_store)
        self.content_analyzer = ContentAnalyzer()
        self.relevance_scorer = RelevanceScorer()

    def run(self) -> List[Dict]:
        queries = self.query_generator.generate(self.topic)
        search_results = self.searcher.search(queries)
        
        processed_results = []
        for result in search_results:
            processed = self._process_result(result)
            if processed:
                processed_results.append(processed)
                if len(processed_results) >= self.num_results:
                    break
        
        return processed_results

    def _process_result(self, result: SearchResult) -> Optional[Dict]:
        try:
            content = self.content_analyzer.extract_content(result.href)
            if not content['success']:
                return None

            score, reasons = self.relevance_scorer.calculate_score(
                content['content'], self.topic, result.published
            )
            
            result.quality_score = score
            result.relevance_reasons = reasons
            return asdict(result)
        except Exception as e:
            logger.warning(f"Processing failed for {result.href}: {str(e)[:100]}")
            return None

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Technical Content Search Engine")
    parser.add_argument('-t', '--topic', required=True, help="Technical topic to research")
    parser.add_argument('-n', '--num', type=int, default=5, help="Number of results to return")
    
    args = parser.parse_args()
    coordinator = SearchCoordinator(args.topic, args.num)
    results = coordinator.run()

    print(f"\nTop {args.num} Results for '{args.topic}':")
    for idx, res in enumerate(results, 1):
        print(f"{idx}. {res['title']} ({res['quality_score']:.1f})")
        print(f"   URL: {res['href']}")
        print(f"   Reasons: {', '.join(res['relevance_reasons'])}\n")
        

def get_final_result(topic: str, num_results: int = 5) -> list:
    """
    Compatibility function to match the interface of the old search_engine.py
    Returns list of results with same structure as the old function:
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
    coordinator = SearchCoordinator(topic=topic, n_results=num_results)
    results = coordinator.run()
    
    # Format results to match the old interface
    formatted_results = []
    for result in results:
        formatted_results.append({
            "title": result.get("title", "No title"),
            "href": result.get("href", ""),
            "quality_score": result.get("quality_score", 0),
            "similarity_score": 0.0  # Default value since we don't have this in the new system
        })
    
    return formatted_results

def search_topic(topic: str, num_results: int = 10) -> List[Dict]:
    """
    Main function to search for content about a topic.
    This function is a compatibility wrapper around get_final_result.
    
    Args:
        topic (str): The topic to search for
        num_results (int): Maximum number of results to return
        
    Returns:
        List[Dict]: List of search results with title, URL, and snippet
    """
    try:
        # Use the new search functionality
        results = get_final_result(topic, num_results)
        
        # Format results to match the expected interface
        formatted_results = []
        for result in results:
            formatted_results.append({
                "title": result.get("title", "No title"),
                "url": result.get("href", ""),
                "snippet": result.get("snippet", "No snippet available")
            })
        
        return formatted_results
    except Exception as e:
        logger.error(f"Error in search_topic: {str(e)}")
        return []