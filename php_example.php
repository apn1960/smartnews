<?php
/**
 * PHP Example for Article Summarizer API
 * This file demonstrates how to consume the FastAPI endpoints
 */

// ===== CONFIGURATION =====
// Update this to match your FastAPI server address
$FASTAPI_SERVER_URL = 'http://localhost:8000';  // Use localhost when both are on same server
// ========================

class ArticleSummarizerAPI {
    private $baseUrl;
    
    // Use localhost when FastAPI and PHP are on the same server
    // Change this only if you need to connect to a different server
    public function __construct($baseUrl = null) {
        global $FASTAPI_SERVER_URL;
        $this->baseUrl = $baseUrl ?: $FASTAPI_SERVER_URL;
    }
    
    /**
     * Make a GET request to the API
     */
    private function makeGetRequest($endpoint) {
        $url = $this->baseUrl . $endpoint;
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, 30);
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        
        if ($httpCode === 200) {
            return json_decode($response, true);
        } else {
            throw new Exception("HTTP Error: $httpCode - $response");
        }
    }
    
    /**
     * Make a POST request to the API
     */
    private function makePostRequest($endpoint, $data) {
        $url = $this->baseUrl . $endpoint;
        $jsonData = json_encode($data);
        
        $ch = curl_init();
        curl_setopt($ch, CURLOPT_URL, $url);
        curl_setopt($ch, CURLOPT_POST, true);
        curl_setopt($ch, CURLOPT_POSTFIELDS, $jsonData);
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
        curl_setopt($ch, CURLOPT_TIMEOUT, 300); // 5 minutes for processing
        curl_setopt($ch, CURLOPT_HTTPHEADER, [
            'Content-Type: application/json',
            'Content-Length: ' . strlen($jsonData)
        ]);
        
        $response = curl_exec($ch);
        $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
        curl_close($ch);
        
        if ($httpCode === 200) {
            return json_decode($response, true);
        } else {
            throw new Exception("HTTP Error: $httpCode - $response");
        }
    }
    
    /**
     * Get API health status
     */
    public function getHealth() {
        return $this->makeGetRequest('/health');
    }
    
    /**
     * Get available models and pricing
     */
    public function getModels() {
        return $this->makeGetRequest('/models');
    }
    
    /**
     * Summarize articles
     */
    public function summarizeArticles($urls, $model = 'gpt-4o-mini', $saveToFile = false, $outputFormat = 'txt') {
        $data = [
            'urls' => $urls,
            'model' => $model,
            'save_to_file' => $saveToFile,
            'output_format' => $outputFormat
        ];
        
        return $this->makePostRequest('/summarize', $data);
    }

    /**
     * Get articles from Neo4j database
     */
    public function getArticles($limit = 50, $source = null, $dateFrom = null, $dateTo = null) {
        $params = http_build_query([
            'limit' => $limit,
            'source' => $source,
            'date_from' => $dateFrom,
            'date_to' => $dateTo
        ]);
        
        return $this->makeGetRequest("/articles?$params");
    }
    
    /**
     * Get all sources from Neo4j database
     */
    public function getSources() {
        return $this->makeGetRequest('/sources');
    }
    
    /**
     * Get statistics from Neo4j database
     */
    public function getStatistics() {
        return $this->makeGetRequest('/statistics');
    }
    
    /**
     * Query articles with advanced filters
     */
    public function queryArticles($filters = []) {
        $data = [
            'limit' => $filters['limit'] ?? 50,
            'source' => $filters['source'] ?? null,
            'date_from' => $filters['date_from'] ?? null,
            'date_to' => $filters['date_to'] ?? null
        ];
        
        return $this->makePostRequest('/articles/query', $data);
    }
}

// Example usage
try {
    $api = new ArticleSummarizerAPI();
    
    // Check API health
    echo "=== API Health Check ===\n";
    $health = $api->getHealth();
    echo "Status: " . $health['status'] . "\n";
    echo "Timestamp: " . $health['timestamp'] . "\n\n";
    
    // Get available models
    echo "=== Available Models ===\n";
    $models = $api->getModels();
    echo "Default model: " . $models['default_model'] . "\n";
    echo "Available models: " . implode(', ', $models['available_models']) . "\n\n";
    
    // Example URLs to summarize
    $urls = [
        'https://example.com/article1',
        'https://example.com/article2'
    ];
    
    echo "=== Summarizing Articles ===\n";
    $result = $api->summarizeArticles($urls, 'gpt-4o-mini', true, 'txt');
    
    if ($result['success']) {
        echo "Message: " . $result['message'] . "\n";
        echo "Total cost: $" . $result['data']['total_cost_usd'] . "\n";
        echo "Total tokens: " . $result['data']['total_tokens'] . "\n";
        
        if ($result['data']['saved_file']) {
            echo "Saved to file: " . $result['data']['saved_file'] . "\n";
        }
        
        echo "\n=== Summaries ===\n";
        foreach ($result['data']['summaries'] as $url => $summary) {
            if (isset($summary['error'])) {
                echo "Error for $url: " . $summary['error'] . "\n";
            } else {
                echo "URL: $url\n";
                echo "Headline: " . $summary['headline'] . "\n";
                echo "Publication Date: " . $summary['publication_date'] . "\n";
                echo "Source: " . $summary['source'] . "\n";
                echo "Summary: " . $summary['summary'] . "\n";
                echo "Tokens used: " . $summary['tokens_used'] . "\n";
                echo "Cost: $" . $summary['cost_usd'] . "\n";
                echo "---\n";
            }
        }
    } else {
        echo "Error: " . $result['error'] . "\n";
    }
    
} catch (Exception $e) {
    echo "Error: " . $e->getMessage() . "\n";
}
?>

<!DOCTYPE html>
<html>
<head>
    <title>Article Summarizer - PHP Example</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .form-group { margin-bottom: 15px; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input[type="text"], textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        textarea { height: 100px; resize: vertical; }
        button { background: #007cba; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        button:hover { background: #005a87; }
        .results { margin-top: 20px; padding: 15px; background: #f5f5f5; border-radius: 4px; }
        .error { color: red; }
        .success { color: green; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Article Summarizer API - PHP Interface</h1>
        
        <form method="POST" action="">
            <div class="form-group">
                <label for="urls">Article URLs (one per line):</label>
                <textarea name="urls" id="urls" placeholder="https://example.com/article1&#10;https://example.com/article2"></textarea>
            </div>
            
            <div class="form-group">
                <label for="model">Model:</label>
                <input type="text" name="model" id="model" value="gpt-4o-mini">
            </div>
            
            <div class="form-group">
                <label>
                    <input type="checkbox" name="save_to_file" value="1"> Save to file
                </label>
            </div>
            
            <div class="form-group">
                <label for="output_format">Output Format:</label>
                <select name="output_format" id="output_format">
                    <option value="txt">Text (.txt)</option>
                    <option value="csv">CSV (.csv)</option>
                </select>
            </div>
            
            <button type="submit">Summarize Articles</button>
        </form>
        
        <!-- Neo4j Data Viewer -->
        <div style="margin-top: 40px;">
            <h2>Neo4j Database Viewer</h2>
            
            <div style="display: flex; gap: 20px; margin-bottom: 20px;">
                <button onclick="loadArticles()" style="background: #28a745;">View Articles</button>
                <button onclick="loadSources()" style="background: #17a2b8;">View Sources</button>
                <button onclick="loadStatistics()" style="background: #6f42c1;">View Statistics</button>
            </div>
            
            <div id="neo4j-results" style="margin-top: 20px;"></div>
        </div>
        
        <script>
            function loadArticles() {
                fetch('?action=articles')
                    .then(response => response.text())
                    .then(html => {
                        document.getElementById('neo4j-results').innerHTML = html;
                    });
            }
            
            function loadSources() {
                fetch('?action=sources')
                    .then(response => response.text())
                    .then(html => {
                        document.getElementById('neo4j-results').innerHTML = html;
                    });
            }
            
            function loadStatistics() {
                fetch('?action=statistics')
                    .then(response => response.text())
                    .then(html => {
                        document.getElementById('neo4j-results').innerHTML = html;
                    });
            }
        </script>
        
        <?php
        // Handle form submissions and Neo4j data requests
        if ($_POST || isset($_GET['action'])) {
            try {
                $api = new ArticleSummarizerAPI();
                
                // Handle Neo4j data requests
                if (isset($_GET['action'])) {
                    switch ($_GET['action']) {
                        case 'articles':
                            $articles = $api->getArticles();
                            if ($articles['success']) {
                                echo '<div class="results">';
                                echo '<h3>Articles in Database (' . $articles['count'] . ')</h3>';
                                foreach ($articles['articles'] as $article) {
                                    echo '<div style="margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 4px;">';
                                    echo '<p><strong>URL:</strong> ' . htmlspecialchars($article['url']) . '</p>';
                                    echo '<p><strong>Headline:</strong> ' . htmlspecialchars($article['headline']) . '</p>';
                                    echo '<p><strong>Publication Date:</strong> ' . htmlspecialchars($article['publication_date']) . '</p>';
                                    echo '<p><strong>Source:</strong> ' . htmlspecialchars($article['source']) . '</p>';
                                    echo '<p><strong>Summary:</strong></p>';
                                    echo '<div style="white-space: pre-wrap; background: white; padding: 10px; border-radius: 4px;">' . htmlspecialchars($article['summary']) . '</div>';
                                    echo '<p><strong>Tokens Used:</strong> ' . $article['tokens_used'] . '</p>';
                                    echo '<p><strong>Cost:</strong> $' . $article['cost_usd'] . '</p>';
                                    echo '<p><strong>Processed:</strong> ' . htmlspecialchars($article['processed_at']) . '</p>';
                                    echo '</div>';
                                }
                                echo '</div>';
                            } else {
                                echo '<div class="error">Error loading articles: ' . htmlspecialchars($articles['error'] ?? 'Unknown error') . '</div>';
                            }
                            break;
                            
                        case 'sources':
                            $sources = $api->getSources();
                            if ($sources['success']) {
                                echo '<div class="results">';
                                echo '<h3>Sources in Database (' . $sources['count'] . ')</h3>';
                                echo '<table style="width: 100%; border-collapse: collapse; margin-top: 15px;">';
                                echo '<tr style="background: #f8f9fa;"><th style="padding: 10px; border: 1px solid #ddd;">Source</th><th style="padding: 10px; border: 1px solid #ddd;">Article Count</th></tr>';
                                foreach ($sources['sources'] as $source) {
                                    echo '<tr>';
                                    echo '<td style="padding: 10px; border: 1px solid #ddd;">' . htmlspecialchars($source['name']) . '</td>';
                                    echo '<td style="padding: 10px; border: 1px solid #ddd; text-align: center;">' . $source['article_count'] . '</td>';
                                    echo '</tr>';
                                }
                                echo '</table>';
                                echo '</div>';
                            } else {
                                echo '<div class="error">Error loading sources: ' . htmlspecialchars($sources['error'] ?? 'Unknown error') . '</div>';
                            }
                            break;
                            
                        case 'statistics':
                            $stats = $api->getStatistics();
                            if ($stats['success']) {
                                echo '<div class="results">';
                                echo '<h3>Database Statistics</h3>';
                                echo '<div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-top: 15px;">';
                                echo '<div style="background: #e3f2fd; padding: 20px; border-radius: 8px; text-align: center;">';
                                echo '<h4>Total Articles</h4>';
                                echo '<p style="font-size: 2em; margin: 0; color: #1976d2;">' . number_format($stats['statistics']['total_articles'] ?? 0) . '</p>';
                                echo '</div>';
                                echo '<div style="background: #f3e5f5; padding: 20px; border-radius: 8px; text-align: center;">';
                                echo '<h4>Total Tokens</h4>';
                                echo '<p style="font-size: 2em; margin: 0; color: #7b1fa2;">' . number_format($stats['statistics']['total_tokens'] ?? 0) . '</p>';
                                echo '</div>';
                                echo '<div style="background: #e8f5e8; padding: 20px; border-radius: 8px; text-align: center;">';
                                echo '<h4>Total Cost</h4>';
                                echo '<p style="font-size: 2em; margin: 0; color: #388e3c;">$' . number_format($stats['statistics']['total_cost'] ?? 0, 6) . '</p>';
                                echo '</div>';
                                echo '<div style="background: #fff3e0; padding: 20px; border-radius: 8px; text-align: center;">';
                                echo '<h4>Avg Cost/Article</h4>';
                                echo '<p style="font-size: 2em; margin: 0; color: #f57c00;">$' . number_format($stats['statistics']['avg_cost_per_article'] ?? 0, 6) . '</p>';
                                echo '</div>';
                                echo '</div>';
                                echo '</div>';
                            } else {
                                echo '<div class="error">Error loading statistics: ' . htmlspecialchars($stats['error'] ?? 'Unknown error') . '</div>';
                            }
                            break;
                    }
                }
                
                // Handle form submissions for article summarization
                if ($_POST) {
                    $urls = array_filter(array_map('trim', explode("\n", $_POST['urls'])));
                    $model = $_POST['model'] ?? 'gpt-4o-mini';
                    $saveToFile = isset($_POST['save_to_file']);
                    $outputFormat = $_POST['output_format'] ?? 'txt';
                    
                    if (empty($urls)) {
                        echo '<div class="error">Please enter at least one URL.</div>';
                    } else {
                        $result = $api->summarizeArticles($urls, $model, $saveToFile, $outputFormat);
                        
                        if ($result['success']) {
                            echo '<div class="results">';
                            echo '<h3>Results</h3>';
                            echo '<p><strong>Message:</strong> ' . htmlspecialchars($result['message']) . '</p>';
                            echo '<p><strong>Total Cost:</strong> $' . $result['data']['total_cost_usd'] . '</p>';
                            echo '<p><strong>Total Tokens:</strong> ' . $result['data']['total_tokens'] . '</p>';
                            
                            if ($result['data']['saved_file']) {
                                echo '<p><strong>Saved to:</strong> ' . htmlspecialchars($result['data']['saved_file']) . '</p>';
                            }
                            
                            if ($result['data']['stored_in_neo4j']) {
                                echo '<p><strong>Stored in Neo4j:</strong> Yes</p>';
                            }
                            
                            echo '<h4>Summaries:</h4>';
                            foreach ($result['data']['summaries'] as $url => $summary) {
                                if (isset($summary['error'])) {
                                    echo '<div class="error"><strong>Error for ' . htmlspecialchars($url) . ':</strong> ' . htmlspecialchars($summary['error']) . '</div>';
                                } else {
                                    echo '<div style="margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 4px;">';
                                    echo '<p><strong>URL:</strong> ' . htmlspecialchars($url) . '</p>';
                                    echo '<p><strong>Headline:</strong> ' . htmlspecialchars($summary['headline']) . '</p>';
                                    echo '<p><strong>Publication Date:</strong> ' . htmlspecialchars($summary['publication_date']) . '</p>';
                                    echo '<p><strong>Source:</strong> ' . htmlspecialchars($summary['source']) . '</p>';
                                    echo '<p><strong>Summary:</strong></p>';
                                    echo '<div style="white-space: pre-wrap; background: white; padding: 10px; border-radius: 4px;">' . htmlspecialchars($summary['summary']) . '</div>';
                                    echo '<p><strong>Tokens Used:</strong> ' . $summary['tokens_used'] . '</p>';
                                    echo '<p><strong>Cost:</strong> $' . $summary['cost_usd'] . '</p>';
                                    echo '</div>';
                                }
                            }
                            echo '</div>';
                        } else {
                            echo '<div class="error">Error: ' . htmlspecialchars($result['error']) . '</div>';
                        }
                    }
                }
            } catch (Exception $e) {
                echo '<div class="error">Error: ' . htmlspecialchars($e->getMessage()) . '</div>';
            }
        }
        ?>
    </div>
</body>
</html>
