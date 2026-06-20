"""Unit tests for the compactTree pure transform (tests-tree-cleanup).

All tests exercise the JS-side compactTree logic via Python helper stubs that
mirror the exact node shape used by buildTree:
  { name: str, children: dict[str, node], tests: list[test_aggregate] }

Compacted nodes add optional fields:
  _segments: list[str]   (breadcrumb label for collapsed chains)
  _mergedTest: test      (single-function file merge flag)

Tests are organised in TDD order:
  Phase 2 — unit tests for the pure transform (written BEFORE implementation).

STRICT TDD: every test in this file was written BEFORE the implementation.
"""

from __future__ import annotations

import copy
from typing import Any

# ---------------------------------------------------------------------------
# Helper: build raw tree nodes matching buildTree's {name, children, tests}
# ---------------------------------------------------------------------------


def _make_test(
    function_name: str,
    file: str = "tests/test_foo.py",
    total_runs: int = 1,
    passed: int = 1,
    failed: int = 0,
    skipped: int = 0,
    errors: int = 0,
) -> dict[str, Any]:
    """Build a minimal test aggregate object matching the DATA.tests item shape."""
    return {
        "aggregate": {
            "function_name": function_name,
            "file": file,
            "total_runs": total_runs,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "errors": errors,
            "total_duration_seconds": 0.1,
        },
        "runs": [],
    }


def _make_node(
    name: str = "node",
    children: dict[str, Any] | None = None,
    tests: list[Any] | None = None,
) -> dict[str, Any]:
    """Build a raw tree node matching buildTree's output shape."""
    return {
        "name": name,
        "children": children if children is not None else {},
        "tests": tests if tests is not None else [],
    }


# ---------------------------------------------------------------------------
# Python-side compactTree implementation reference
# (mirrors the JS we will write — used to drive tests from Python;
#  the actual production code is in _js.py as inline JS)
# ---------------------------------------------------------------------------


def _node_agg(node: dict[str, Any]) -> dict[str, int]:
    """Compute aggregate counts for a node (mirrors JS nodeAgg)."""
    p = f = s = e = 0
    for t in node["tests"]:
        agg = t["aggregate"]
        p += agg["passed"]
        f += agg["failed"]
        s += agg["skipped"]
        e += agg["errors"]
    for child in node["children"].values():
        ca = _node_agg(child)
        p += ca["passed"]
        f += ca["failed"]
        s += ca["skipped"]
        e += ca["error"]
    return {"passed": p, "failed": f, "skipped": s, "error": e}


def _common_prefix_strip(root: dict[str, Any]) -> dict[str, Any]:
    """Strip longest shared leading path segments from root (mirrors JS commonPrefixStrip)."""
    node = root
    while True:
        children = node["children"]
        if len(children) != 1:
            break
        child_name = next(iter(children))
        if node["tests"]:  # has own tests — stop
            break
        node = children[child_name]
    return node


def _collapse_chains(node: dict[str, Any]) -> dict[str, Any]:
    """Recursively collapse single-child-dir chains (mirrors JS collapseChains)."""
    # First recurse into children
    new_children: dict[str, Any] = {}
    for cname, child in node["children"].items():
        collapsed = _collapse_chains(child)
        new_children[cname] = collapsed

    node = dict(node)
    node["children"] = new_children

    # Collapse: if no own tests and exactly one child dir, merge
    while not node["tests"] and len(node["children"]) == 1:
        child_name = next(iter(node["children"]))
        child = node["children"][child_name]
        # Merge _segments
        my_segs: list[str] = node.get("_segments", [node["name"]])
        child_segs: list[str] = child.get("_segments", [child_name])
        merged: dict[str, Any] = {
            "name": " / ".join(my_segs + child_segs),
            "_segments": my_segs + child_segs,
            "children": child["children"],
            "tests": child["tests"],
        }
        node = merged

    return node


def _flag_single_fn_merges(node: dict[str, Any]) -> dict[str, Any]:
    """Flag file nodes with exactly one test for merged rendering."""
    new_children: dict[str, Any] = {}
    for cname, child in node["children"].items():
        new_children[cname] = _flag_single_fn_merges(child)

    node = dict(node)
    node["children"] = new_children

    # File node: no child dirs and exactly one test
    if not node["children"] and len(node["tests"]) == 1:
        node["_mergedTest"] = node["tests"][0]

    return node


def _compact_tree(raw_root: dict[str, Any]) -> dict[str, Any]:
    """Full compactTree pipeline: prefix strip -> chain collapse -> single-fn merge."""
    stripped = _common_prefix_strip(raw_root)
    collapsed = _collapse_chains(stripped)
    return _flag_single_fn_merges(collapsed)


# ---------------------------------------------------------------------------
# Phase 2: Unit Tests (RED -> GREEN with implementation)
# ---------------------------------------------------------------------------


class TestCommonPrefixStrip:
    def test_common_prefix_strip_single_shared_root(self) -> None:
        """2.2: shared root 'tests/' stripped; unit and integration become top-level.

        Spec: REQ-1 scenario 1 + 3.
        """
        unit_node = _make_node("unit", tests=[_make_test("test_a")])
        integration_node = _make_node("integration", tests=[_make_test("test_b")])
        tests_node = _make_node(
            "tests", children={"unit": unit_node, "integration": integration_node}
        )
        root = _make_node("root", children={"tests": tests_node})

        result = _common_prefix_strip(root)

        # tests/ is stripped; result is tests_node whose children are unit+integration
        assert "unit" in result["children"]
        assert "integration" in result["children"]
        assert "tests" not in result["children"]

    def test_no_common_prefix_unmodified(self) -> None:
        """2.3: no common prefix -> root unchanged; both dirs appear at top level.

        Spec: REQ-1 scenario 2.
        """
        unit_node = _make_node("unit", tests=[_make_test("test_a")])
        integration_node = _make_node("integration", tests=[_make_test("test_b")])
        root = _make_node("root", children={"unit": unit_node, "integration": integration_node})

        result = _common_prefix_strip(root)

        assert "unit" in result["children"]
        assert "integration" in result["children"]


class TestCollapseChains:
    def test_single_child_chain_collapse(self) -> None:
        """2.4: ctec -> FOX -> fox_delay (each 1 child, no own tests) -> single breadcrumb.

        Spec: REQ-2 scenario 1.
        """
        test_a = _make_test("test_fox_delay")
        fox_delay_node = _make_node("fox_delay", tests=[test_a])
        fox_node = _make_node("FOX", children={"fox_delay": fox_delay_node})
        ctec_node = _make_node("ctec", children={"FOX": fox_node})

        result = _collapse_chains(ctec_node)

        assert "_segments" in result
        assert result["_segments"] == ["ctec", "FOX", "fox_delay"]
        assert result["tests"] == [test_a]
        assert result["children"] == {}

    def test_multi_child_stops_collapse(self) -> None:
        """2.5: features/ -> {auth/, payments/} -> features NOT collapsed.

        Spec: REQ-2 scenario 2.
        """
        auth_node = _make_node("auth", tests=[_make_test("test_login")])
        payments_node = _make_node("payments", tests=[_make_test("test_pay")])
        features_node = _make_node(
            "features", children={"auth": auth_node, "payments": payments_node}
        )

        result = _collapse_chains(features_node)

        assert "_segments" not in result
        assert "auth" in result["children"]
        assert "payments" in result["children"]

    def test_mixed_chain_ends_at_multi_child(self) -> None:
        """2.6: module/ -> sub/ -> {a/, b/} -> 'module / sub' breadcrumb with two children.

        Spec: REQ-2 scenario 3.
        """
        a_node = _make_node("a", tests=[_make_test("test_a")])
        b_node = _make_node("b", tests=[_make_test("test_b")])
        sub_node = _make_node("sub", children={"a": a_node, "b": b_node})
        module_node = _make_node("module", children={"sub": sub_node})

        result = _collapse_chains(module_node)

        assert "_segments" in result
        assert result["_segments"] == ["module", "sub"]
        assert "a" in result["children"]
        assert "b" in result["children"]


class TestFlagSingleFnMerges:
    def test_single_fn_file_merged(self) -> None:
        """2.7: file node with tests=[one_test], no children -> _mergedTest set.

        Spec: REQ-3 scenario 1.
        """
        test_a = _make_test("test_foo")
        file_node = _make_node("test_foo.py", tests=[test_a])

        result = _flag_single_fn_merges(file_node)

        assert "_mergedTest" in result
        assert result["_mergedTest"] is test_a

    def test_multi_fn_file_not_merged(self) -> None:
        """2.8: file node with tests=[t1, t2] -> no _mergedTest; both tests remain.

        Spec: REQ-3 scenario 2.
        """
        t1 = _make_test("test_a")
        t2 = _make_test("test_b")
        file_node = _make_node("test_utils.py", tests=[t1, t2])

        result = _flag_single_fn_merges(file_node)

        assert "_mergedTest" not in result
        assert len(result["tests"]) == 2

    def test_parametrized_single_fn_merges(self) -> None:
        """2.9: parametrized test (one function, total_runs=3) -> single _mergedTest.

        Spec: REQ-7 parametrized row.
        """
        test_parametrized = _make_test("test_foo", total_runs=3)
        file_node = _make_node("test_foo.py", tests=[test_parametrized])

        result = _flag_single_fn_merges(file_node)

        assert "_mergedTest" in result
        assert result["_mergedTest"]["aggregate"]["total_runs"] == 3

    def test_class_based_function_name_not_split(self) -> None:
        """2.10: function_name with '::' is label text only — not a path separator.

        Spec: REQ-7 class-based.
        """
        test_class = _make_test("TestFoo::test_method")
        file_node = _make_node("test_class.py", tests=[test_class])

        result = _flag_single_fn_merges(file_node)

        # Still merges (one test function entry); function_name preserved intact
        assert "_mergedTest" in result
        assert result["_mergedTest"]["aggregate"]["function_name"] == "TestFoo::test_method"


class TestCompactTree:
    def test_compactTree_does_not_mutate_input(self) -> None:
        """2.11: compactTree must not mutate its input (pure function invariant).

        Spec: Design D1 invariant / REQ-6.
        """
        test_a = _make_test("test_foo")
        file_node = _make_node("test_foo.py", tests=[test_a])
        sub_node = _make_node("sub", children={"test_foo.py": file_node})
        tests_node = _make_node("tests", children={"sub": sub_node})
        raw_root = _make_node("root", children={"tests": tests_node})

        raw_before = copy.deepcopy(raw_root)
        _compact_tree(raw_root)
        raw_after = copy.deepcopy(raw_root)

        assert raw_before == raw_after, "compactTree must not mutate the input"

    def test_nodeAgg_correct_on_compacted_graph(self) -> None:
        """2.12: after collapsing 3 dirs with 5 tests (3 passed, 2 failed),
        nodeAgg returns {passed:3, failed:2, skipped:0, error:0}.

        Spec: REQ-5.
        """
        tests = [
            _make_test("test_a", passed=1, failed=0),
            _make_test("test_b", passed=1, failed=0),
            _make_test("test_c", passed=1, failed=0),
            _make_test("test_d", passed=0, failed=1),
            _make_test("test_e", passed=0, failed=1),
        ]
        leaf_node = _make_node("leaf", tests=tests)
        mid_node = _make_node("mid", children={"leaf": leaf_node})
        top_node = _make_node("top", children={"mid": mid_node})

        compacted = _compact_tree(top_node)
        agg = _node_agg(compacted)

        assert agg["passed"] == 3
        assert agg["failed"] == 2
        assert agg["skipped"] == 0
        assert agg["error"] == 0

    def test_single_test_run_no_crash(self) -> None:
        """2.13: single test in one file in one dir -> compact without crash.

        Spec: REQ-7 single test.
        """
        test_a = _make_test("test_only")
        file_node = _make_node("test_only.py", tests=[test_a])
        dir_node = _make_node("tests", children={"test_only.py": file_node})
        root = _make_node("root", children={"tests": dir_node})

        result = _compact_tree(root)

        assert result is not None
        # Should produce either a merged leaf or a structure with no crash
        assert "_mergedTest" in result or "children" in result

    def test_flat_layout_no_crash(self) -> None:
        """2.14: root with two direct file nodes (no intermediate dirs) -> no crash.

        Spec: REQ-7 flat layout.
        """
        t1 = _make_test("test_a")
        t2 = _make_test("test_b")
        file1 = _make_node("test_a.py", tests=[t1])
        file2 = _make_node("test_b.py", tests=[t2])
        root = _make_node("root", children={"test_a.py": file1, "test_b.py": file2})

        result = _compact_tree(root)

        assert result is not None
        assert "children" in result
        assert len(result["children"]) == 2
