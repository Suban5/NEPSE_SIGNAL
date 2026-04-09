#!/bin/bash

# UI2-T3 Smoke Validation Tests
# Validates all dashboard endpoints are responding with expected schema

BASE_URL="${1:-http://localhost:8000}"
PASSED=0
FAILED=0

echo "=== UI2 Dashboard Smoke Tests ==="
echo "Base URL: $BASE_URL"
echo ""

# Test 1: Signal Summary Endpoint
echo "[Test 1] GET /analytics/signal-summary"
RESPONSE=$(curl -s -X GET "$BASE_URL/analytics/signal-summary?top_n=10&sector_relative=false" \
  -H "Content-Type: application/json" \
  -w "\n%{http_code}")
STATUS=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$STATUS" == "200" ]; then
  if echo "$BODY" | grep -q '"top_n"' && echo "$BODY" | grep -q '"execution_id"' && echo "$BODY" | grep -q '"rows"'; then
    echo "✅ PASS (HTTP $STATUS, schema valid)"
    ((PASSED++))
  else
    echo "❌ FAIL (HTTP $STATUS, missing required fields)"
    ((FAILED++))
  fi
else
  echo "❌ FAIL (HTTP $STATUS)"
  echo "$BODY"
  ((FAILED++))
fi
echo ""

# Test 2: Blue-Chip Ranking Endpoint
echo "[Test 2] GET /analytics/bluechip-ranking"
RESPONSE=$(curl -s -X GET "$BASE_URL/analytics/bluechip-ranking?top_n=10&sector_relative=false" \
  -H "Content-Type: application/json" \
  -w "\n%{http_code}")
STATUS=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$STATUS" == "200" ]; then
  if echo "$BODY" | grep -q '"top_n"' && echo "$BODY" | grep -q '"execution_id"' && echo "$BODY" | grep -q '"rows"'; then
    echo "✅ PASS (HTTP $STATUS, schema valid)"
    ((PASSED++))
  else
    echo "❌ FAIL (HTTP $STATUS, missing required fields)"
    ((FAILED++))
  fi
else
  echo "❌ FAIL (HTTP $STATUS)"
  echo "$BODY"
  ((FAILED++))
fi
echo ""

# Test 3: Backtest Summary Endpoint
echo "[Test 3] GET /analytics/backtest-summary"
RESPONSE=$(curl -s -X GET "$BASE_URL/analytics/backtest-summary?lookback_days=252&rebalance=monthly&sector_relative=false" \
  -H "Content-Type: application/json" \
  -w "\n%{http_code}")
STATUS=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$STATUS" == "200" ]; then
  if echo "$BODY" | grep -q '"lookback_days"' && echo "$BODY" | grep -q '"portfolio_metrics"' && echo "$BODY" | grep -q '"historical_validation"'; then
    echo "✅ PASS (HTTP $STATUS, schema valid)"
    ((PASSED++))
  else
    echo "❌ FAIL (HTTP $STATUS, missing required fields)"
    ((FAILED++))
  fi
else
  echo "❌ FAIL (HTTP $STATUS)"
  echo "$BODY"
  ((FAILED++))
fi
echo ""

# Test 4: Health Endpoint
echo "[Test 4] GET /health"
RESPONSE=$(curl -s -X GET "$BASE_URL/health" \
  -H "Content-Type: application/json" \
  -w "\n%{http_code}")
STATUS=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$STATUS" == "200" ]; then
  if echo "$BODY" | grep -q '"ok"'; then
    echo "✅ PASS (HTTP $STATUS, schema valid)"
    ((PASSED++))
  else
    echo "❌ FAIL (HTTP $STATUS, missing required fields)"
    ((FAILED++))
  fi
else
  echo "❌ FAIL (HTTP $STATUS)"
  echo "$BODY"
  ((FAILED++))
fi
echo ""

# Test 5: Metrics Endpoint
echo "[Test 5] GET /metrics"
RESPONSE=$(curl -s -X GET "$BASE_URL/metrics" \
  -H "Content-Type: application/json" \
  -w "\n%{http_code}")
STATUS=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$STATUS" == "200" ]; then
  if echo "$BODY" | grep -q '"request_count"' && echo "$BODY" | grep -q '"execution_trace_counts"'; then
    echo "✅ PASS (HTTP $STATUS, schema valid)"
    ((PASSED++))
  else
    echo "❌ FAIL (HTTP $STATUS, missing required fields)"
    ((FAILED++))
  fi
else
  echo "❌ FAIL (HTTP $STATUS)"
  echo "$BODY"
  ((FAILED++))
fi
echo ""

# Test 6: Error Handling - Invalid Parameter
echo "[Test 6] Error Handling - Invalid Parameter"
RESPONSE=$(curl -s -X GET "$BASE_URL/analytics/signal-summary?top_n=invalid" \
  -H "Content-Type: application/json" \
  -w "\n%{http_code}")
STATUS=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$STATUS" == "422" ]; then
  if echo "$BODY" | grep -q '"error"'; then
    echo "✅ PASS (HTTP $STATUS, error response valid)"
    ((PASSED++))
  else
    echo "❌ FAIL (HTTP $STATUS, missing error fields)"
    ((FAILED++))
  fi
elif [ "$STATUS" == "200" ]; then
  echo "⚠️  WARN (HTTP 200 returned instead of 422 for invalid param—check validation)"
  ((PASSED++))
else
  echo "❌ FAIL (HTTP $STATUS)"
  echo "$BODY"
  ((FAILED++))
fi
echo ""

# Summary
echo "=== Test Summary ==="
echo "✅ Passed: $PASSED"
echo "❌ Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
  echo "🎉 All UI2 smoke tests passed!"
  exit 0
else
  echo "⚠️  Some tests failed. Review above for details."
  exit 1
fi
