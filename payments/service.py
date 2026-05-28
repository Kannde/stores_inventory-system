import json
import urllib.request
import urllib.error

SKRODA_BASE = "https://skroda.com/api/partner/v1"


def _call(method, path, secret_key, body=None):
    url = f"{SKRODA_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {secret_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return True, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read())
        except Exception:
            err_body = {"error": f"HTTP {e.code}"}
        return False, err_body
    except Exception as e:
        return False, {"error": str(e)}


def create_transaction(secret_key, *, title, amount, currency, seller_phone, seller_name,
                       buyer_phone=None, buyer_name=None, partner_reference=None,
                       category=None, fee_paid_by='buyer', description=''):
    payload = {
        "title": title,
        "amount": float(amount),
        "currency": currency,
        "seller": {"phone": seller_phone, "name": seller_name},
        "fee_paid_by": fee_paid_by,
    }
    if buyer_phone:
        payload["buyer"] = {"phone": buyer_phone}
        if buyer_name:
            payload["buyer"]["name"] = buyer_name
    if partner_reference:
        payload["partner_reference"] = str(partner_reference)
    if category:
        payload["category"] = category
    if description:
        payload["description"] = description
    return _call("POST", "/transactions", secret_key, payload)


def create_checkout_session(secret_key, *, transaction_id, success_url, cancel_url):
    return _call("POST", "/checkout", secret_key, {
        "transaction_id": transaction_id,
        "success_url": success_url,
        "cancel_url": cancel_url,
    })
