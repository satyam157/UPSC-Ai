#!/usr/bin/env python3
"""
URL Content Fetcher & Summarizer with Coaching Institute Integration
Fetches content from coaching institutes and generates crisp UPSC-relevant summaries
"""

import requests
from bs4 import BeautifulSoup
from llm import ask_llm
from urllib.parse import urljoin
import time

# Coaching institute URLs (most reliable sources)
COACHING_INSTITUTES = {
    "Next IAS": "https://nextias.com",
    "Vision IAS": "https://visionias.in",
    "Forum IAS": "https://forumias.com",
    "Vajiram & Ravi": "https://vajiramandrav.com"
}

class URLSummarizer:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        self.timeout = 10
    
    def fetch_article(self, url):
        """
        Fetch article content from URL with better error handling
        Returns: (title, content, source, error_message)
        """
        try:
            # Ensure URL has protocol
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            # Identify source coaching institute
            source = "Unknown"
            for institute, base_url in COACHING_INSTITUTES.items():
                if base_url in url:
                    source = institute
                    break
            
            response = requests.get(url, headers=self.headers, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()
            
            # Check if response is too short
            if len(response.content) < 1000:
                return None, None, source, f"⚠️ Page content too short - likely a list/index page"
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove unwanted elements
            for tag in soup(['script', 'style', 'nav', 'footer', 'ads', 'sidebar']):
                tag.decompose()
            
            # Get title
            title = None
            if soup.find('h1'):
                title = soup.find('h1').get_text(strip=True)
            elif soup.find('title'):
                title = soup.find('title').get_text(strip=True)
                title = title.split('|')[0].strip()  # Remove extra | suffixes
            else:
                title = "Coaching Material - No Title"
            
            # Get main content - try multiple strategies
            content_sections = []
            
            # Strategy 1: Look for article containers
            article_div = (
                soup.find('article') or 
                soup.find('main') or 
                soup.find(attrs={'class': ['content', 'post-content', 'article-content', 'entry-content', 'article-body', 'course-content']}) or
                soup.find(attrs={'id': ['content', 'post', 'article', 'main-content', 'post-body']})
            )
            
            if article_div:
                paragraphs = article_div.find_all(['p', 'li', 'div'], recursive=True)
            else:
                # Fallback: Get all paragraphs
                paragraphs = soup.find_all('p')
            
            # Extract and filter content
            for para in paragraphs:
                text = para.get_text(strip=True)
                if len(text) > 30:  # Only meaningful paragraphs
                    content_sections.append(text)
            
            content = '\n\n'.join(content_sections[:20])  # Limit to first 20 paragraphs
            
            if len(content) < 500:
                return None, None, source, f"⚠️ Insufficient content extracted - try a different URL"
            
            return title, content[:11000], source, None  # Limit to 11000 chars (~3000-3500 tokens)
        
        except requests.exceptions.Timeout:
            return None, None, "Unknown", f"⏱️ Timeout fetching URL (>{self.timeout}s) - try again or use different URL"
        except requests.exceptions.ConnectionError:
            return None, None, "Unknown", f"🔗 Connection refused - website may be down or blocking automated access"
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None, None, "Unknown", f"❌ Page not found (404) - URL may be broken"
            else:
                return None, None, "Unknown", f"❌ HTTP Error {e.response.status_code}"
        except Exception as e:
            return None, None, "Unknown", f"❌ Error: {str(e)[:100]}"
    
    def generate_summary(self, title, content, source="Unknown"):
        """
        Generate crisp UPSC-relevant summary with NCERT connections
        Returns: (summary_with_ncert, error_message)
        """
        try:
            prompt = f"""You are an expert UPSC coach. Create SHORT, CRISP, EXAM-FOCUSED summary with NCERT links.

**Article:** {title}
**Source:** {source}
**Content:** {content}

**OUTPUT FORMAT (STRICT):**

---

**TL;DR:** [1 sentence essence]

**📌 What is it?**
[1-2 lines maximum, simple explanation]

**🎯 Key Facts**
• [Fact 1 with numbers/dates]
• [Fact 2]
• [Fact 3]
(Max 3 bullets)

**📚 NCERT Link**
Class [X] [Subject] → Chapter: [Name]
Connection: [1-2 lines how it connects]

**🏛️ UPSC Angle**
GS [Paper]: [Why it matters - 2 lines max]

**💾 Remember**
→ [One key takeaway]
→ [One date/number/name]
→ [One practical application]

---

**RULE: MAX 250 WORDS. SHORT SENTENCES. NO JARGON.**"""

            summary = ask_llm(prompt)
            return summary, None
        
        except Exception as e:
            return None, f"❌ Error generating summary: {str(e)[:150]}"
    
    def summarize_url(self, url):
        """
        Complete flow: Fetch URL → Generate Summary with NCERT
        Returns: (title, summary_with_ncert, source, error_message)
        """
        title, content, source, fetch_error = self.fetch_article(url)
        
        if fetch_error:
            return None, None, source, fetch_error
        
        summary, summary_error = self.generate_summary(title, content, source)
        
        if summary_error:
            return title, None, source, summary_error
        
        return title, summary, source, None


def fetch_and_summarize_urls(urls_list):
    """
    Fetch and summarize multiple URLs (teaching resource articles)
    urls_list: list of URLs from coaching institutes
    Returns: list of (url, title, summary_with_ncert, source, error)
    """
    summarizer = URLSummarizer()
    results = []
    
    for idx, url in enumerate(urls_list):
        try:
            # Ensure URL has protocol
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            
            title, summary, source, error = summarizer.summarize_url(url)
            
            if error:
                results.append((url, None, None, "Unknown", error))
            else:
                results.append((url, title, summary, source, None))
        
        except Exception as e:
            results.append((url, None, None, "Unknown", f"❌ Unexpected error: {str(e)[:100]}"))
        
        # Rate limiting - don't hammer servers
        if idx < len(urls_list) - 1:
            time.sleep(1)
    
    return results
