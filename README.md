# Article Summarizer API

A FastAPI-based service that summarizes articles using OpenAI GPT models, with Neo4j graph database storage and a PHP frontend for easy integration.

## Features

- **FastAPI Backend**: RESTful API for article summarization
- **Neo4j Integration**: Graph database storage for articles, sources, and relationships
- **PHP Frontend**: Web interface for submitting URLs and viewing results
- **Multiple Models**: Support for various OpenAI GPT models
- **File Export**: Save summaries in TXT or CSV format
- **Token Tracking**: Monitor usage and costs
- **Git Integration**: Automatic commits for saved files
- **CORS Support**: Accessible from web applications
- **Graph Analytics**: Query articles by source, date, and relationships

## Setup

### Prerequisites

- Python 3.8+
- PHP 7.4+ with cURL extension
- OpenAI API key
- Neo4j Database (4.4+ or 5.0+)
- Git (optional, for file tracking)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd gpt-summarize
   ```

2. **Install Python dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up OpenAI API key**
   ```bash
   export OPENAI_API_KEY="your-api-key-here"
   ```

4. **Set up Neo4j database**
   ```bash
   # Set Neo4j environment variables
   export NEO4J_URI="bolt://localhost:7687"
   export NEO4J_USER="neo4j"
   export NEO4J_PASSWORD="your-password"
   export NEO4J_DATABASE="neo4j"
   ```

5. **Start the FastAPI server**
   ```bash
   python main-orig.py
   ```

The API will be available at `http://localhost:8000`

## Neo4j Setup

### Quick Start with Docker

```bash
# Pull and run Neo4j
docker run \
    --name neo4j \
    -p 7474:7474 -p 7687:7687 \
    -e NEO4J_AUTH=neo4j/password \
    -e NEO4J_PLUGINS='["apoc"]' \
    neo4j:5.15.0

# Access Neo4j Browser at http://localhost:7474
# Username: neo4j, Password: password
```

### Manual Installation

1. Download Neo4j from [neo4j.com](https://neo4j.com/download/)
2. Install and start the service
3. Set initial password
4. Update environment variables

## API Endpoints

### GET `/`
Root endpoint with API information and available endpoints.

### GET `/health`
Health check endpoint to verify API and Neo4j status.

### GET `/models`
Get available OpenAI models and pricing information.

### POST `/summarize`
Main endpoint for summarizing articles with optional Neo4j storage.

**Request Body:**
```json
{
  "urls": [
    "https://example.com/article1",
    "https://example.com/article2"
  ],
  "model": "gpt-4o-mini",
  "save_to_file": true,
  "output_format": "txt",
  "store_in_neo4j": true
}
```

### GET `/articles`
Retrieve articles from Neo4j with optional filters.

**Query Parameters:**
- `limit`: Maximum number of articles (default: 50)
- `source`: Filter by source name
- `date_from`: Filter by start date
- `date_to`: Filter by end date

### GET `/sources`
Get all unique sources with article counts.

### GET `/statistics`
Get summary statistics from Neo4j database.

### POST `/articles/query`
Advanced article querying with filters.

## Neo4j Data Model

The application creates a graph structure with:

- **Article nodes**: Store article metadata and summaries
- **Source nodes**: Represent publication sources
- **PUBLISHED_BY relationships**: Connect articles to sources

### Node Properties

**Article Node:**
- `url`: Unique article URL
- `headline`: Article headline
- `publication_date`: Publication date
- `summary`: AI-generated summary
- `tokens_used`: Token consumption
- `cost_usd`: Processing cost
- `processed_at`: Timestamp of processing

**Source Node:**
- `name`: Source name/domain
- `article_count`: Number of articles (calculated)

## PHP Frontend

The `php_example.php` file provides a complete web interface with:

- **Article Summarization**: Submit URLs for processing
- **Neo4j Data Viewer**: Browse stored articles, sources, and statistics
- **Real-time Updates**: View database content without page refresh
- **Filtering Options**: Query articles by various criteria

### Usage

1. Place `php_example.php` in your web server directory
2. Ensure the FastAPI backend and Neo4j are running
3. Access the PHP file through your web browser
4. Use the interface to summarize articles and view database content

## Configuration

### Environment Variables

- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `NEO4J_URI`: Neo4j connection URI (default: bolt://localhost:7687)
- `NEO4J_USER`: Neo4j username (default: neo4j)
- `NEO4J_PASSWORD`: Neo4j password (required)
- `NEO4J_DATABASE`: Neo4j database name (default: neo4j)
- `GITHUB_COMMIT_BRANCH`: Git branch for commits (default: "main")

### Model Pricing

The API includes built-in pricing for different OpenAI models:

- `gpt-5-nano`: $0.05/1M input, $0.40/1M output
- `gpt-4o-mini`: $0.15/1M input, $0.60/1M output
- `gpt-4o`: $2.50/1M input, $10.00/1M output

## File Output

### Text Format (.txt)
Human-readable format with clear separators and metadata.

### CSV Format (.csv)
Structured format suitable for spreadsheet applications.

Files are automatically named with timestamps: `summaries_YYYYMMDD_HHMMSS.{format}`

## Error Handling

The API includes comprehensive error handling:

- **Invalid URLs**: Rejected with appropriate error messages
- **Processing Errors**: Individual article failures don't stop batch processing
- **Neo4j Connection**: Graceful fallback if database is unavailable
- **Rate Limiting**: Maximum 10 URLs per request
- **Timeout Handling**: 5-minute timeout for processing requests

## Development

### Running in Development Mode

```bash
python main-orig.py
```

The server runs with auto-reload enabled for development.

### API Documentation

Interactive API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Testing

Test the API endpoints using curl:

```bash
# Health check
curl http://localhost:8000/health

# Get models
curl http://localhost:8000/models

# Summarize articles
curl -X POST http://localhost:8000/summarize \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://example.com/article"], "store_in_neo4j": true}'

# Get articles from Neo4j
curl http://localhost:8000/articles?limit=10

# Get statistics
curl http://localhost:8000/statistics
```

## Production Deployment

### Security Considerations

- Configure CORS origins properly for production
- Use environment variables for sensitive configuration
- Implement rate limiting and authentication if needed
- Use HTTPS in production
- Secure Neo4j database access

### Scaling

- The API can be deployed behind a reverse proxy (nginx, Apache)
- Use multiple worker processes with uvicorn
- Consider using Redis for caching if needed
- Neo4j can be clustered for high availability

## Troubleshooting

### Common Issues

1. **OpenAI API Key**: Ensure `OPENAI_API_KEY` is set correctly
2. **Neo4j Connection**: Check Neo4j service status and credentials
3. **Dependencies**: Install all requirements with `pip install -r requirements.txt`
4. **Port Conflicts**: Change ports if 8000 (FastAPI) or 7687 (Neo4j) are occupied
5. **CORS Issues**: Check CORS configuration for your domain

### Neo4j Issues

1. **Connection Refused**: Ensure Neo4j service is running
2. **Authentication Failed**: Verify username/password
3. **Database Not Found**: Check database name in environment variables
4. **Port Blocked**: Verify firewall settings for port 7687

### Logs

The API logs processing information to the console:
- Extracted publication dates and sources
- Token usage and costs
- Neo4j connection status
- Processing attempts and errors

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]
