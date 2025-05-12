import os
import re
import openai
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import argparse
from typing import Optional, Dict, Any
import io
import PyPDF2
import urllib.parse
# Remove the circular import
# from content_research import ContentResearcher
#from utils.text_processing import summarize_text

# Import your search pipeline
# from internet_search import SearchCoordinator

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# --- Helper functions ---
def sanitize_text(text: str) -> str:
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters
    text = re.sub(r'[^\w\s.,!?-]', '', text)
    return text.strip()

def sanitize_for_pdf(text: str) -> str:
    if text is None:
        return ""
    replacements = {
        '\u2013': '-', '\u2014': '--',
        '\u2018': "'", '\u2019': "'",
        '\u201C': '"', '\u201D': '"',
        '\u2026': '...'
    }
    for u, a in replacements.items():
        text = text.replace(u, a)
    return text

def summarize_text(text: str, topic: str) -> str:
    prompt = (
        f"Please provide a concise summary of the following article (keep it under 1500 words):\n"
        f"{text[:4000]}\n\n"
        f"Ensure the summary is highly relevant to the topic: {topic}. "
        "Include factual details, numbers, and examples if any."
    )
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"Summarization error: {e}")
        return ""

# --- Extraction & Summarization ---
def extract_content_from_link(url: str, topic: Optional[str] = None) -> Dict[str, Any]:
    try:
        # Check if the URL is a PDF
        is_pdf = url.lower().endswith('.pdf') or 'pdf' in url.lower()
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Download the content
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        content = ""
        
        if is_pdf:
            # Handle PDF content
            try:
                # Create a PDF reader object
                pdf_file = io.BytesIO(response.content)
                pdf_reader = PyPDF2.PdfReader(pdf_file)
                
                # Extract text from each page
                for page_num in range(len(pdf_reader.pages)):
                    page = pdf_reader.pages[page_num]
                    content += page.extract_text() + "\n\n"
                
                if not content.strip():
                    return {
                        "success": False,
                        "error": "Failed to extract text from PDF"
                    }
            except Exception as e:
                print(f"PDF extraction error: {e}")
                return {
                    "success": False,
                    "error": f"PDF extraction error: {str(e)}"
                }
        else:
            # Handle HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'footer', 'header']):
                element.decompose()
            
            # Extract main content
            content = ' '.join([p.get_text() for p in soup.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6'])])
            content = content.strip()
            
            if not content:
                return {
                    "success": False,
                    "error": "Failed to extract content from URL"
                }
        
        # Sanitize the content
        sanitized_content = sanitize_text(content)
        
        # Create summary if topic is provided
        summary = None
        if topic:
            summary = summarize_text(sanitized_content, topic)
            
        return {
            "success": True,
            "content": sanitized_content,
            "summary": summary,
            "url": url
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

# --- Validation ---
def validate_research_data(data) -> bool:
    if not isinstance(data, list) or not data:
        return False
    for item in data:
        if not isinstance(item, dict):
            return False
        if not all(k in item for k in ('title','link','summarized_text')):
            return False
        if not item['summarized_text'].strip():
            return False
    return True

# --- Main pipeline ---
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Search, extract, and summarize content for a given topic"
    )
    parser.add_argument('-t','--topic', required=True, help="Topic to research")
    parser.add_argument('-n','--num', type=int, default=5, help="Number of scrapable URLs to retrieve")
    args = parser.parse_args()

    # This part would need to be modified since we removed the SearchCoordinator import
    print(f"Please provide URLs to analyze for topic: {args.topic}")
    urls = input("Enter URLs separated by commas: ").split(',')
    urls = [url.strip() for url in urls]

    # 2. Extract & summarize each URL
    final_data = []
    for url in urls:
        data = extract_content_from_link(url, args.topic)
        if data["success"]:
            final_data.append({
                "title": url,  # Using URL as title since we don't have it
                "link": url,
                "summarized_text": data.get("summary", data["content"][:200] + "...")
            })
        else:
            print(f"Skipping invalid data from {url}: {data.get('error', 'Unknown error')}")

    # 3. Output results
    print(f"\n--- Research Summaries for '{args.topic}' ---\n")
    for item in final_data:
        print(f"Title: {item['title']}\nLink: {item['link']}\nSummary:\n{item['summarized_text']}\n{'-'*60}\n")
