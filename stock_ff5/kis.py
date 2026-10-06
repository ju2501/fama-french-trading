"""Small KIS REST adapter. No automatic retries for order submissions."""
from dataclasses import dataclass, field
from datetime import datetime, time as clock_time
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

SEOUL = ZoneInfo("Asia/Seoul")
DOMAINS = {"paper": "https://openapivts.koreainvestment.com:29443",
           "live": "https://openapi.koreainvestment.com:9443"}


class BrokerError(RuntimeError):
    pass


@dataclass(frozen=True)
class Credentials:
    environment: str
    app_key: str = field(repr=False)
    app_secret: str = field(repr=False)
    cano: str = field(repr=False)
    product: str = field(repr=False)

    def __post_init__(self):
        if self.environment not in DOMAINS:
            raise ValueError("KIS_ENV must be paper or live")
        if not self.app_key or not self.app_secret:
            raise ValueError("KIS_APP_KEY and KIS_APP_SECRET are required")
        if not re.fullmatch(r"\d{8}", self.cano) or not re.fullmatch(r"\d{2}", self.product):
            raise ValueError("KIS_CANO must be 8 digits and KIS_ACNT_PRDT_CD 2 digits")

    @classmethod
    def from_env(cls):
        return cls(os.getenv("KIS_ENV", "paper"), os.getenv("KIS_APP_KEY", ""),
                   os.getenv("KIS_APP_SECRET", ""), os.getenv("KIS_CANO", ""),
                   os.getenv("KIS_ACNT_PRDT_CD", "01"))

    @property
    def identity(self):
        return hashlib.sha256(f"{self.environment}:{self.cano}:{self.product}".encode()).hexdigest()[:20]


def secure_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_name(path.name + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as out:
        json.dump(data, out, ensure_ascii=False, indent=2, allow_nan=False)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temp, path)


class KIS:
    def __init__(self, credentials, state_dir):
        self.credentials = credentials
        self.base_url = DOMAINS[credentials.environment]
        self.state_dir = Path(state_dir)
        self.token = None
        self.last_request = 0.0

    def _http(self, method, path, payload, headers):
        # Deliberately slow enough for typical demo-account rate limits.
        time.sleep(max(0, 0.7 - (time.monotonic() - self.last_request)))
        body = None
        url = self.base_url + path
        if method == "GET":
            url += "?" + urlencode(payload)
        else:
            body = json.dumps(payload).encode()
        request = Request(url, data=body, headers={"Content-Type": "application/json; charset=utf-8", **headers}, method=method)
        self.last_request = time.monotonic()
        try:
            with urlopen(request, timeout=20) as response:
                return json.load(response), {k.lower(): v for k, v in response.headers.items()}
        except HTTPError as exc:
            raise BrokerError(f"KIS HTTP {exc.code}; request was not retried") from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise BrokerError("KIS response unavailable/invalid; request was not retried") from None

    def authenticate(self):
        c = self.credentials
        key_id = hashlib.sha256(c.app_key.encode()).hexdigest()[:12]
        cache = self.state_dir / f"token-{c.identity}-{key_id}.json"
        if cache.exists():
            cached = json.loads(cache.read_text())
            if cached.get("expires_at", 0) > time.time() + 120:
                self.token = cached["access_token"]
                return
        result, _ = self._http("POST", "/oauth2/tokenP", {
            "grant_type": "client_credentials", "appkey": c.app_key, "appsecret": c.app_secret}, {})
        if not result.get("access_token") or float(result.get("expires_in", 0)) <= 120:
            raise BrokerError("Token issuance failed")
        self.token = result["access_token"]
        secure_write(cache, {"access_token": self.token, "expires_at": time.time() + float(result["expires_in"])})

    def _request(self, method, path, tr_id, payload, continuation=""):
        if self.token is None:
            self.authenticate()
        c = self.credentials
        result, headers = self._http(method, path, payload, {
            "authorization": f"Bearer {self.token}", "appkey": c.app_key,
            "appsecret": c.app_secret, "tr_id": tr_id, "custtype": "P", "tr_cont": continuation})
        if result.get("rt_cd") != "0":
            raise BrokerError(f"KIS rejected request ({result.get('msg_cd', 'unknown')}); inspect the broker account")
        return result, headers

    def _id(self, live):
        return "V" + live[1:] if self.credentials.environment == "paper" else live

    def _account(self):
        return {"CANO": self.credentials.cano, "ACNT_PRDT_CD": self.credentials.product}

    def _pages(self, path, tr_id, params):
        params = {**params, "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""}
        continuation, seen = "", set()
        for _ in range(100):
            data, headers = self._request("GET", path, tr_id, params, continuation)
            yield data
            if headers.get("tr_cont") not in ("M", "F"):
                return
            cursor = (data["ctx_area_fk100"], data["ctx_area_nk100"])
            if cursor in seen or not any(cursor):
                raise BrokerError("Invalid pagination; refusing a partial account snapshot")
            seen.add(cursor)
            params.update(CTX_AREA_FK100=cursor[0], CTX_AREA_NK100=cursor[1])
            continuation = "N"
        raise BrokerError("Pagination limit exceeded")

    def balance(self):
        positions, sellable, summary = {}, {}, None
        for page in self._pages("/uapi/domestic-stock/v1/trading/inquire-balance", self._id("TTTC8434R"), {
            **self._account(), "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02", "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N", "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "00"}):
            for item in page["output1"]:
                quantity = int(item["hldg_qty"])
                if quantity:
                    positions[item["pdno"]] = quantity
                    sellable[item["pdno"]] = int(item["ord_psbl_qty"])
            if summary is None:
                summary = page["output2"][0]
        equity = float(summary["tot_evlu_amt"])
        if not math.isfinite(equity) or equity <= 0:
            raise BrokerError("Invalid account valuation")
        return {"positions": positions, "sellable": sellable, "equity": equity}

    def pending_orders(self, date):
        rows = []
        for page in self._pages("/uapi/domestic-stock/v1/trading/inquire-daily-ccld", self._id("TTTC0081R"), {
            **self._account(), "INQR_STRT_DT": date, "INQR_END_DT": date,
            "SLL_BUY_DVSN_CD": "00", "PDNO": "", "CCLD_DVSN": "02", "INQR_DVSN": "00",
            "INQR_DVSN_3": "00", "ORD_GNO_BRNO": "", "ODNO": "", "INQR_DVSN_1": "", "EXCG_ID_DVSN_CD": "KRX"}):
            rows.extend(page["output1"])
        return [item for item in rows if int(item["rmn_qty"]) > 0]

    def quote(self, symbol):
        data, _ = self._request("GET", "/uapi/domestic-stock/v1/quotations/inquire-price", "FHKST01010100", {
            "FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": symbol})
        price = int(data["output"]["stck_prpr"])
        if price <= 0:
            raise BrokerError("Invalid quote")
        return price

    def buying_power(self, symbol):
        data, _ = self._request("GET", "/uapi/domestic-stock/v1/trading/inquire-psbl-order", self._id("TTTC8908R"), {
            **self._account(), "PDNO": symbol, "ORD_UNPR": "0", "ORD_DVSN": "01",
            "CMA_EVLU_AMT_ICLD_YN": "N", "OVRS_ICLD_YN": "N"})
        out = data["output"]
        amount, quantity = float(out["nrcvb_buy_amt"]), int(out["nrcvb_buy_qty"])
        if not math.isfinite(amount) or amount < 0 or quantity < 0:
            raise BrokerError("Invalid cash-only buying power")
        return amount, quantity

    def order(self, symbol, side, quantity, limit_price):
        if side not in ("buy", "sell") or type(quantity) is not int or quantity <= 0:
            raise ValueError("Invalid order")
        if not re.fullmatch(r"\d{6}", symbol) or type(limit_price) is not int or limit_price <= 0:
            raise ValueError("Invalid symbol or limit price")
        data, _ = self._request("POST", "/uapi/domestic-stock/v1/trading/order-cash",
            self._id("TTTC0012U" if side == "buy" else "TTTC0011U"), {
                **self._account(), "PDNO": symbol, "ORD_DVSN": "00", "ORD_QTY": str(quantity),
                "ORD_UNPR": str(limit_price), "EXCG_ID_DVSN_CD": "KRX",
                "SLL_TYPE": "01" if side == "sell" else "", "CNDT_PRIC": ""})
        number = data["output"].get("ODNO")
        if not number:
            raise BrokerError("Order response lacks an order number; reconcile before retrying")
        return str(number)


def require_session(now, sessions_file):
    import csv
    local = now.astimezone(SEOUL)
    with open(sessions_file, newline="") as source:
        dates = {r["date"] for r in csv.DictReader(source)}
    if local.date().isoformat() not in dates or local.weekday() >= 5:
        raise ValueError("Today is not in the supplied KRX session calendar")
    if not clock_time(9, 10) <= local.time().replace(tzinfo=None) <= clock_time(15, 10):
        raise ValueError("Submission window is 09:10–15:10 Asia/Seoul")


def plan_orders(weights, account, quotes, buying_power, budget, max_order_value):
    if not math.isfinite(budget) or budget <= 0 or not math.isfinite(max_order_value) or max_order_value <= 0:
        raise ValueError("Positive finite budget/order limit required")
    if any(not math.isfinite(w) or w < 0 or w > 1 for w in weights.values()) or sum(weights.values()) > 1 + 1e-9:
        raise ValueError("Invalid portfolio weights")
    equity = min(budget, account["equity"])
    symbols = set(weights) | set(account["positions"])
    orders = []
    # Do not finance buys with as-yet-unfilled sells. Reserve a 1% fee/cash cushion.
    cash = min((v[0] for v in buying_power.values()), default=0) * 0.99
    for symbol in sorted(symbols):
        price = quotes[symbol]
        if type(price) is not int or price <= 0:
            raise ValueError("Quotes must be positive integer KRW prices")
        target = math.floor(equity * weights.get(symbol, 0) / price)
        difference = target - account["positions"].get(symbol, 0)
        if difference < 0:
            quantity = min(-difference, account["sellable"].get(symbol, 0))
            side = "sell"
        else:
            quantity = min(difference, buying_power[symbol][1], math.floor(cash / (price * 1.01)))
            side = "buy"
        quantity = min(quantity, math.floor(max_order_value / price))
        if quantity > 0:
            orders.append({"symbol": symbol, "side": side, "quantity": int(quantity), "limit_price": price})
            if side == "buy":
                cash -= quantity * price * 1.01
    return sorted(orders, key=lambda o: (o["side"] != "sell", o["symbol"]))


def execute_batch(broker, orders, signal_result, state_dir, allow_live=False):
    """Durable monthly claim BEFORE any orders. Ambiguous requests are never replayed.

    Callers must enforce session/data/preflight gates before invoking this function.
    A returned order id indicates acceptance only; the operator must check fills.
    """
    if signal_result["synthetic"]:
        raise ValueError("Synthetic data cannot be used for broker orders")
    if broker.credentials.environment == "live" and not allow_live:
        raise ValueError("Live submission requires --allow-live")
    root = Path(state_dir)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Key independent of weights/config: changing a signal cannot double-submit.
    month = signal_result["as_of"][:7]
    journal = root / f"rebalance-{broker.credentials.identity}-{month}.json"
    try:
        fd = os.open(journal, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise BrokerError("This account/month was already claimed; inspect its journal and broker fills") from None
    state = {"as_of": signal_result["as_of"], "factor_month": signal_result["factor_month"],
             "status": "claimed", "orders": orders, "accepted": []}
    with os.fdopen(fd, "w") as out:
        json.dump(state, out)
        out.flush()
        os.fsync(out.fileno())
    for index, order in enumerate(orders):
        state.update(status="submitting", pending_index=index)
        secure_write(journal, state)
        try:
            number = broker.order(**order)
        except Exception:
            state["status"] = "unknown_or_rejected_check_broker"
            secure_write(journal, state)
            raise
        state["accepted"].append({"index": index, "order_number": number})
        state["status"] = "accepted_not_confirmed_filled"
        secure_write(journal, state)
    state["status"] = "submitted_check_fills" if orders else "no_orders"
    state.pop("pending_index", None)
    secure_write(journal, state)
    return state
