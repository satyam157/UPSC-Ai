"""
Syllabus Resource Scraper - Fetches UPSC Resources from Internet
Automatically fetches, parses, and summarizes content from multiple URLs
"""

import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
from typing import List, Dict, Tuple
import time

# ══════════════════════════════════════════════════════════════════════════════
# RESOURCE URLS - Main sources for each material type
# ══════════════════════════════════════════════════════════════════════════════

RESOURCE_URLS = {
    "Yojana": {
        "description": "Monthly magazine on government schemes and policies",
        "primary_urls": [
            "https://yojana.gov.in/",
            "https://www.thehindu.com/",
        ],
        "backup_urls": [
            "https://pib.gov.in/",
            "https://indianexpress.com/",
        ]
    },
    
    "Kurukshetra": {
        "description": "Monthly magazine on rural development and governance",
        "primary_urls": [
            "https://ird.gov.in/",
            "https://www.thehindu.com/news/",
        ],
        "backup_urls": [
            "https://pib.gov.in/",
            "https://indianexpress.com/",
        ]
    },
    
    "Economic Survey": {
        "description": "Annual economic review and policy analysis",
        "primary_urls": [
            "https://www.indiabudget.gov.in/",
            "https://www.thehindu.com/business/",
        ],
        "backup_urls": [
            "https://pib.gov.in/",
            "https://indianexpress.com/section/business/",
        ]
    },
    
    "Budget": {
        "description": "Union Budget allocation and major announcements",
        "primary_urls": [
            "https://www.indiabudget.gov.in/",
            "https://pib.gov.in/",
        ],
        "backup_urls": [
            "https://www.thehindu.com/business/",
            "https://indianexpress.com/section/business/",
        ]
    },
    
    "India Yearbook": {
        "description": "Key facts, figures, and institutions of India",
        "primary_urls": [
            "https://main.indiabudget.gov.in/",
            "https://pib.gov.in/",
        ],
        "backup_urls": [
            "https://www.thehindu.com/",
            "https://indianexpress.com/",
        ]
    }
}


# ══════════════════════════════════════════════════════════════════════════════
# WEB SCRAPING FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def fetch_url_content(url: str, timeout: int = 5) -> Tuple[bool, str]:
    """
    Fetch content from a URL and extract text
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds (default 5)
    
    Returns:
        (success: bool, content: str)
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(['script', 'style', 'meta', 'link']):
            script.decompose()
        
        # Get text
        text = soup.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        if not text or len(text) < 100:
            return False, "Page content too short"
        
        # Return first 3000 characters
        return True, text[:3000]
    
    except requests.Timeout:
        return False, f"Timeout fetching {url} (>5s)"
    except requests.ConnectionError:
        return False, f"Connection error: {url}"
    except requests.RequestException as e:
        return False, f"Error fetching URL: {str(e)[:50]}"
    except Exception as e:
        return False, f"Error parsing content: {str(e)[:50]}"


def fetch_resource_content(resource_type: str) -> Tuple[List[Dict], List[str]]:
    """
    Fetch content from multiple URLs for a resource type
    
    Args:
        resource_type: "Yojana", "Kurukshetra", etc.
    
    Returns:
        (articles: List[Dict with title, content, url], errors: List[str])
    """
    if resource_type not in RESOURCE_URLS:
        return [], [f"Unknown resource type: {resource_type}"]
    
    resource_info = RESOURCE_URLS[resource_type]
    articles = []
    errors = []
    
    # Try primary URLs first, then backup
    urls_to_try = resource_info['primary_urls'] + resource_info['backup_urls']
    
    for idx, url in enumerate(urls_to_try):
        if len(articles) >= 3:  # Get content from up to 3 sources
            break
        
        success, content = fetch_url_content(url)
        
        if success:
            articles.append({
                'url': url,
                'title': f"{resource_type} - Source {len(articles) + 1}",
                'content': content,
                'fetched_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
        else:
            errors.append(f"Source {idx + 1} ({url}): {content}")
        
        # Rate limiting
        if idx < len(urls_to_try) - 1 and len(articles) < 3:
            time.sleep(0.5)
    
    return articles, errors


def combine_articles_for_summary(articles: List[Dict]) -> str:
    """
    Combine content from multiple articles into one text for summarization
    
    Args:
        articles: List of article dicts with 'content' and 'url' keys
    
    Returns:
        Combined text suitable for LLM summarization
    """
    combined = []
    
    for idx, article in enumerate(articles, 1):
        combined.append(f"=== SOURCE {idx}: {article['url']} ===")
        combined.append(article['content'][:1500])
        combined.append("")
    
    return "\n".join(combined)


# ══════════════════════════════════════════════════════════════════════════════
# HIGH-LEVEL RESOURCE FETCHERS
# ══════════════════════════════════════════════════════════════════════════════

def fetch_yojana_summaries() -> Dict:
    """Fetch and prepare Yojana magazine content for summarization"""
    articles, errors = fetch_resource_content("Yojana")
    return {
        "type": "Yojana",
        "description": RESOURCE_URLS["Yojana"]["description"],
        "articles": articles,
        "errors": errors,
        "combined_content": combine_articles_for_summary(articles) if articles else ""
    }

def fetch_kurukshetra_summaries() -> Dict:
    """Fetch and prepare Kurukshetra magazine content"""
    articles, errors = fetch_resource_content("Kurukshetra")
    return {
        "type": "Kurukshetra",
        "description": RESOURCE_URLS["Kurukshetra"]["description"],
        "articles": articles,
        "errors": errors,
        "combined_content": combine_articles_for_summary(articles) if articles else ""
    }

def fetch_economic_survey_summaries() -> Dict:
    """Fetch and prepare Economic Survey content"""
    articles, errors = fetch_resource_content("Economic Survey")
    return {
        "type": "Economic Survey",
        "description": RESOURCE_URLS["Economic Survey"]["description"],
        "articles": articles,
        "errors": errors,
        "combined_content": combine_articles_for_summary(articles) if articles else ""
    }

def fetch_budget_summaries() -> Dict:
    """Fetch and prepare Budget content"""
    articles, errors = fetch_resource_content("Budget")
    return {
        "type": "Budget",
        "description": RESOURCE_URLS["Budget"]["description"],
        "articles": articles,
        "errors": errors,
        "combined_content": combine_articles_for_summary(articles) if articles else ""
    }

def fetch_india_yearbook_summaries() -> Dict:
    """Fetch and prepare India Yearbook content"""
    articles, errors = fetch_resource_content("India Yearbook")
    return {
        "type": "India Yearbook",
        "description": RESOURCE_URLS["India Yearbook"]["description"],
        "articles": articles,
        "errors": errors,
        "combined_content": combine_articles_for_summary(articles) if articles else ""
    }


# ══════════════════════════════════════════════════════════════════════════════
# RESOURCE TYPE MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

RESOURCE_TYPES = {
    "Yojana": fetch_yojana_summaries,
    "Kurukshetra": fetch_kurukshetra_summaries,
    "Economic Survey": fetch_economic_survey_summaries,
    "Budget": fetch_budget_summaries,
    "India Yearbook": fetch_india_yearbook_summaries,
}

def get_all_resource_types() -> List[str]:
    """Get all available resource types"""
    return list(RESOURCE_TYPES.keys())

def get_resource_info(resource_type: str) -> Dict:
    """Get information about a resource type including URLs"""
    if resource_type in RESOURCE_URLS:
        return RESOURCE_URLS[resource_type]
    return None
