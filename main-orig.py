import tiktoken
from openai import OpenAI
from newspaper import Article
import csv
from datetime import datetime
import os
import subprocess
import time
import re
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import json
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError

# Note: This script requires python-dateutil for better date parsing
# Install with: pip install python-dateutil fastapi uvicorn neo4j

# --- CONFIG ---
client = OpenAI()
model = "gpt-4o-mini"
LOG_FILE = "token_usage.csv"
GITHUB_COMMIT_BRANCH = "main"  # Change if your branch is different

# Neo4j Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

MODEL_PRICING = {
    "gpt-5-nano": {"input": 0.05, "output": 0.40},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "default": {"input": 1.00, "output": 1.00},
}

# Initialize FastAPI app
app = FastAPI(
    title="Article Summarizer API",
    description="API for summarizing articles using OpenAI GPT models with Neo4j storage",
    version="1.0.0"
)

# Add CORS middleware for PHP app access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- NEO4J CONNECTION ---
class Neo4jService:
    def __init__(self, uri, user, password, database):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self.driver = None
        
    def connect(self):
        try:
            self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            # Test connection
            with self.driver.session(database=self.database) as session:
                result = session.run("RETURN 1 as test")
                result.single()
            print("✓ Connected to Neo4j successfully")
            return True
        except (ServiceUnavailable, AuthError) as e:
            print(f"✗ Neo4j connection failed: {e}")
            return False
        except Exception as e:
            print(f"✗ Unexpected Neo4j error: {e}")
            return False
    
    def close(self):
        if self.driver:
            self.driver.close()
    
    def create_constraints_and_indexes(self):
        """Create constraints and indexes for better performance"""
        try:
            with self.driver.session(database=self.database) as session:
                # Create constraints
                session.run("CREATE CONSTRAINT article_url IF NOT EXISTS FOR (a:Article) REQUIRE a.url IS UNIQUE")
                session.run("CREATE CONSTRAINT source_name IF NOT EXISTS FOR (s:Source) REQUIRE s.name IS UNIQUE")
                
                # Create indexes
                session.run("CREATE INDEX article_date IF NOT EXISTS FOR (a:Article) ON (a.publication_date)")
                session.run("CREATE INDEX article_headline IF NOT EXISTS FOR (a:Article) ON (a.headline)")
                
                print("✓ Neo4j constraints and indexes created")
        except Exception as e:
            print(f"⚠ Warning: Could not create constraints/indexes: {e}")
    
    def store_article(self, article_data):
        """Store article summary in Neo4j"""
        try:
            with self.driver.session(database=self.database) as session:
                # Create or merge article node
                article_query = """
                MERGE (a:Article {url: $url})
                SET a.headline = $headline,
                    a.publication_date = $publication_date,
                    a.summary = $summary,
                    a.tokens_used = $tokens_used,
                    a.cost_usd = $cost_usd,
                    a.processed_at = datetime()
                RETURN a
                """
                
                # Create or merge source node
                source_query = """
                MERGE (s:Source {name: $source_name})
                RETURN s
                """
                
                # Create relationship between article and source
                relationship_query = """
                MATCH (a:Article {url: $url})
                MATCH (s:Source {name: $source_name})
                MERGE (a)-[:PUBLISHED_BY]->(s)
                RETURN a, s
                """
                
                # Execute queries
                session.run(article_query, article_data)
                session.run(source_query, {"source_name": article_data["source"]})
                session.run(relationship_query, {
                    "url": article_data["url"],
                    "source_name": article_data["source"]
                })
                
                return True
        except Exception as e:
            print(f"✗ Error storing article in Neo4j: {e}")
            return False
    
    def get_articles(self, limit=50, source=None, date_from=None, date_to=None):
        """Retrieve articles from Neo4j with optional filters"""
        try:
            with self.driver.session(database=self.database) as session:
                query = """
                MATCH (a:Article)-[:PUBLISHED_BY]->(s:Source)
                """
                
                params = {}
                where_clauses = []
                
                if source:
                    where_clauses.append("s.name = $source")
                    params["source"] = source
                
                if date_from:
                    where_clauses.append("a.publication_date >= $date_from")
                    params["date_from"] = date_from
                
                if date_to:
                    where_clauses.append("a.publication_date <= $date_to")
                    params["date_to"] = date_to
                
                if where_clauses:
                    query += " WHERE " + " AND ".join(where_clauses)
                
                query += """
                RETURN a.url as url, a.headline as headline, a.publication_date as publication_date,
                       a.summary as summary, a.tokens_used as tokens_used, a.cost_usd as cost_usd,
                       s.name as source, a.processed_at as processed_at
                ORDER BY a.processed_at DESC
                LIMIT $limit
                """
                params["limit"] = limit
                
                result = session.run(query, params)
                articles = [dict(record) for record in result]
                return articles
        except Exception as e:
            print(f"✗ Error retrieving articles from Neo4j: {e}")
            return []
    
    def get_sources(self):
        """Get all unique sources"""
        try:
            with self.driver.session(database=self.database) as session:
                query = """
                MATCH (s:Source)
                RETURN s.name as name, count((s)<-[:PUBLISHED_BY]-()) as article_count
                ORDER BY article_count DESC
                """
                result = session.run(query)
                sources = [dict(record) for record in result]
                return sources
        except Exception as e:
            print(f"✗ Error retrieving sources from Neo4j: {e}")
            return []
    
    def get_statistics(self):
        """Get summary statistics"""
        try:
            with self.driver.session(database=self.database) as session:
                query = """
                MATCH (a:Article)
                RETURN count(a) as total_articles,
                       sum(a.tokens_used) as total_tokens,
                       sum(a.cost_usd) as total_cost,
                       avg(a.cost_usd) as avg_cost_per_article
                """
                result = session.run(query)
                stats = result.single()
                return dict(stats) if stats else {}
        except Exception as e:
            print(f"✗ Error retrieving statistics from Neo4j: {e}")
            return {}

# Initialize Neo4j service
neo4j_service = Neo4jService(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, NEO4J_DATABASE)

# --- PYDANTIC MODELS ---
class SummarizeRequest(BaseModel):
    urls: List[str]
    model: Optional[str] = "gpt-4o-mini"
    save_to_file: Optional[bool] = False
    output_format: Optional[str] = "txt"
    store_in_neo4j: Optional[bool] = True

class SummarizeResponse(BaseModel):
    success: bool
    message: str
    data: Optional[dict] = None
    error: Optional[str] = None

class ArticleSummary(BaseModel):
    url: str
    headline: str
    publication_date: str
    source: str
    summary: str
    tokens_used: int
    cost_usd: float

class Neo4jQueryRequest(BaseModel):
    limit: Optional[int] = 50
    source: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None

# --- HELPERS ---
def fetch_article_text(url: str) -> tuple[str, str, str, str]:
    """Fetch and clean main article text, publication date, source, and headline using newspaper4k."""
    article = Article(url)
    article.download()
    article.parse()
    
    # Try multiple methods to get the publication date
    pub_date = None
    
    # Method 1: Try to get the parsed publication date
    if article.publish_date:
        pub_date = article.publish_date.strftime("%b. %d, %Y")
    
    # Method 2: Try to get date from metadata
    if not pub_date and article.meta_data:
        meta_date = article.meta_data.get('date') or article.meta_data.get('pubdate')
        if meta_date:
            try:
                from dateutil import parser
                parsed_date = parser.parse(meta_date)
                pub_date = parsed_date.strftime("%b. %d, %Y")
            except:
                pass
    
    # Method 3: Try to get date from article text (look for common date patterns)
    if not pub_date:
        # Look for common date patterns in the first 1000 characters
        text_sample = article.text[:1000]
        date_patterns = [
            r'\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4}\b',
            r'\b\d{1,2}/\d{1,2}/\d{4}\b',
            r'\b\d{1,2}-\d{1,2}-\d{4}\b',
            r'\b\d{4}-\d{1,2}-\d{1,2}\b'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text_sample, re.IGNORECASE)
            if match:
                try:
                    from dateutil import parser
                    parsed_date = parser.parse(match.group())
                    pub_date = parsed_date.strftime("%b. %d, %Y")
                    break
                except:
                    continue
    
    # Method 4: Use current date as fallback if all else fails
    if not pub_date:
        from datetime import datetime
        pub_date = datetime.now().strftime("%b. %d, %Y")
        print(f"Warning: Could not extract publication date from {url}, using current date")
    
    # Extract headline from the article
    headline = article.title.strip() if article.title else "No headline available"
    
    # Extract source from URL domain
    from urllib.parse import urlparse
    parsed_url = urlparse(url)
    source = parsed_url.netloc
    
    # Clean up the source (remove www. prefix and get the main domain)
    if source.startswith('www.'):
        source = source[4:]
    
    # Handle common cases where we want the main domain, not subdomains
    # For example: "news.ithacavoice.com" -> "ithacavoice.com"
    if source.count('.') > 1:
        parts = source.split('.')
        if len(parts) >= 2:
            source = '.'.join(parts[-2:])
    
    return article.text.strip(), pub_date, source, headline

def count_tokens(text: str, model: str) -> int:
    encoding = tiktoken.encoding_for_model(model)
    return len(encoding.encode(text))

def estimate_cost(model: str, prompt_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
    input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost

def log_usage(model: str, prompt_tokens: int, output_tokens: int, total_tokens: int, cost_usd: float):
    """Append token usage + cost to CSV."""
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "model", "prompt_tokens", "output_tokens", "total_tokens", "cost_usd"])
        writer.writerow([
            datetime.utcnow().isoformat(),
            model,
            prompt_tokens,
            output_tokens,
            total_tokens,
            round(cost_usd, 6)
        ])
    print(f"Logged token usage to {LOG_FILE}")

def git_push_commit(file_path: str, commit_message: str):
    """Stage, commit, and push a file using local Git CLI."""
    try:
        subprocess.run(["git", "add", file_path], check=True)
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push", "origin", GITHUB_COMMIT_BRANCH], check=True)
        print(f"Changes pushed to GitHub: {commit_message}")
    except subprocess.CalledProcessError as e:
        print(f"Git push failed: {e}")

def save_summaries_to_file(results: dict, filename: str = None, format: str = "txt"):
    """Save summaries to a file in the specified format."""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"summaries_{timestamp}.{format}"
    
    try:
        if format.lower() == "csv":
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Article Number", "URL", "Headline", "Publication Date", "Source", "Summary"])
                for i, (url, data) in enumerate(results.items(), 1):
                    writer.writerow([f"Article {i}", url, data['headline'], data['publication_date'], data['source'], data['summary']])
        else:  # txt format
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"ARTICLE SUMMARIES - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("="*80 + "\n\n")
                
                for i, (url, data) in enumerate(results.items(), 1):
                    f.write(f"ARTICLE {i}\n")
                    f.write(f"URL: {url}\n")
                    f.write(f"Headline: {data['headline']}\n")
                    f.write(f"Publication Date: {data['publication_date']}\n")
                    f.write(f"Source: {data['source']}\n")
                    f.write("-"*60 + "\n")
                    f.write(data['summary'] + "\n\n")
        
        print(f"✓ Summaries saved to: {filename}")
        return filename
    except Exception as e:
        print(f"✗ Error saving to file: {str(e)}")
        return None

# --- MAIN FUNCTION ---
def summarize_article(url: str, model_name: str = "gpt-4o-mini", retries: int = 2) -> dict:
    """Fetch article, summarize, retry if summary is empty."""
    try:
        article_text, pub_date, source, headline = fetch_article_text(url)
        
        print(f"Extracted publication date: {pub_date}")
        print(f"Extracted source: {source}")
        print(f"Extracted headline: {headline}")

        messages = [
            {"role": "system", "content": """
Style: Write in AP style. Be concise, factual, and avoid opinion or interpretation.

Length: Summaries must be 3 paragraphs. Each paragraph should be 2–4 sentences. Each summary must begin with the article's published date in AP date format (e.g., Feb. 21, 2025).

Tone: Neutral and professional. Do not insert analysis, speculation, or commentary.

Content: Capture the main developments, essential context, and key quotes or statistics if available. Avoid minor details or redundancy.

Headline: Use the exact headline provided in the prompt for the article and place it at the top of the summary.

Sources: At the end of every summary, include a source line crediting the publisher.
- Use the exact source provided in the prompt.
- Do not invent sources. Do not omit sources.
- Always output in plain text, not markdown or hyperlinks.
"""},

            {"role": "user", "content": (
                f"Summarize the following article in 3 concise paragraphs under 250 words. "
                f"The summary must begin with the publication date: {pub_date}, "
                f"include the headline at the top: {headline}, "
                f"and a source line crediting: {source}\n\n{article_text}"
            )}
        ]

        for attempt in range(retries + 1):
            prompt_tokens = sum(count_tokens(m["content"], model_name) for m in messages)

            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                temperature=0.3,
                max_completion_tokens=1000
            )

            summary = response.choices[0].message.content.strip()
            output_tokens = count_tokens(summary, model_name)
            total_tokens = prompt_tokens + output_tokens
            cost_usd = estimate_cost(model_name, prompt_tokens, output_tokens)

            log_usage(model_name, prompt_tokens, output_tokens, total_tokens, cost_usd)

            print(f"Attempt {attempt+1} - Input: {prompt_tokens}, Output: {output_tokens}, Total: {total_tokens}, Cost: ${cost_usd:.6f}")

            if summary:
                return {
                    "headline": headline,
                    "publication_date": pub_date,
                    "source": source,
                    "summary": summary,
                    "tokens_used": total_tokens,
                    "cost_usd": cost_usd
                }
            else:
                print("Summary was empty, retrying...")
                time.sleep(1)  # brief pause before retry

        return {"error": "Summary could not be generated after multiple attempts."}
    
    except Exception as e:
        return {"error": f"Error processing article: {str(e)}"}

# --- API ENDPOINTS ---
@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Article Summarizer API with Neo4j Storage",
        "version": "1.0.0",
        "endpoints": {
            "/summarize": "POST - Summarize multiple articles",
            "/articles": "GET - Retrieve articles from Neo4j",
            "/sources": "GET - Get all sources",
            "/statistics": "GET - Get summary statistics",
            "/health": "GET - Health check",
            "/models": "GET - Available models and pricing"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    neo4j_status = "connected" if neo4j_service.connect() else "disconnected"
    return {
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "neo4j": neo4j_status
    }

@app.get("/models")
async def get_models():
    """Get available models and pricing information."""
    return {
        "available_models": list(MODEL_PRICING.keys()),
        "pricing": MODEL_PRICING,
        "default_model": model
    }

@app.post("/summarize", response_model=SummarizeResponse)
async def summarize_articles(request: SummarizeRequest, background_tasks: BackgroundTasks):
    """Summarize multiple articles from URLs."""
    try:
        if not request.urls:
            raise HTTPException(status_code=400, detail="No URLs provided")
        
        if len(request.urls) > 10:  # Limit to prevent abuse
            raise HTTPException(status_code=400, detail="Maximum 10 URLs allowed per request")
        
        results = {}
        total_cost = 0
        total_tokens = 0
        
        for url in request.urls:
            if not url.startswith(('http://', 'https://')):
                results[url] = {"error": "Invalid URL format"}
                continue
            
            print(f"\nProcessing: {url}")
            result = summarize_article(url, request.model)
            
            if "error" not in result:
                total_cost += result["cost_usd"]
                total_tokens += result["tokens_used"]
                
                # Store in Neo4j if requested
                if request.store_in_neo4j:
                    article_data = {
                        "url": url,
                        "headline": result["headline"],
                        "publication_date": result["publication_date"],
                        "source": result["source"],
                        "summary": result["summary"],
                        "tokens_used": result["tokens_used"],
                        "cost_usd": result["cost_usd"]
                    }
                    neo4j_service.store_article(article_data)
            
            results[url] = result
        
        # Save to file if requested
        saved_file = None
        if request.save_to_file:
            saved_file = save_summaries_to_file(results, format=request.output_format)
        
        # Log git commit if file was saved
        if saved_file:
            background_tasks.add_task(git_push_commit, saved_file, f"Update summaries file: {saved_file}")
        
        return SummarizeResponse(
            success=True,
            message=f"Successfully processed {len(request.urls)} articles",
            data={
                "summaries": results,
                "total_cost_usd": round(total_cost, 6),
                "total_tokens": total_tokens,
                "saved_file": saved_file,
                "stored_in_neo4j": request.store_in_neo4j
            }
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/articles")
async def get_articles(
    limit: int = 50,
    source: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
):
    """Retrieve articles from Neo4j with optional filters."""
    try:
        articles = neo4j_service.get_articles(limit, source, date_from, date_to)
        return {
            "success": True,
            "count": len(articles),
            "articles": articles
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving articles: {str(e)}")

@app.get("/sources")
async def get_sources():
    """Get all unique sources with article counts."""
    try:
        sources = neo4j_service.get_sources()
        return {
            "success": True,
            "count": len(sources),
            "sources": sources
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving sources: {str(e)}")

@app.get("/statistics")
async def get_statistics():
    """Get summary statistics from Neo4j."""
    try:
        stats = neo4j_service.get_statistics()
        return {
            "success": True,
            "statistics": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving statistics: {str(e)}")

@app.post("/articles/query")
async def query_articles(request: Neo4jQueryRequest):
    """Query articles with advanced filters."""
    try:
        articles = neo4j_service.get_articles(
            request.limit,
            request.source,
            request.date_from,
            request.date_to
        )
        return {
            "success": True,
            "count": len(articles),
            "articles": articles
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying articles: {str(e)}")

# --- ENTRY POINT ---
if __name__ == "__main__":
    print("Starting Article Summarizer API with Neo4j...")
    
    # Initialize Neo4j connection
    if neo4j_service.connect():
        neo4j_service.create_constraints_and_indexes()
    else:
        print("⚠ Warning: Neo4j connection failed. Some features may not work.")
    
    print("API will be available at: http://localhost:8000")
    print("Documentation available at: http://localhost:8000/docs")
    
    try:
        uvicorn.run(
            "main-orig:app",
            host="0.0.0.0",
            port=8000,
            reload=True
        )
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        neo4j_service.close()
        print("Neo4j connection closed.")
