#!/usr/bin/env python3
"""
Minimal Stripe test-mode client (stdlib only) for the MPP spend flow.

When a Stripe TEST key is present, the MPP planner can create real test-mode
PaymentIntents so the founder sees genuine authorization objects in their
Stripe test dashboard instead of fabricated ids. Safety is built in:

- Only `sk_test_...` keys are accepted. A live key (`sk_live_...`) is refused
  outright -- this tool will never touch live money.
- Intents are created UNCONFIRMED and UNCAPTURED (no payment method attached),
  so even in test mode no charge is ever authorized or captured. They are
  pure "authorization pending founder approval" records.
- Test mode moves no real money regardless.

Callers use `available()` to branch, and fall back to a clearly-labelled
simulation when no test key is configured (see mpp_spend_planner.py).
"""

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request

PAYMENT_INTENTS_ENDPOINT = "https://api.stripe.com/v1/payment_intents"
TEST_KEY_PREFIX = "sk_test_"


def get_test_key():
    """Return a configured Stripe TEST key, or None.

    A placeholder or a non-test key returns None so callers degrade to
    simulation rather than doing anything with a live key.
    """
    key = os.environ.get("STRIPE_API_KEY", "").strip()
    if not key or key.startswith("replace_with"):
        return None
    if not key.startswith(TEST_KEY_PREFIX):
        # Refuse live/unknown keys loudly; never fall through to using them.
        print("⚠️  STRIPE_API_KEY is not a test key (sk_test_...); refusing to use it. "
              "MPP will stay in simulation.")
        return None
    return key


def available():
    return get_test_key() is not None


def dashboard_url(intent_id):
    return f"https://dashboard.stripe.com/test/payments/{intent_id}"


def create_authorization_intent(amount_cents, currency="usd", metadata=None, timeout=15):
    """Create an unconfirmed test-mode PaymentIntent (no charge).

    Returns a dict {id, status, dashboard_url, mode:"test"} on success, or a
    dict {error: <message>} on failure so the caller can fall back to
    simulation without crashing the pipeline.
    """
    key = get_test_key()
    if key is None:
        return {"error": "no test key configured"}

    if not isinstance(amount_cents, int) or amount_cents <= 0:
        return {"error": f"invalid amount_cents: {amount_cents!r}"}

    fields = [
        ("amount", str(amount_cents)),
        ("currency", currency),
        # No payment method + no confirm => status requires_payment_method,
        # i.e. authorization pending, zero charge.
        ("payment_method_types[]", "card"),
        ("capture_method", "manual"),
        ("description", "Flywheel MPP authorization (pending founder approval)"),
    ]
    for k, v in (metadata or {}).items():
        fields.append((f"metadata[{k}]", str(v)))

    body = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        PAYMENT_INTENTS_ENDPOINT,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", "")
        except Exception:
            pass
        return {"error": f"stripe HTTP {exc.code}: {detail or exc.reason}"}
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError, ValueError) as exc:
        # socket.timeout is distinct from TimeoutError before Python 3.10.
        return {"error": f"stripe request failed: {exc}"}

    intent_id = data.get("id")
    if not intent_id:
        return {"error": "stripe response had no intent id"}
    return {
        "id": intent_id,
        "status": data.get("status", "requires_payment_method"),
        "dashboard_url": dashboard_url(intent_id),
        "mode": "test",
    }
