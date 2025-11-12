#!/bin/bash
#
# Test script for keyword search and one-time scraping
# This script creates a test keyword search and triggers a scrape
#

set -e

# Configuration
API_URL="${API_URL:-http://localhost:7101}"
API_KEY="${API_KEY:-dev_api_key}"
SEARCH_NAME="${SEARCH_NAME:-Test Search $(date +%s)}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check if API is reachable
check_api() {
    print_info "Checking API connectivity..."
    if curl -s -f "${API_URL}/health" > /dev/null 2>&1; then
        print_success "API is reachable"
        return 0
    else
        print_error "API is not reachable at ${API_URL}"
        print_info "Make sure the API is running: docker-compose up"
        exit 1
    fi
}

# Create a keyword search
create_search() {
    print_info "Creating keyword search: ${SEARCH_NAME}" >&2
    
    # Example: Search for freelance/gig opportunities
    # You can customize these keywords and subreddits
    SEARCH_DATA=$(cat <<EOF
{
  "name": "${SEARCH_NAME}",
  "keywords": [
    "looking for",
    "need a",
    "hiring",
    "freelance",
    "remote work"
  ],
  "patterns": [
    "looking for",
    "need someone",
    "hiring"
  ],
  "platforms": ["reddit"],
  "reddit_config": {
    "subreddits": ["forhire", "freelance"],
    "limit": 10,
    "include_comments": true,
    "sort": "new",
    "time_filter": "day"
  },
  "scraping_mode": "one_time",
  "enabled": true
}
EOF
)
    
    RESPONSE=$(curl -s -w "\n%{http_code}" \
        -X POST "${API_URL}/api/v1/keyword-searches" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: ${API_KEY}" \
        -d "${SEARCH_DATA}")
    
    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    
    if [ "$HTTP_CODE" -eq 201 ]; then
        SEARCH_ID=$(echo "$BODY" | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
        print_success "Keyword search created successfully" >&2
        print_info "Search ID: ${SEARCH_ID}" >&2
        echo "$SEARCH_ID"
    else
        print_error "Failed to create keyword search" >&2
        echo "HTTP Status: $HTTP_CODE" >&2
        echo "Response: $BODY" | jq '.' 2>/dev/null || echo "$BODY" >&2
        exit 1
    fi
}

# Trigger a one-time scrape
trigger_scrape() {
    local SEARCH_ID=$1
    print_info "Triggering one-time scrape for search: ${SEARCH_ID}"
    
    RESPONSE=$(curl -s -w "\n%{http_code}" \
        -X POST "${API_URL}/api/v1/keyword-searches/${SEARCH_ID}/scrape" \
        -H "X-API-Key: ${API_KEY}")
    
    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    
    if [ "$HTTP_CODE" -eq 200 ]; then
        print_success "Scrape triggered successfully"
        
        # Parse and display results
        if command -v jq &> /dev/null; then
            echo ""
            echo "Scrape Results:"
            echo "$BODY" | jq '.'
            
            POSTS_COUNT=$(echo "$BODY" | jq -r '.posts_scraped // 0')
            COMMENTS_COUNT=$(echo "$BODY" | jq -r '.comments_scraped // 0')
            LEADS_COUNT=$(echo "$BODY" | jq -r '.leads_found // 0')
            
            echo ""
            print_info "Summary:"
            echo "  - Posts scraped: ${POSTS_COUNT}"
            echo "  - Comments scraped: ${COMMENTS_COUNT}"
            echo "  - Leads found: ${LEADS_COUNT}"
        else
            echo "$BODY"
            print_warning "Install 'jq' for better output formatting: brew install jq"
        fi
    else
        print_error "Failed to trigger scrape"
        echo "HTTP Status: $HTTP_CODE"
        echo "Response: $BODY" | jq '.' 2>/dev/null || echo "$BODY"
        exit 1
    fi
}

# Get search status
get_status() {
    local SEARCH_ID=$1
    print_info "Getting search status..."
    
    RESPONSE=$(curl -s -w "\n%{http_code}" \
        -X GET "${API_URL}/api/v1/keyword-searches/${SEARCH_ID}/status" \
        -H "X-API-Key: ${API_KEY}")
    
    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    
    if [ "$HTTP_CODE" -eq 200 ]; then
        if command -v jq &> /dev/null; then
            echo ""
            echo "Search Status:"
            echo "$BODY" | jq '.'
        else
            echo "$BODY"
        fi
    else
        print_warning "Failed to get status (HTTP $HTTP_CODE)"
    fi
}

# List leads found
list_leads() {
    local SEARCH_ID=$1
    print_info "Listing leads found..."
    
    RESPONSE=$(curl -s -w "\n%{http_code}" \
        -X GET "${API_URL}/api/v1/leads?keyword_search_id=${SEARCH_ID}&limit=10" \
        -H "X-API-Key: ${API_KEY}")
    
    HTTP_CODE=$(echo "$RESPONSE" | tail -n1)
    BODY=$(echo "$RESPONSE" | sed '$d')
    
    if [ "$HTTP_CODE" -eq 200 ]; then
        if command -v jq &> /dev/null; then
            LEADS_COUNT=$(echo "$BODY" | jq 'length')
            print_success "Found ${LEADS_COUNT} lead(s)"
            if [ "$LEADS_COUNT" -gt 0 ]; then
                echo ""
                echo "$BODY" | jq '.[] | {id, title, score, source_url}' | head -20
            fi
        else
            echo "$BODY"
        fi
    else
        print_warning "Failed to list leads (HTTP $HTTP_CODE)"
    fi
}

# Delete the test search (optional cleanup)
delete_search() {
    local SEARCH_ID=$1
    if [ "${CLEANUP:-false}" = "true" ]; then
        print_info "Cleaning up test search..."
        HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
            -X DELETE "${API_URL}/api/v1/keyword-searches/${SEARCH_ID}" \
            -H "X-API-Key: ${API_KEY}")
        
        if [ "$HTTP_CODE" -eq 204 ]; then
            print_success "Test search deleted"
        else
            print_warning "Failed to delete search (HTTP $HTTP_CODE)"
        fi
    else
        print_info "Test search kept (set CLEANUP=true to auto-delete)"
    fi
}

# Main execution
main() {
    echo "========================================="
    echo "Rixly Keyword Search Test Script"
    echo "========================================="
    echo ""
    
    # Check API
    check_api
    
    # Create search
    SEARCH_ID=$(create_search)
    echo ""
    
    # Wait a moment for search to be ready
    sleep 1
    
    # Trigger scrape
    trigger_scrape "$SEARCH_ID"
    echo ""
    
    # Wait for scrape to complete (scraping can take time)
    print_info "Waiting for scrape to complete (this may take a minute)..."
    sleep 5
    
    # Get status
    get_status "$SEARCH_ID"
    echo ""
    
    # List leads
    list_leads "$SEARCH_ID"
    echo ""
    
    # Cleanup
    delete_search "$SEARCH_ID"
    
    echo ""
    print_success "Test completed!"
    echo ""
    print_info "Search ID: ${SEARCH_ID}"
    print_info "View search: ${API_URL}/api/v1/keyword-searches/${SEARCH_ID}"
    print_info "View leads: ${API_URL}/api/v1/leads?keyword_search_id=${SEARCH_ID}"
}

# Run main function
main

