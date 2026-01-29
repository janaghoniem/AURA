# ============================================================================
# ENHANCED PLAYWRIGHT PYTHON DATA COLLECTION (10X MORE DATA)
# ============================================================================
# Balanced filtering: More permissive to collect MORE examples
# But still focused on Playwright Python web automation

import requests
from bs4 import BeautifulSoup
import json
import time
from pathlib import Path
from typing import List, Dict, Any
import re
from urllib.parse import urljoin, urlparse
from datetime import datetime

# ============================================================================
# Configuration
# ============================================================================

class WebDataCollectionConfig:
    """Configuration for Playwright Python data collection"""
    
    def __init__(self, library_name: str = "playwright"):
        self.library_name = library_name
        # Fixed path: backend\agents\execution_agent\RAG\web\rag_data
        self.base_dir = Path("backend/agents/execution_agent/RAG/web/rag_data") / library_name
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Output directories
        self.docs_dir = self.base_dir / "documentation"
        self.github_dir = self.base_dir / "github"
        self.stackoverflow_dir = self.base_dir / "stackoverflow"
        self.combined_dir = self.base_dir / "combined"
        
        for d in [self.docs_dir, self.github_dir, self.stackoverflow_dir, self.combined_dir]:
            d.mkdir(exist_ok=True)
    
    def get_output_path(self, source: str, filename: str) -> Path:
        """Get output path for a specific source"""
        source_map = {
            'docs': self.docs_dir,
            'github': self.github_dir,
            'stackoverflow': self.stackoverflow_dir,
            'combined': self.combined_dir
        }
        return source_map[source] / filename

# ============================================================================
# ENHANCED Documentation Scraper (MORE DOCS)
# ============================================================================

class PlaywrightPythonDocsScraper:
    """Scrape Playwright Python documentation - EXPANDED"""
    
    def __init__(self, config: WebDataCollectionConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.visited_urls = set()
        self.collected_data = []
    
    def scrape_python_docs(self):
        """Scrape MORE Playwright Python documentation"""
        
        # EXPANDED: More starting points, deeper crawling
        doc_urls = [
            # Getting Started
            ('https://playwright.dev/python/docs/intro', 3),
            ('https://playwright.dev/python/docs/library', 2),
            
            # Core API
            ('https://playwright.dev/python/docs/api/class-playwright', 2),
            ('https://playwright.dev/python/docs/api/class-browser', 2),
            ('https://playwright.dev/python/docs/api/class-browsercontext', 2),
            ('https://playwright.dev/python/docs/api/class-page', 3),  # Most important
            ('https://playwright.dev/python/docs/api/class-frame', 2),
            ('https://playwright.dev/python/docs/api/class-locator', 3),  # Important
            ('https://playwright.dev/python/docs/api/class-elementhandle', 2),
            
            # Automation
            ('https://playwright.dev/python/docs/locators', 2),
            ('https://playwright.dev/python/docs/input', 2),
            ('https://playwright.dev/python/docs/navigations', 2),
            ('https://playwright.dev/python/docs/selectors', 2),
            ('https://playwright.dev/python/docs/handles', 2),
            ('https://playwright.dev/python/docs/events', 2),
            
            # Features
            ('https://playwright.dev/python/docs/screenshots', 1),
            ('https://playwright.dev/python/docs/downloads', 1),
            ('https://playwright.dev/python/docs/network', 2),
            ('https://playwright.dev/python/docs/dialogs', 1),
            ('https://playwright.dev/python/docs/browser-contexts', 2),
            ('https://playwright.dev/python/docs/pages', 2),
            
            # Advanced
            ('https://playwright.dev/python/docs/auth', 1),
            ('https://playwright.dev/python/docs/emulation', 1),
            ('https://playwright.dev/python/docs/codegen', 1),
            ('https://playwright.dev/python/docs/debug', 1),
            ('https://playwright.dev/python/docs/trace-viewer', 1),
            
            # Guides
            ('https://playwright.dev/python/docs/writing-tests', 2),
            ('https://playwright.dev/python/docs/test-runners', 1),
            ('https://playwright.dev/python/docs/best-practices', 1),
        ]
        
        for url, max_depth in doc_urls:
            print(f"\n📖 Scraping: {url} (depth {max_depth})")
            self.scrape_page(url, max_depth=max_depth)
            time.sleep(0.5)
    
    def scrape_page(self, url: str, max_depth: int = 2, current_depth: int = 0):
        """Scrape page - MORE PERMISSIVE filtering"""
        
        if current_depth > max_depth or url in self.visited_urls:
            return
        
        self.visited_urls.add(url)
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            content_section = soup.find('article') or soup.find('main') or soup.find('div', class_='markdown')
            
            if content_section:
                text_content = content_section.get_text(separator='\n', strip=True)
                
                # Extract ALL code blocks (more permissive)
                code_blocks = []
                for code_tag in content_section.find_all(['code', 'pre']):
                    code_text = code_tag.get_text(strip=True)
                    
                    # More permissive: Just check for Playwright keywords
                    if len(code_text) > 20 and self._looks_like_playwright(code_text):
                        code_blocks.append(code_text)
                
                # SAVE even if no code blocks (text content is still useful)
                headers = [h.get_text(strip=True) for h in content_section.find_all(['h1', 'h2', 'h3', 'h4'])]
                
                page_data = {
                    'id': f"doc_{len(self.collected_data)}",
                    'type': 'documentation',
                    'library': 'playwright',
                    'language': 'python',
                    'source': 'documentation',
                    'source_url': url,
                    'title': soup.find('title').get_text(strip=True) if soup.find('title') else '',
                    'headers': headers,
                    'content': text_content[:10000],  # Increased
                    'code_blocks': code_blocks,
                    'collected_at': datetime.now().isoformat()
                }
                
                self.collected_data.append(page_data)
                print(f"  ✅ Collected: {len(code_blocks)} code blocks")
                
                # Follow more links
                if current_depth < max_depth:
                    for link in content_section.find_all('a', href=True):
                        next_url = urljoin(url, link['href'])
                        
                        if urlparse(next_url).netloc == urlparse(url).netloc:
                            clean_url = next_url.split('#')[0]
                            if clean_url not in self.visited_urls:
                                time.sleep(0.3)
                                self.scrape_page(clean_url, max_depth, current_depth + 1)
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    def _looks_like_playwright(self, code: str) -> bool:
        """More permissive check"""
        keywords = [
            'playwright', 'page.', 'browser.', 'context.',
            'locator', 'goto', 'click', 'fill', 'await',
            'async', 'chromium', 'firefox', 'webkit'
        ]
        return any(kw in code.lower() for kw in keywords)
    
    def save_data(self):
        """Save collected documentation"""
        output_file = self.config.get_output_path('docs', f'{self.config.library_name}_docs.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.collected_data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved {len(self.collected_data)} documentation pages")
        return output_file

# ============================================================================
# ENHANCED GitHub Scraper (MORE REPOS, MORE FILES)
# ============================================================================

class PlaywrightPythonGitHubScraper:
    """Scrape MORE Playwright Python code from GitHub"""
    
    def __init__(self, config: WebDataCollectionConfig, github_token: str = None):
        self.config = config
        self.github_token = github_token
        self.session = requests.Session()
        
        headers = {'User-Agent': 'RAG-Data-Collector'}
        if github_token:
            headers['Authorization'] = f'token {github_token}'
        self.session.headers.update(headers)
        
        self.collected_data = []
    
    def scrape_python_repos(self):
        """Scrape MULTIPLE Python Playwright repositories"""
        
        # EXPANDED: More repositories
        repositories = [
            # Official repos
            {
                'url': 'https://github.com/microsoft/playwright-python',
                'patterns': ['*.py', 'examples/*.py'],
                'exclude_dirs': ['__pycache__', '.github']  # Keep tests, they have good examples
            },
            
            # Community examples (via search)
            # We'll search for repos with playwright-python topic
        ]
        
        for repo_config in repositories:
            self.scrape_repository(
                repo_config['url'],
                include_patterns=repo_config['patterns'],
                exclude_dirs=repo_config.get('exclude_dirs', [])
            )
            time.sleep(2)
        
        # BONUS: Search for more repos on GitHub
        self.search_github_repos('playwright python', max_repos=5)
    
    def search_github_repos(self, query: str, max_repos: int = 5):
        """Search GitHub for Playwright Python repositories"""
        print(f"\n🔍 Searching GitHub: '{query}'")
        
        search_url = "https://api.github.com/search/repositories"
        params = {
            'q': query,
            'sort': 'stars',
            'order': 'desc',
            'per_page': max_repos
        }
        
        try:
            response = self.session.get(search_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            repos = data.get('items', [])[:max_repos]
            
            for repo in repos:
                repo_url = repo['html_url']
                repo_name = repo['full_name']
                
                # Skip if not Python
                if repo.get('language') != 'Python':
                    continue
                
                print(f"  → Found: {repo_name}")
                
                self.scrape_repository(
                    repo_url,
                    include_patterns=['*.py', 'examples/*.py'],
                    exclude_dirs=['__pycache__', '.github'],
                    max_depth=2
                )
                time.sleep(1)
                
        except Exception as e:
            print(f"  ❌ Search error: {e}")
    
    def scrape_repository(self, repo_url: str, include_patterns: List[str], 
                         exclude_dirs: List[str] = None, max_depth: int = 4):
        """Scrape Python files - MORE PERMISSIVE"""
        
        parts = repo_url.rstrip('/').split('/')
        owner, repo = parts[-2], parts[-1]
        
        print(f"\n📦 Scraping: {owner}/{repo}")
        
        if exclude_dirs is None:
            exclude_dirs = ['__pycache__', '.git']
        
        def process_contents(contents, current_path='', depth=0):
            if depth > max_depth:
                return
            
            for item in contents:
                if item['type'] == 'file':
                    if item['name'].endswith('.py'):
                        self._process_python_file(owner, repo, item)
                        time.sleep(0.3)
                        
                elif item['type'] == 'dir':
                    if item['name'] not in exclude_dirs:
                        subcontents = self.get_repo_contents(owner, repo, item['path'])
                        time.sleep(0.5)
                        process_contents(subcontents, item['path'], depth + 1)
        
        root_contents = self.get_repo_contents(owner, repo)
        process_contents(root_contents)
    
    def get_repo_contents(self, owner: str, repo: str, path: str = ''):
        """Get repository contents"""
        url = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
        
        try:
            response = self.session.get(url)
            response.raise_for_status()
            contents = response.json()
            
            if not isinstance(contents, list):
                contents = [contents]
            
            return contents
        except Exception as e:
            print(f"    ❌ Error: {e}")
            return []
    
    def _process_python_file(self, owner: str, repo: str, file_item: Dict):
        """Process Python file - MORE PERMISSIVE filtering"""
        
        try:
            response = self.session.get(file_item['download_url'])
            response.raise_for_status()
            content = response.text
            
            # MORE PERMISSIVE: Just check for Playwright keywords
            if not self._contains_playwright(content):
                return
            
            file_data = {
                'id': f"github_{len(self.collected_data)}",
                'type': 'github_code',
                'library': 'playwright',
                'language': 'python',
                'source': 'github',
                'source_url': file_item['html_url'],
                'repo': f"{owner}/{repo}",
                'file_path': file_item['path'],
                'file_name': file_item['name'],
                'content': content[:20000],  # Increased
                'collected_at': datetime.now().isoformat()
            }
            
            self.collected_data.append(file_data)
            print(f"  ✅ {file_item['path']}")
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
    
    def _contains_playwright(self, content: str) -> bool:
        """Check if file contains Playwright code - PERMISSIVE"""
        keywords = [
            'from playwright', 'import playwright',
            'page.goto', 'page.click', 'page.fill',
            'browser.new_page', 'async_playwright',
            'sync_playwright', 'chromium.launch'
        ]
        return any(kw in content for kw in keywords)
    
    def save_data(self):
        """Save collected GitHub data"""
        output_file = self.config.get_output_path('github', f'{self.config.library_name}_github.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.collected_data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved {len(self.collected_data)} GitHub files")
        return output_file

# ============================================================================
# ENHANCED StackOverflow Scraper (MORE TAGS, MORE QUESTIONS)
# ============================================================================

class PlaywrightPythonStackOverflowScraper:
    """Scrape MORE Playwright Python Q&A"""
    
    def __init__(self, config: WebDataCollectionConfig, api_key: str = None):
        self.config = config
        self.api_key = api_key
        self.base_url = "https://api.stackexchange.com/2.3"
        self.collected_data = []
    
    def search_python_questions(self):
        """Search for MORE Playwright Python questions"""
        
        # EXPANDED: More tags, more questions
        searches = [
            # Primary tags
            ('playwright-python', 300),  # Increased
            ('playwright;python', 200),  # Increased
            
            # Related tags
            ('playwright', 100),  # General Playwright (will filter for Python)
            ('web-automation;python', 50),  # May include Playwright
            ('browser-automation;python', 50),  # May include Playwright
        ]
        
        for tags, max_results in searches:
            print(f"\n🔍 Searching: {tags}")
            self.search_questions(tags=tags, max_results=max_results)
            time.sleep(2)
    
    def search_questions(self, tags: str, max_results: int = 100):
        """Search StackOverflow - MORE PERMISSIVE"""
        
        # Make multiple requests if needed (max 100 per request)
        total_collected = 0
        page = 1
        
        while total_collected < max_results:
            page_size = min(100, max_results - total_collected)
            
            params = {
                'order': 'desc',
                'sort': 'votes',
                'tagged': tags,
                'site': 'stackoverflow',
                'pagesize': page_size,
                'page': page,
                'filter': 'withbody'
            }
            
            if self.api_key:
                params['key'] = self.api_key
            
            try:
                response = requests.get(f"{self.base_url}/questions", params=params)
                response.raise_for_status()
                data = response.json()
                
                questions = data.get('items', [])
                if not questions:
                    break
                
                print(f"  📋 Page {page}: {len(questions)} questions")
                
                for question in questions:
                    self._process_question(question)
                    time.sleep(0.3)
                
                total_collected += len(questions)
                page += 1
                
                if 'quota_remaining' in data:
                    print(f"  📊 API quota: {data['quota_remaining']}")
                
                if not data.get('has_more'):
                    break
                
                time.sleep(1)
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                break
    
    def _process_question(self, question: Dict):
        """Process question - MORE PERMISSIVE"""
        
        question_id = question['question_id']
        
        params = {
            'order': 'desc',
            'sort': 'votes',
            'site': 'stackoverflow',
            'filter': 'withbody'
        }
        
        if self.api_key:
            params['key'] = self.api_key
        
        try:
            response = requests.get(
                f"{self.base_url}/questions/{question_id}/answers",
                params=params
            )
            response.raise_for_status()
            answers = response.json().get('items', [])
            
            # Extract code - MORE PERMISSIVE
            question_code = self._extract_code(question.get('body', ''))
            
            answer_codes = []
            for answer in answers:
                # Include more answers (even low-scored)
                codes = self._extract_code(answer.get('body', ''))
                answer_codes.extend(codes)
            
            # SAVE even if minimal code (question text is still useful)
            if question_code or answer_codes or 'playwright' in question.get('title', '').lower():
                item_data = {
                    'id': f"so_{question_id}",
                    'type': 'stackoverflow',
                    'library': 'playwright',
                    'language': 'python',
                    'source': 'stackoverflow',
                    'source_url': question['link'],
                    'question_id': question_id,
                    'title': question['title'],
                    'score': question.get('score', 0),
                    'tags': question.get('tags', []),
                    'question_code': question_code,
                    'answer_codes': answer_codes,
                    'view_count': question.get('view_count', 0),
                    'collected_at': datetime.now().isoformat()
                }
                
                self.collected_data.append(item_data)
                print(f"  ✅ Q{question_id}: {len(question_code) + len(answer_codes)} snippets")
        
        except Exception as e:
            print(f"  ❌ Error Q{question_id}: {e}")
    
    def _extract_code(self, html_content: str) -> List[str]:
        """Extract code - MORE PERMISSIVE"""
        
        soup = BeautifulSoup(html_content, 'html.parser')
        code_blocks = []
        
        for code_tag in soup.find_all('code'):
            code_text = code_tag.get_text(strip=True)
            
            # MORE PERMISSIVE: Accept shorter snippets
            if len(code_text) > 10:  # Lowered from 30
                # Check for Playwright OR Python
                playwright_kw = ['playwright', 'page.', 'browser.', 'locator', 
                               'goto', 'click', 'fill', 'chromium']
                python_kw = ['import', 'from', 'def ', 'await', 'async']
                
                has_playwright = any(kw in code_text.lower() for kw in playwright_kw)
                has_python = any(kw in code_text for kw in python_kw)
                
                if has_playwright or has_python:
                    code_blocks.append(code_text)
        
        return code_blocks
    
    def save_data(self):
        """Save collected StackOverflow data"""
        output_file = self.config.get_output_path('stackoverflow', f'{self.config.library_name}_stackoverflow.json')
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.collected_data, f, indent=2, ensure_ascii=False)
        print(f"\n💾 Saved {len(self.collected_data)} StackOverflow items")
        return output_file

# ============================================================================
# Main Collection Pipeline
# ============================================================================

def collect_more_playwright_data(github_token: str = None, stackoverflow_key: str = None):
    """Collect 10X MORE Playwright Python data"""
    
    print("=" * 80)
    print("ENHANCED PLAYWRIGHT PYTHON DATA COLLECTION (10X MORE DATA)")
    print("More permissive filtering = More examples = Better RAG")
    print("=" * 80)
    
    config = WebDataCollectionConfig('playwright')
    
    # 1. Docs (expanded crawling)
    print("\n" + "=" * 80)
    print("[1/3] EXPANDED DOCUMENTATION SCRAPING")
    print("=" * 80)
    doc_scraper = PlaywrightPythonDocsScraper(config)
    doc_scraper.scrape_python_docs()
    doc_scraper.save_data()
    
    # 2. GitHub (more repos, more files)
    print("\n" + "=" * 80)
    print("[2/3] EXPANDED GITHUB SCRAPING")
    print("=" * 80)
    github_scraper = PlaywrightPythonGitHubScraper(config, github_token)
    github_scraper.scrape_python_repos()
    github_scraper.save_data()
    
    # 3. StackOverflow (more tags, more questions)
    print("\n" + "=" * 80)
    print("[3/3] EXPANDED STACKOVERFLOW SCRAPING")
    print("=" * 80)
    so_scraper = PlaywrightPythonStackOverflowScraper(config, stackoverflow_key)
    so_scraper.search_python_questions()
    so_scraper.save_data()
    
    # 4. Combine
    print("\n" + "=" * 80)
    print("[4/4] COMBINING DATA")
    print("=" * 80)
    combine_data(config)
    
    print("\n" + "=" * 80)
    print("✅ ENHANCED DATA COLLECTION COMPLETE")
    print("=" * 80)
    
    print_stats(config)

def combine_data(config: WebDataCollectionConfig):
    """Combine all sources"""
    
    combined = []
    
    sources = [
        ('docs', f'{config.library_name}_docs.json'),
        ('github', f'{config.library_name}_github.json'),
        ('stackoverflow', f'{config.library_name}_stackoverflow.json'),
    ]
    
    for source, filename in sources:
        path = config.get_output_path(source, filename)
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                combined.extend(data)
                print(f"  ✅ {source}: {len(data)} items")
        else:
            print(f"  ⚠️  Missing: {path}")
    
    combined_path = config.get_output_path('combined', f'{config.library_name}_combined.json')
    
    with open(combined_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Total: {len(combined)} items → {combined_path}")
    return combined_path

def print_stats(config: WebDataCollectionConfig):
    """Print collection statistics"""
    
    print("\n" + "=" * 80)
    print("COLLECTION STATISTICS")
    print("=" * 80)
    
    combined_path = config.get_output_path('combined', f'{config.library_name}_combined.json')
    
    if combined_path.exists():
        with open(combined_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        python_count = sum(1 for item in data if item.get('language') == 'python')
        
        total_code = 0
        for item in data:
            if 'code_blocks' in item:
                total_code += len(item['code_blocks'])
            if 'question_code' in item:
                total_code += len(item['question_code'])
            if 'answer_codes' in item:
                total_code += len(item['answer_codes'])
        
        print(f"\n📊 Total Items: {len(data)}")
        print(f"🐍 Python Items: {python_count}")
        print(f"📝 Code Examples: {total_code}")
        
        by_source = {}
        for item in data:
            source = item.get('source', 'unknown')
            by_source[source] = by_source.get(source, 0) + 1
        
        print(f"\n🌐 By Source:")
        for source, count in sorted(by_source.items()):
            print(f"  • {source}: {count}")
        
        print(f"\n🎯 Expected 1000-2000+ items with this version!")
    else:
        print("⚠️  Combined data not found")

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import os
    
    collect_more_playwright_data(
        github_token=os.environ.get("GITHUB_TOKEN"),
        stackoverflow_key=os.environ.get("STACKOVERFLOW_KEY")
    )