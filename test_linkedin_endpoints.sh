#!/bin/bash

# Test LinkedIn Integration Endpoints
# Make sure you have a valid auth token from login

BASE_URL="${API_BASE_URL:-http://localhost:8000}"
echo "Testing LinkedIn endpoints at: $BASE_URL"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if AUTH_TOKEN is set
if [ -z "$AUTH_TOKEN" ]; then
    echo -e "${YELLOW}⚠️  AUTH_TOKEN not set. You need to login first and get a token.${NC}"
    echo "Example: export AUTH_TOKEN='your_jwt_token_here'"
    echo ""
    echo "Or test without auth (some endpoints require auth):"
    echo ""
fi

echo "=========================================="
echo "1. Testing GET /linkedin/auth-url"
echo "=========================================="
if [ -z "$AUTH_TOKEN" ]; then
    curl -X GET "$BASE_URL/linkedin/auth-url" \
        -H "Content-Type: application/json" \
        -w "\nHTTP Status: %{http_code}\n" \
        | jq '.' 2>/dev/null || cat
else
    curl -X GET "$BASE_URL/linkedin/auth-url" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -w "\nHTTP Status: %{http_code}\n" \
        | jq '.' 2>/dev/null || cat
fi
echo ""

echo "=========================================="
echo "2. Testing POST /linkedin/update-url (Manual URL Entry)"
echo "=========================================="
if [ -z "$AUTH_TOKEN" ]; then
    echo -e "${RED}❌ This endpoint requires authentication${NC}"
    echo "Set AUTH_TOKEN environment variable first"
else
    # Test with valid URL
    echo "Testing with valid LinkedIn URL..."
    curl -X POST "$BASE_URL/linkedin/update-url" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -d '{"linkedin_url": "https://www.linkedin.com/in/testuser"}' \
        -w "\nHTTP Status: %{http_code}\n" \
        | jq '.' 2>/dev/null || cat
    
    echo ""
    echo "Testing with invalid URL (should fail)..."
    curl -X POST "$BASE_URL/linkedin/update-url" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $AUTH_TOKEN" \
        -d '{"linkedin_url": "invalid-url"}' \
        -w "\nHTTP Status: %{http_code}\n" \
        | jq '.' 2>/dev/null || cat
fi
echo ""

echo "=========================================="
echo "3. Testing Health Check"
echo "=========================================="
curl -X GET "$BASE_URL/health" \
    -w "\nHTTP Status: %{http_code}\n" \
    | jq '.' 2>/dev/null || cat
echo ""

echo "=========================================="
echo "✅ Testing Complete!"
echo "=========================================="
echo ""
echo "To test OAuth callback flow:"
echo "1. Get auth URL from endpoint 1"
echo "2. Open the auth_url in browser"
echo "3. Authorize the app"
echo "4. Copy the 'code' from redirect URL"
echo "5. Call POST /linkedin/callback with the code"

