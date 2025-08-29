import os
import requests
from transformers import pipeline
from git import Repo

# Summarization model
summarizer = pipeline("summarization", model="facebook/bart-large-cnn")

# Dictionary of article URLs
articles = {
    "BBC": "https://www.bbc.com/news/articles/cdx069we39xo",
    "CNN": "https://www.cnn.com/2025/08/21/world/climate-change-report/index.html",
    "Reuters": "https://www.reuters.com/world/europe/european-elections-2025-08-21/",
}

# Function to fetch article content (very simplified)
def fetch_article(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text[:4000]  # crude: truncate to avoid token overflow
    except Exception as e:
        return f"Error fetching {url}: {e}"

# Summarize articles
summaries = {}
for source, url in articles.items():
    content = fetch_article(url)
    if "Error fetching" not in content:
        summary = summarizer(content, max_length=200, min_length=150, do_sample=False)
        summaries[source] = summary[0]['summary_text']
    else:
        summaries[source] = content

# Save summaries to a markdown file
with open("summaries.md", "w", encoding="utf-8") as f:
    for source, summary in summaries.items():
        f.write(f"## {source}\n\n{summary}\n\n")

# Push changes to GitHub
repo_dir = os.getcwd()  # assumes script is in the repo
repo = Repo(repo_dir)

repo.git.add("summaries.md")
repo.index.commit("Add new article summaries")
origin = repo.remote(name="origin")
origin.push()

print("✅ Summaries saved and pushed to GitHub.")
