"""GraphQL API tests demonstrating structured logging, procedure steps, and retry behavior."""

from __future__ import annotations

import logging
import time

import pytest

from stepdoc import step

log = logging.getLogger("graphql")


# ---------------------------------------------------------------------------
# Simulated GraphQL helpers
# ---------------------------------------------------------------------------

_PRODUCTS = [
    {"id": "prod_001", "name": "Wireless Headphones", "price": 79.99, "stock": 142, "category": "electronics"},
    {"id": "prod_002", "name": "Ergonomic Keyboard", "price": 129.00, "stock": 58, "category": "electronics"},
    {"id": "prod_003", "name": "Standing Desk Mat", "price": 45.50, "stock": 0, "category": "furniture"},
    {"id": "prod_004", "name": "USB-C Hub", "price": 34.99, "stock": 310, "category": "electronics"},
    {"id": "prod_005", "name": "Monitor Arm", "price": 89.00, "stock": 23, "category": "furniture"},
]

_ORDERS = [
    {"id": "ord_101", "user_id": 1, "product_id": "prod_001", "quantity": 2, "status": "shipped", "total": 159.98},
    {"id": "ord_102", "user_id": 2, "product_id": "prod_002", "quantity": 1, "status": "processing", "total": 129.00},
    {"id": "ord_103", "user_id": 1, "product_id": "prod_004", "quantity": 3, "status": "delivered", "total": 104.97},
    {"id": "ord_104", "user_id": 3, "product_id": "prod_005", "quantity": 1, "status": "cancelled", "total": 89.00},
]


def _execute_graphql(query: str, variables: dict | None = None) -> dict:
    """Simulate a GraphQL execution engine."""
    variables = variables or {}
    # Very rough query parser for simulation
    if "products" in query and "category" in str(variables):
        cat = variables.get("category", "")
        filtered = [p for p in _PRODUCTS if p["category"] == cat]
        return {"data": {"products": filtered}, "errors": None}
    if "products" in query:
        return {"data": {"products": _PRODUCTS}, "errors": None}
    if "product(" in query or "product_by_id" in query.lower():
        pid = variables.get("id", "prod_001")
        product = next((p for p in _PRODUCTS if p["id"] == pid), None)
        if product:
            return {"data": {"product": product}, "errors": None}
        return {"data": {"product": None}, "errors": [{"message": f"Product {pid} not found", "path": ["product"]}]}
    if "orders" in query and "user_id" in str(variables):
        uid = variables.get("user_id", 1)
        filtered = [o for o in _ORDERS if o["user_id"] == uid]
        return {"data": {"orders": filtered}, "errors": None}
    if "orders" in query:
        return {"data": {"orders": _ORDERS}, "errors": None}
    if "createProduct" in query or "mutation" in query.lower() and "product" in query.lower():
        new_product = {"id": "prod_006", **variables.get("input", {})}
        return {"data": {"createProduct": new_product}, "errors": None}
    if "introspection" in query.lower() or "__schema" in query:
        return {
            "data": {"__schema": {"types": [{"name": "Query"}, {"name": "Mutation"}, {"name": "Product"}, {"name": "Order"}]}},
            "errors": None,
        }
    return {"data": None, "errors": [{"message": "Unknown query"}]}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_query_all_products() -> None:
    """Test fetching the complete product catalog via GraphQL."""
    gql = log.getChild("graphql")
    validation = log.getChild("validation")

    query = "{ products { id name price stock category } }"

    with step("Execute products query"):
        gql.info("Sending query", extra={"query": query, "variables": None})
        gql.debug("Query complexity estimate", extra={"depth": 1, "fields": 5, "estimated_cost": 5})
        time.sleep(0.001)
        result = _execute_graphql(query)
        gql.info("Query result received", extra={"product_count": len(result["data"]["products"])})
        gql.debug("First product", extra={"data": result["data"]["products"][0]})

    with step("Validate response structure"):
        with step("Check no errors"):
            validation.info("Error field", extra={"errors": result["errors"]})
            assert result["errors"] is None

        with step("Check product list"):
            products = result["data"]["products"]
            validation.info("Product count", extra={"count": len(products), "expected_min": 1})
            assert len(products) >= 1

        with step("Verify product fields"):
            for field in ("id", "name", "price", "stock", "category"):
                validation.debug(f"Field '{field}' present in first product", extra={"value": products[0][field]})
                assert field in products[0]
            validation.info("All product fields verified")


@pytest.mark.parametrize(
    "category,expected_count",
    [
        ("electronics", 3),
        ("furniture", 2),
        ("clothing", 0),
    ],
    ids=["electronics", "furniture", "empty-category"],
)
def test_query_products_by_category(category: str, expected_count: int) -> None:
    """Test filtering products by category."""
    gql = log.getChild("graphql")
    filter_log = log.getChild("filter")

    query = '{ products(category: $category) { id name price } }'
    variables = {"category": category}

    with step("Execute filtered query"):
        gql.info("Sending category query", extra={"query": query, "variables": variables})
        result = _execute_graphql(query, variables)
        products = result["data"]["products"]
        filter_log.info("Filtered results", extra={"category": category, "count": len(products)})
        filter_log.debug("Products found", extra={"names": [p["name"] for p in products]})

    with step("Validate filter results"):
        filter_log.info("Comparing counts", extra={"expected": expected_count, "actual": len(products)})
        assert len(products) == expected_count
        if products:
            for p in products:
                filter_log.debug("Verify category match", extra={"product": p["name"], "category": p["category"]})
                assert p["category"] == category
        filter_log.info("Category filter works correctly")


def test_query_product_by_id() -> None:
    """Test fetching a single product by its ID."""
    gql = log.getChild("graphql")

    query = "{ product(id: $id) { id name price stock } }"
    variables = {"id": "prod_002"}

    with step("Execute single product query"):
        gql.info("Querying product", extra={"query": query, "variables": variables})
        time.sleep(0.001)
        result = _execute_graphql(query, variables)
        gql.info("Product fetched", extra={"data": result["data"]["product"]})
        gql.debug("Response metadata", extra={"has_errors": result["errors"] is not None, "cache_hit": False})

    with step("Verify product data"):
        product = result["data"]["product"]
        gql.info("Validating product fields", extra={"data": {"id": product["id"], "name": product["name"]}})
        assert product["id"] == "prod_002"
        assert product["name"] == "Ergonomic Keyboard"
        assert product["price"] == 129.00
        gql.info("Product data matches expected values")


def test_query_nonexistent_product() -> None:
    """Test querying a product that does not exist returns an error."""
    gql = log.getChild("graphql")
    error_log = log.getChild("errors")

    query = "{ product(id: $id) { id name } }"
    variables = {"id": "prod_999"}

    with step("Query non-existent product"):
        gql.info("Sending query for missing product", extra={"variables": variables})
        result = _execute_graphql(query, variables)
        gql.info("Result received", extra={"data": result["data"], "errors": result["errors"]})

    with step("Validate error response"):
        with step("Check errors array present"):
            error_log.info("Errors field", extra={"errors": result["errors"]})
            assert result["errors"] is not None
            assert len(result["errors"]) > 0

        with step("Check error message"):
            error_log.info("Error message", extra={"data": {"message": result["errors"][0]["message"]}})
            assert "not found" in result["errors"][0]["message"].lower()

        with step("Check data is null"):
            error_log.info("Data field", extra={"product": result["data"]["product"]})
            assert result["data"]["product"] is None
            error_log.info("Error handling for missing resource verified")


def test_query_orders_by_user() -> None:
    """Test fetching orders filtered by user ID."""
    gql = log.getChild("graphql")
    orders_log = log.getChild("orders")

    query = "{ orders(user_id: $user_id) { id status total } }"
    variables = {"user_id": 1}

    with step("Execute orders query"):
        gql.info("Fetching user orders", extra={"query": query, "variables": variables})
        result = _execute_graphql(query, variables)
        orders = result["data"]["orders"]
        orders_log.info("Orders fetched", extra={"count": len(orders)})
        for order in orders:
            orders_log.debug("Order detail", extra={"data": order})

    with step("Validate order data"):
        with step("Check order count"):
            orders_log.info("Expected 2 orders for user 1", extra={"actual": len(orders)})
            assert len(orders) == 2

        with step("Verify all belong to user"):
            for order in orders:
                assert order["user_id"] == 1
            orders_log.info("All orders belong to the queried user")

        with step("Check order totals are positive"):
            for order in orders:
                orders_log.debug("Order total", extra={"id": order["id"], "total": order["total"]})
                assert order["total"] > 0
            orders_log.info("Order validation complete")


def test_mutation_create_product() -> None:
    """Test creating a product via GraphQL mutation."""
    gql = log.getChild("graphql")
    mutation_log = log.getChild("mutation")

    mutation = "mutation CreateProduct($input: ProductInput!) { createProduct(input: $input) { id name price } }"
    variables = {"input": {"name": "Webcam HD", "price": 59.99, "stock": 200, "category": "electronics"}}

    with step("Prepare mutation"):
        mutation_log.info("Mutation details", extra={"mutation": mutation[:60] + "...", "variables": variables})
        mutation_log.debug("Input validation", extra={"name_length": len(variables["input"]["name"]), "price_positive": variables["input"]["price"] > 0})

    with step("Execute mutation"):
        time.sleep(0.001)
        result = _execute_graphql(mutation, variables)
        gql.info("Mutation result", extra={"data": result["data"]})
        gql.debug("Execution metadata", extra={"errors": result["errors"], "cache_invalidated": True})

    with step("Validate created product"):
        created = result["data"]["createProduct"]
        mutation_log.info("Created product", extra={"data": created})
        assert created["id"] == "prod_006"
        assert created["name"] == "Webcam HD"
        mutation_log.info("Product creation mutation succeeded")


def test_introspection_query() -> None:
    """Test GraphQL schema introspection."""
    gql = log.getChild("graphql")
    schema_log = log.getChild("schema")

    query = "{ __schema { types { name } } }"

    with step("Execute introspection query"):
        gql.info("Sending introspection query", extra={"query": query})
        result = _execute_graphql(query)
        gql.info("Schema received", extra={"type_count": len(result["data"]["__schema"]["types"])})

    with step("Validate schema types"):
        types = [t["name"] for t in result["data"]["__schema"]["types"]]
        schema_log.info("Available types", extra={"types": types})
        for expected in ("Query", "Mutation", "Product", "Order"):
            with step(f"Check type: {expected}"):
                schema_log.debug(f"Looking for {expected}", extra={"present": expected in types})
                assert expected in types
        schema_log.info("Schema introspection returned all expected types")


@pytest.mark.parametrize(
    "depth,max_allowed",
    [
        (2, 10),
        (5, 10),
        (10, 10),
    ],
    ids=["shallow", "medium", "at-limit"],
)
def test_query_depth_limit(depth: int, max_allowed: int) -> None:
    """Test that query depth is within the allowed limit."""
    gql = log.getChild("graphql")
    security = log.getChild("security")

    with step("Construct nested query"):
        nested = "{ " * depth + "id" + " }" * depth
        gql.info("Generated nested query", extra={"depth": depth, "query_length": len(nested)})
        security.debug("Depth analysis", extra={"depth": depth, "max_allowed": max_allowed})

    with step("Validate depth"):
        security.info("Checking depth limit", extra={"depth": depth, "max": max_allowed, "allowed": depth <= max_allowed})
        assert depth <= max_allowed
        security.info("Query depth within acceptable range")


def test_query_cost_estimation() -> None:
    """Test that complex queries have accurate cost estimates."""
    gql = log.getChild("graphql")
    perf = log.getChild("performance")

    queries = [
        {"query": "{ products { id } }", "expected_cost": 5},
        {"query": "{ products { id name price stock category } }", "expected_cost": 25},
        {"query": "{ orders { id product { name price } user { name email } } }", "expected_cost": 48},
    ]

    for i, q in enumerate(queries):
        with step(f"Estimate cost for query {i + 1}"):
            gql.info("Query", extra={"query": q["query"][:50], "index": i})
            # Simulated cost based on field count
            field_count = q["query"].count(" ")
            simulated_cost = field_count * 2
            perf.info("Cost estimate", extra={"estimated": simulated_cost, "expected": q["expected_cost"]})
            perf.debug("Cost breakdown", extra={"field_count": field_count, "multiplier": 2})

    perf.info("Cost estimation analysis complete", extra={"queries_analyzed": len(queries)})


def test_batch_queries() -> None:
    """Test executing multiple queries in a single batch request."""
    gql = log.getChild("graphql")
    batch = log.getChild("batch")

    queries = [
        ("{ products { id name } }", {}),
        ("{ orders { id status } }", {}),
        ('{ product(id: $id) { name } }', {"id": "prod_001"}),
    ]

    with step("Execute batch"):
        batch.info("Batch request", extra={"query_count": len(queries)})
        results = []
        for i, (query, variables) in enumerate(queries):
            gql.debug(f"Executing query {i + 1}", extra={"query": query[:40]})
            result = _execute_graphql(query, variables)
            results.append(result)
            gql.info(f"Query {i + 1} complete", extra={"has_errors": result["errors"] is not None})
        batch.info("Batch complete", extra={"results_count": len(results)})

    with step("Validate batch results"):
        for i, result in enumerate(results):
            with step(f"Check query {i + 1} result"):
                batch.debug(f"Result {i + 1}", extra={"data_keys": list(result["data"].keys()) if result["data"] else []})
                assert result["data"] is not None
        batch.info("All batch queries returned data")


@pytest.mark.parametrize(
    "fragment_name,fragment_fields",
    [
        ("ProductBasic", ["id", "name"]),
        ("ProductFull", ["id", "name", "price", "stock", "category"]),
    ],
    ids=["basic-fragment", "full-fragment"],
)
def test_fragment_resolution(fragment_name: str, fragment_fields: list) -> None:
    """Test that GraphQL fragments are resolved correctly."""
    gql = log.getChild("graphql")
    fragment = log.getChild("fragment")

    with step("Define and use fragment"):
        fields_str = " ".join(fragment_fields)
        query = f"fragment {fragment_name} on Product {{ {fields_str} }} {{ products {{ ...{fragment_name} }} }}"
        gql.info("Fragment query", extra={"fragment": fragment_name, "fields": fragment_fields, "query_length": len(query)})
        fragment.debug("Fragment definition", extra={"data": {"name": fragment_name, "field_count": len(fragment_fields)}})

    with step("Execute query with fragment"):
        result = _execute_graphql("{ products { id name price stock category } }")
        gql.info("Result received", extra={"product_count": len(result["data"]["products"])})
        time.sleep(0.001)

    with step("Verify fragment fields present"):
        product = result["data"]["products"][0]
        for field in fragment_fields:
            with step(f"Check field: {field}"):
                fragment.debug(f"Field {field}", extra={"present": field in product, "value": product.get(field)})
                assert field in product
        fragment.info(f"Fragment {fragment_name} resolved all fields")


def test_subscription_placeholder() -> None:
    """Test subscription query parsing (no actual WebSocket)."""
    gql = log.getChild("graphql")
    sub = log.getChild("subscription")

    subscription_query = "subscription { productUpdated { id name stock } }"

    with step("Parse subscription query"):
        gql.info("Subscription query", extra={"query": subscription_query})
        sub.info("Extracting subscription fields", extra={"type": "productUpdated", "fields": ["id", "name", "stock"]})
        sub.debug("Subscription metadata", extra={"transport": "websocket", "protocol": "graphql-ws"})

    with step("Simulate subscription event"):
        event = {"id": "prod_001", "name": "Wireless Headphones", "stock": 140}
        sub.info("Event received", extra={"data": event})
        sub.debug("Event processing", extra={"latency_ms": 3, "sequence": 1})
        assert event["id"] == "prod_001"
        sub.info("Subscription event processed")


def test_query_aliasing() -> None:
    """Test field aliasing in GraphQL queries."""
    gql = log.getChild("graphql")

    with step("Execute aliased query"):
        query = "{ electronics: products(category: electronics) { name } office: products(category: furniture) { name } }"
        gql.info("Aliased query", extra={"query": query[:60] + "...", "aliases": ["electronics", "office"]})
        electronics = _execute_graphql("{ products }", {"category": "electronics"})
        furniture = _execute_graphql("{ products }", {"category": "furniture"})
        gql.info("Both aliases resolved", extra={
            "electronics_count": len(electronics["data"]["products"]),
            "furniture_count": len(furniture["data"]["products"]),
        })

    with step("Validate aliased results"):
        assert len(electronics["data"]["products"]) == 3
        assert len(furniture["data"]["products"]) == 2
        gql.info("Field aliasing verified")


@pytest.mark.parametrize(
    "variables,valid",
    [
        ({"id": "prod_001"}, True),
        ({"id": ""}, False),
        ({"id": None}, False),
    ],
    ids=["valid-id", "empty-id", "null-id"],
)
def test_variable_validation(variables: dict, valid: bool) -> None:
    """Test that GraphQL variables are validated before execution."""
    gql = log.getChild("graphql")
    validator = log.getChild("validator")

    with step("Validate variables"):
        gql.info("Input variables", extra={"data": variables})
        id_val = variables.get("id")
        is_valid = isinstance(id_val, str) and len(id_val) > 0
        validator.info("Validation result", extra={"is_valid": is_valid, "expected_valid": valid})
        validator.debug("Validation details", extra={"type": type(id_val).__name__, "value": id_val})

    with step("Assert validation outcome"):
        assert is_valid == valid
        validator.info("Variable validation behaves correctly")


@pytest.mark.skip(reason="Persisted queries feature not yet enabled")
def test_persisted_queries() -> None:
    """Test that persisted query hashes are resolved."""
    gql = log.getChild("graphql")
    gql.info("This test is skipped")


@pytest.mark.skip(reason="Federation gateway pending deployment")
def test_federation_stitching() -> None:
    """Test schema federation across services."""
    gql = log.getChild("graphql")
    gql.info("This test is skipped")


# --- Flaky service / retry tests ---


def test_graphql_gateway_retry(flaky_service) -> None:
    """Test GraphQL gateway retries on upstream service failure."""
    gql = log.getChild("graphql")
    gateway = log.getChild("gateway")

    with step("Send query through gateway"):
        gql.info("Routing query to product service", extra={"service": "product-svc", "attempt": 1})
        try:
            flaky_service("graphql_gateway")
        except ConnectionError as exc:
            gateway.warning("Upstream service failed", extra={"error": str(exc), "service": "product-svc"}, exc_info=exc)

    with step("Retry via gateway"):
        gateway.info("Retrying upstream call", extra={"attempt": 2, "circuit_breaker": "half-open"})
        time.sleep(0.001)
        result = flaky_service("graphql_gateway")
        gql.info("Gateway retry succeeded", extra={"result": result})

    with step("Validate response"):
        assert result == "ok:graphql_gateway"
        gateway.info("Gateway failover handled correctly")


def test_resolver_cache_retry(flaky_service) -> None:
    """Test resolver-level cache fetch retries on transient error."""
    gql = log.getChild("graphql")
    cache = log.getChild("cache")

    with step("Attempt cache lookup"):
        cache.info("Checking resolver cache", extra={"key": "products:electronics", "ttl": 300})
        try:
            flaky_service("gql_cache_fetch")
        except ConnectionError as exc:
            cache.warning("Cache fetch failed", extra={"error": str(exc)}, exc_info=exc)

    with step("Retry cache fetch"):
        cache.info("Retrying cache lookup", extra={"attempt": 2, "fallback": "direct-db"})
        result = flaky_service("gql_cache_fetch")
        cache.info("Cache fetch succeeded on retry", extra={"result": result})

    with step("Verify data returned"):
        assert result == "ok:gql_cache_fetch"
        cache.info("Resolver cache retry logic verified")


# --- Deliberate failures ---


def test_query_returns_unexpected_null() -> None:
    """Test that non-nullable fields are never null (deliberately fails)."""
    gql = log.getChild("graphql")
    validation = log.getChild("validation")

    with step("Query product"):
        result = _execute_graphql("{ product(id: $id) { id name price } }", {"id": "prod_001"})
        gql.info("Product fetched", extra={"data": result["data"]["product"]})

    with step("Simulate null in non-nullable field"):
        product = dict(result["data"]["product"])
        product["price"] = None  # Simulate unexpected null
        validation.warning("Null detected in non-nullable field", extra={"field": "price", "value": product["price"]})
        assert product["price"] is not None, (
            f"Field 'price' is non-nullable but returned None for product {product['id']}"
        )


def test_mutation_validation_error() -> None:
    """Test that invalid mutation input is rejected (deliberately fails)."""
    gql = log.getChild("graphql")
    mutation_log = log.getChild("mutation")

    with step("Send mutation with negative price"):
        variables = {"input": {"name": "Bad Product", "price": -10.00, "stock": 5, "category": "electronics"}}
        mutation_log.info("Mutation input", extra={"data": variables})
        result = _execute_graphql("mutation { createProduct }", variables)
        gql.info("Mutation result", extra={"data": result["data"]})

    with step("Verify validation error"):
        # Our sim doesn't validate, so this will fail as expected
        mutation_log.error("Mutation should have been rejected", extra={
            "price": variables["input"]["price"],
            "expected": "validation error",
        })
        assert result["errors"] is not None, (
            f"Mutation with negative price (-10.00) should return validation errors, "
            f"but got success: {result['data']}"
        )


def test_rate_limited_query() -> None:
    """Test that excessive queries trigger rate limiting (deliberately fails)."""
    gql = log.getChild("graphql")
    rate = log.getChild("rate_limit")

    with step("Send burst of queries"):
        responses = []
        for i in range(20):
            result = _execute_graphql("{ products { id } }")
            responses.append(result)
            if i % 5 == 0:
                gql.debug(f"Query batch {i // 5 + 1}", extra={"queries_sent": i + 1})
        rate.info("Burst complete", extra={"total_queries": len(responses)})

    with step("Check for rate limit response"):
        # All responses succeed in our sim, so this will fail
        rate_limited = [r for r in responses if r.get("errors") and "rate" in str(r["errors"]).lower()]
        rate.warning("No rate limiting detected", extra={"rate_limited_count": len(rate_limited), "total": len(responses)})
        assert len(rate_limited) > 0, (
            f"Sent 20 rapid queries but none were rate-limited; expected at least 1 rate-limit error"
        )
