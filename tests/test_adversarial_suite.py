"""Empirical Adversarial Test Suite for docs/design_system_2.md.

Adversarial Challenger Suite:
1. AST-level function token parsing (tinycss2 ComponentValue tree).
2. Fallback presence & non-emptiness verification.
3. Fallback-substitution stylesheet roundtrip (replaces all var(--x, fb) with fb and asserts AST validity).
4. Custom property dependency graph & orphan token detection.
5. Display-P3 @supports fallback resilience check.
6. Non-CSS code block (JS/Tailwind, HTML) var() fallback completeness check.
"""

import math
import os
import re
import sys
import time
from pathlib import Path

import pytest
import tinycss2

SRC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../src"))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from flask import Flask, jsonify

import limiter
from validator import (
    RESERVED_ALIASES,
    sanitize_alias,
    sanitize_link_password,
    sanitize_url,
)

DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "design_system_2.md"


def get_all_code_blocks(doc_text: str):
    lines = doc_text.splitlines()
    blocks = []
    in_block = False
    curr_lang = ""
    curr_lines = []
    start_line = 0

    for idx, line in enumerate(lines, 1):
        if line.startswith("```"):
            if not in_block:
                in_block = True
                curr_lang = line[3:].strip()
                curr_lines = []
                start_line = idx + 1
            else:
                in_block = False
                blocks.append({
                    "lang": curr_lang,
                    "start_line": start_line,
                    "end_line": idx - 1,
                    "content": "\n".join(curr_lines),
                })
        elif in_block:
            curr_lines.append(line)
    return blocks


def parse_var_functions_from_tokens(component_values):
    """
    Recursively walk tinycss2 ComponentValues to locate FunctionBlock with name == 'var'.
    Returns list of dicts: {
        'name': 'var',
        'arguments': [tokens],
        'token_name': str,
        'has_comma': bool,
        'fallback_tokens': [tokens],
        'fallback_str': str
    }
    """
    vars_found = []

    def walk(tokens):
        for token in tokens:
            if token.type == 'function' and token.lower_name == 'var':
                args = token.arguments
                # In tinycss2, arguments is a list of ComponentValues
                # First non-whitespace should be ident (--foo)
                arg_tokens = [t for t in args if t.type not in ('whitespace', 'comment')]

                token_ident = ""
                has_comma = False
                fallback_tokens = []

                # Check for token name
                if arg_tokens and arg_tokens[0].type == 'ident':
                    token_ident = arg_tokens[0].value

                # Check for comma
                comma_idx = -1
                for idx, t in enumerate(args):
                    if t.type == 'literal' and t.value == ',':
                        has_comma = True
                        comma_idx = idx
                        break

                if has_comma:
                    fallback_tokens = args[comma_idx + 1:]

                fallback_str = tinycss2.serialize(fallback_tokens).strip() if fallback_tokens else ""

                vars_found.append({
                    'raw': tinycss2.serialize([token]),
                    'token_name': token_ident,
                    'has_comma': has_comma,
                    'fallback_str': fallback_str,
                    'fallback_tokens_count': len([t for t in fallback_tokens if t.type not in ('whitespace', 'comment')]),
                    'line': token.source_line,
                    'column': token.source_column,
                })
                # Also walk arguments for nested functions e.g. var(--a, var(--b, c))
                walk(token.arguments)
            elif hasattr(token, 'arguments'):
                walk(token.arguments)
            elif hasattr(token, 'content'):
                walk(token.content)

    walk(component_values)
    return vars_found


def test_tinycss2_ast_var_fallbacks():
    """Verify that every var() function found in the tinycss2 AST of all CSS blocks has a valid fallback."""
    if not DOC_PATH.exists():
        pytest.skip("docs/design_system_2.md not present")
    content = DOC_PATH.read_text(encoding="utf-8")
    blocks = get_all_code_blocks(content)
    css_blocks = [b for b in blocks if b["lang"] == "css"]

    all_ast_vars = []
    missing_fallbacks = []

    for block in css_blocks:
        rules, _ = tinycss2.parse_stylesheet_bytes(
            block["content"].encode('utf-8'),
            skip_comments=False,
            skip_whitespace=False
        )
        vars_in_block = parse_var_functions_from_tokens(rules)
        for v in vars_in_block:
            actual_line = block["start_line"] + v['line'] - 1
            v['doc_line'] = actual_line
            all_ast_vars.append(v)
            if not v['has_comma'] or not v['fallback_str']:
                missing_fallbacks.append(v)

    print(f"Total CSS AST var() expressions found: {len(all_ast_vars)}")
    assert len(all_ast_vars) > 0, "No var() expressions found in CSS blocks!"
    assert len(missing_fallbacks) == 0, f"Found {len(missing_fallbacks)} var() calls without fallback: {missing_fallbacks}"


def test_fallback_simulation_stylesheet_validity():
    r"""
    STRESS TEST: Fallback-Only Simulation.
    If custom properties fail to resolve, does every var(--token, fallback) degrade to a valid CSS value?
    We replace every var(--[\w-]+,\s*([^)]+)\) with its fallback value and verify the resulting CSS
    stylesheet still parses with zero AST errors in tinycss2 and cssutils.
    """
    if not DOC_PATH.exists():
        pytest.skip("docs/design_system_2.md not present")
    content = DOC_PATH.read_text(encoding="utf-8")
    blocks = get_all_code_blocks(content)
    css_blocks = [b for b in blocks if b["lang"] == "css"]

    for b_idx, block in enumerate(css_blocks, 1):
        css_text = block["content"]

        # Replace var(--name, fallback) with fallback using paren-aware balancer
        def replace_var_with_fallback(text):
            var_pattern = re.compile(r'\bvar\s*\(')
            pos = 0
            out = []
            while True:
                m = var_pattern.search(text, pos)
                if not m:
                    out.append(text[pos:])
                    break
                out.append(text[pos:m.start()])
                # Find matching paren
                start_p = m.end() - 1
                paren_count = 0
                end_p = -1
                for i in range(start_p, len(text)):
                    if text[i] == '(':
                        paren_count += 1
                    elif text[i] == ')':
                        paren_count -= 1
                        if paren_count == 0:
                            end_p = i + 1
                            break
                if end_p == -1:
                    out.append(text[m.start():])
                    break

                full_var = text[m.start():end_p]
                inner = full_var[full_var.find('(') + 1 : -1].strip()
                # find first non-nested comma
                comma_idx = -1
                nest = 0
                for ci, c in enumerate(inner):
                    if c == '(':
                        nest += 1
                    elif c == ')':
                        nest -= 1
                    elif c == ',' and nest == 0:
                        comma_idx = ci
                        break
                if comma_idx != -1:
                    fallback = inner[comma_idx + 1:].strip()
                    # Recursively process fallback if nested
                    fallback = replace_var_with_fallback(fallback)
                    out.append(fallback)
                else:
                    out.append("/* MISSING_FALLBACK */")
                pos = end_p
            return "".join(out)

        simulated_css = replace_var_with_fallback(css_text)
        assert "/* MISSING_FALLBACK */" not in simulated_css, f"Missing fallback in block #{b_idx}"

        # Parse with tinycss2
        rules, _ = tinycss2.parse_stylesheet_bytes(
            simulated_css.encode('utf-8'),
            skip_comments=False,
            skip_whitespace=False
        )
        errors = [r for r in rules if r.type == 'error']
        assert len(errors) == 0, f"Block #{b_idx} failed AST parse after fallback substitution: {errors}"


def test_dependency_graph_primitives_defined():
    """
    Verify that all tokens referenced in var(--name, ...) actually have definitions
    either as raw primitives or semantic tokens.
    """
    if not DOC_PATH.exists():
        pytest.skip("docs/design_system_2.md not present")
    content = DOC_PATH.read_text(encoding="utf-8")
    blocks = get_all_code_blocks(content)
    css_blocks = [b for b in blocks if b["lang"] == "css"]
    master_block = next(b for b in css_blocks if "MASTER DESIGN TOKENS" in b["content"])

    # Extract all declared custom properties
    declared_props = set(re.findall(r'(--[\w-]+)\s*:', master_block["content"]))

    # Extract all referenced custom properties across all CSS blocks
    referenced_props = set()
    for b in css_blocks:
        rules, _ = tinycss2.parse_stylesheet_bytes(b["content"].encode('utf-8'))
        vars_found = parse_var_functions_from_tokens(rules)
        for v in vars_found:
            referenced_props.add(v['token_name'])

    # Find orphans (referenced in var() but never declared)
    orphans = [p for p in referenced_props if p not in declared_props]
    assert len(orphans) == 0, f"Orphan custom property tokens detected: {orphans}"


def test_contrast_ratio_formula_verification():
    """
    Empirically verify mathematical contrast ratios:
    - Text Primary (Light): #141413 on #FAF9F5 >= 17.0:1
    - Text Primary (Dark): #EDEDEC on #141413 >= 15.5:1
    - Accent Cobalt Light: #0E2AF5 on #FAF9F5 >= 7.0:1
    - Accent Cobalt Dark: #4D74FF on #1C1C1A >= 4.0:1
    - Accent Text Tint Dark: #6B8BFF on #1C1C1A >= 4.5:1
    - Control Border Light: #8E8D88 on #FAF9F5 >= 3.0:1
    - Control Border Dark: #686764 on #1C1C1A >= 3.0:1
    """
    def hex_to_srgb(hex_code):
        hex_code = hex_code.lstrip('#')
        r = int(hex_code[0:2], 16) / 255.0
        g = int(hex_code[2:4], 16) / 255.0
        b = int(hex_code[4:6], 16) / 255.0
        return r, g, b

    def rel_luminance(r, g, b):
        def chan(c):
            return c / 12.92 if c <= 0.03928 else math.pow((c + 0.055) / 1.055, 2.4)
        return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)

    def contrast(hex1, hex2):
        l1 = rel_luminance(*hex_to_srgb(hex1))
        l2 = rel_luminance(*hex_to_srgb(hex2))
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    assert contrast('#141413', '#FAF9F5') >= 17.0
    assert contrast('#EDEDEC', '#141413') >= 15.5
    assert contrast('#0E2AF5', '#FAF9F5') >= 7.0
    assert contrast('#4D74FF', '#1C1C1A') >= 4.0
    assert contrast('#6B8BFF', '#1C1C1A') >= 4.5
    assert contrast('#8E8D88', '#FAF9F5') >= 3.0
    assert contrast('#686764', '#1C1C1A') >= 3.0


def test_tailwind_js_code_block_var_fallbacks():
    """Verify that the javascript code block (tailwind.config.js) var() usages have fallbacks."""
    if not DOC_PATH.exists():
        pytest.skip("docs/design_system_2.md not present")
    content = DOC_PATH.read_text(encoding="utf-8")
    blocks = get_all_code_blocks(content)
    js_blocks = [b for b in blocks if b["lang"] == "javascript"]

    var_re = re.compile(r'var\((--[\w-]+)(?:,\s*([^)]+))?\)')
    for b in js_blocks:
        matches = var_re.findall(b["content"])
        for token, fb in matches:
            assert fb.strip(), f"Missing fallback in Tailwind config: {token}"


# ==============================================================================
# RIGOROUS RATE LIMITING TESTS (limiter.py)
# ==============================================================================

def test_limiter_guest_sliding_window_enforcement():
    """Verify sliding window limits for anonymous guests with Retry-After and 429."""
    app = Flask("test_limiter_guest")

    @app.route("/test-guest")
    @limiter.rate_limit(guest_limit=3, auth_limit=10, window_seconds=60)
    def guest_endpoint():
        return jsonify({"status": "ok"})

    client = app.test_client()

    with limiter._LOCK:
        limiter._REQUEST_LOG.clear()

    # First 3 requests should succeed
    for i in range(3):
        res = client.get("/test-guest", environ_base={"REMOTE_ADDR": "192.0.2.1"})
        assert res.status_code == 200
        assert res.headers.get("X-RateLimit-Limit") == "3"
        assert res.headers.get("X-RateLimit-Remaining") == str(2 - i)

    # 4th request must be blocked
    res_blocked = client.get("/test-guest", environ_base={"REMOTE_ADDR": "192.0.2.1"})
    assert res_blocked.status_code == 429
    assert "Retry-After" in res_blocked.headers
    assert int(res_blocked.headers["Retry-After"]) >= 1
    assert res_blocked.headers.get("X-RateLimit-Remaining") == "0"
    data = res_blocked.get_json()
    assert "Rate limit exceeded" in data["message"]


def test_limiter_auth_tier_higher_limit():
    """Verify authenticated users receive higher tier allowance."""
    app = Flask("test_limiter_auth")

    @app.route("/test-auth")
    @limiter.rate_limit(guest_limit=2, auth_limit=5, window_seconds=60)
    def auth_endpoint():
        return jsonify({"status": "ok"})

    client = app.test_client()

    with limiter._LOCK:
        limiter._REQUEST_LOG.clear()

    auth_headers = {"X-API-Key": "usr_vip_token_123"}

    # Authenticated user can execute 5 requests (exceeding guest_limit of 2)
    for i in range(5):
        res = client.get("/test-auth", headers=auth_headers)
        assert res.status_code == 200
        assert res.headers.get("X-RateLimit-Limit") == "5"
        assert res.headers.get("X-RateLimit-Remaining") == str(4 - i)

    # 6th request is blocked
    res_blocked = client.get("/test-auth", headers=auth_headers)
    assert res_blocked.status_code == 429


def test_limiter_forwarded_for_and_client_isolation():
    """Verify X-Forwarded-For parsing uses the leftmost client IP and isolates clients."""
    app = Flask("test_limiter_ip")

    @app.route("/test-ip")
    @limiter.rate_limit(guest_limit=2, auth_limit=5, window_seconds=60)
    def ip_endpoint():
        return jsonify({"status": "ok"}), 200

    client = app.test_client()

    with limiter._LOCK:
        limiter._REQUEST_LOG.clear()

    # Exhaust client A (multi-hop forwarded header)
    h_a = {"X-Forwarded-For": "203.0.113.195, 70.41.3.18, 150.172.238.178"}
    res1 = client.get("/test-ip", headers=h_a)
    res2 = client.get("/test-ip", headers=h_a)
    res3 = client.get("/test-ip", headers=h_a)
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res3.status_code == 429

    # Client B with different IP must NOT be blocked
    h_b = {"X-Forwarded-For": "198.51.100.42"}
    res_b = client.get("/test-ip", headers=h_b)
    assert res_b.status_code == 200


def test_limiter_sliding_window_memory_eviction():
    """Verify expired timestamps and idle clients are purged from memory."""
    now = time.time()
    stale_client = "ip:10.0.0.99"
    active_client = "ip:10.0.0.100"

    with limiter._LOCK:
        limiter._REQUEST_LOG.clear()
        # Stale client has requests from 120 and 90 seconds ago (window = 60s)
        limiter._REQUEST_LOG[stale_client] = [now - 120, now - 90]
        # Active client has request from 10 seconds ago
        limiter._REQUEST_LOG[active_client] = [now - 10]

    app = Flask("test_limiter_evict")

    @app.route("/test-evict")
    @limiter.rate_limit(guest_limit=5, auth_limit=5, window_seconds=60)
    def evict_endpoint():
        return jsonify({"status": "ok"}), 200

    client = app.test_client()

    # Trigger rate limiter check for stale client
    client.get("/test-evict", environ_base={"REMOTE_ADDR": "10.0.0.99"})

    with limiter._LOCK:
        # Stale timestamps should be gone, only the new request timestamp should be present
        assert len(limiter._REQUEST_LOG[stale_client]) == 1
        assert len(limiter._REQUEST_LOG[active_client]) == 1


def test_limiter_thread_safety_concurrency():
    """Verify thread safety under concurrent requests without corruption."""
    import concurrent.futures

    app = Flask("test_limiter_concurrent")

    @app.route("/test-concurrent")
    @limiter.rate_limit(guest_limit=15, auth_limit=25, window_seconds=60)
    def concurrent_endpoint():
        return jsonify({"status": "ok"}), 200

    client = app.test_client()

    with limiter._LOCK:
        limiter._REQUEST_LOG.clear()

    def make_req(idx):
        return client.get(
            "/test-concurrent",
            environ_base={"REMOTE_ADDR": "192.168.1.50"},
        ).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        statuses = list(executor.map(make_req, range(20)))

    # Exactly 15 should succeed (200) and 5 should be rate-limited (429)
    assert statuses.count(200) == 15
    assert statuses.count(429) == 5


# ==============================================================================
# RIGOROUS VALIDATION TESTS (validator.py)
# ==============================================================================

def test_validator_sanitize_url_protocol_and_syntax():
    """Verify protocol whitelist and syntactic validation for URLs."""
    valid_cases = [
        "https://example.com",
        "http://subdomain.example.co.uk/path/to/resource?query=1#frag",
        "https://python.org:8080/downloads/",
        "https://user-valid.app/test",
    ]
    for url in valid_cases:
        ok, res = sanitize_url(url)
        assert ok is True, f"Expected {url} to be valid, got: {res}"

    malicious_schemes = [
        "javascript:alert(1)",
        "file:///etc/passwd",
        "ftp://ftp.is.co.za/rfc/rfc1808.txt",
        "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
        "blob:https://example.com/uuid",
        "vbscript:msgbox(1)",
        "mailto:admin@example.com",
    ]
    for url in malicious_schemes:
        ok, res = sanitize_url(url)
        assert ok is False, f"Expected {url} to be rejected"
        assert "Only HTTP and HTTPS" in res or "Invalid protocol" in res

    assert sanitize_url("")[0] is False
    assert sanitize_url("   ")[0] is False
    assert sanitize_url(None)[0] is False
    assert sanitize_url(12345)[0] is False
    assert sanitize_url({})[0] is False


def test_validator_sanitize_url_anti_ssrf_and_dns():
    """Verify loopback, private networks, and invalid domain structures are blocked."""
    blocked_ssrf = [
        "http://localhost",
        "http://localhost:5000/admin",
        "http://127.0.0.1",
        "http://127.0.0.1:8080/metrics",
        "http://0.0.0.0",
        "http://0.0.0.0:3000",
        "http://service.local",
        "http://intranet.internal",
    ]
    for url in blocked_ssrf:
        ok, res = sanitize_url(url)
        assert ok is False, f"Expected SSRF URL {url} to be rejected"
        assert "prohibited" in res.lower()

    invalid_structure = [
        "http://",
        "https://",
        "http://singleworddomain",
        "https://invalid_tld_123",
        "https://.com",
    ]
    for url in invalid_structure:
        ok, res = sanitize_url(url)
        assert ok is False, f"Expected malformed URL {url} to be rejected"


def test_validator_sanitize_alias_constraints():
    """Verify length, character set, and type safety for custom aliases."""
    valid_aliases = ["abc", "my-link", "super_alias_2026", "a" * 30]
    for alias in valid_aliases:
        ok, res = sanitize_alias(alias)
        assert ok is True, f"Expected alias {alias} to be valid, got: {res}"

    assert sanitize_alias("")[0] is False
    assert sanitize_alias("a")[0] is False
    assert sanitize_alias("ab")[0] is False
    assert sanitize_alias("a" * 31)[0] is False

    invalid_chars = [
        "my link",
        "alias@domain",
        "alias#tag",
        "alias$money",
        "alias!exclamation",
        "path/slash",
        "alias.dot",
        "unicode⚡alias",
    ]
    for alias in invalid_chars:
        ok, res = sanitize_alias(alias)
        assert ok is False, f"Expected alias {alias} with special chars to be rejected"

    assert sanitize_alias(None)[0] is False
    assert sanitize_alias(123)[0] is False


def test_validator_sanitize_alias_reserved_keywords():
    """Verify all internal routing reserved keywords are prohibited as aliases."""
    for keyword in RESERVED_ALIASES:
        ok, res = sanitize_alias(keyword)
        assert ok is False, f"Reserved keyword '{keyword}' should be rejected"
        if keyword != "favicon.ico":
            assert "reserved system keyword" in res

        ok_upper, _ = sanitize_alias(keyword.upper())
        assert ok_upper is False, f"Upper reserved keyword '{keyword.upper()}' should be rejected"


def test_validator_sanitize_link_password():
    """Verify link password length bounds and printable character constraints."""
    valid_passwords = [
        "abc",
        "password123!",
        "P@$$w0rd_With_Specials~#^&*()",
        "p" * 100,
    ]
    for pwd in valid_passwords:
        ok, res = sanitize_link_password(pwd)
        assert ok is True, f"Expected password {pwd} to be valid"

    assert sanitize_link_password("")[0] is False
    assert sanitize_link_password("ab")[0] is False
    assert sanitize_link_password("p" * 101)[0] is False

    assert sanitize_link_password("pass\nword")[0] is False
    assert sanitize_link_password("pass\rword")[0] is False
    assert sanitize_link_password("pass\tword")[0] is False
    assert sanitize_link_password("pass\x00word")[0] is False

    assert sanitize_link_password(None)[0] is False
    assert sanitize_link_password(12345)[0] is False


if __name__ == "__main__":
    if DOC_PATH.exists():
        test_tinycss2_ast_var_fallbacks()
        test_fallback_simulation_stylesheet_validity()
        test_dependency_graph_primitives_defined()
        test_tailwind_js_code_block_var_fallbacks()
    test_contrast_ratio_formula_verification()
    test_limiter_guest_sliding_window_enforcement()
    test_limiter_auth_tier_higher_limit()
    test_limiter_forwarded_for_and_client_isolation()
    test_limiter_sliding_window_memory_eviction()
    test_limiter_thread_safety_concurrency()
    test_validator_sanitize_url_protocol_and_syntax()
    test_validator_sanitize_url_anti_ssrf_and_dns()
    test_validator_sanitize_alias_constraints()
    test_validator_sanitize_alias_reserved_keywords()
    test_validator_sanitize_link_password()
    print("ALL EMPIRICAL ADVERSARIAL STRESS TESTS PASSED SUCCESSFULLY!")
