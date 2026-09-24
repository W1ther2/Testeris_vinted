# -*- coding: utf-8 -*-
"""Busena tarp paleidimu: seen.json (matyti skelbimai) ir state.json (visa kita)."""

import json
import time

from . import config
from .market import Market
from .tracker import Tracker


def seen_key(key):
    """Seni irasai ('123') -> 'vinted:123'. Fingerprintai ('fp:...') nekeiciami."""
    k = str(key)
    return k if ":" in k or k.startswith("__") else "vinted:" + k


def load_seen(path=None):
    path = path or config.SEEN_FILE
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        data = json.loads(content) if content else {}
    except FileNotFoundError:
        return {}
    except Exception as e:
        print(f"! {path} sugadintas ({e}) – pradedama nuo tuscio.")
        return {}
    now = time.time()
    if isinstance(data, list):
        return {seen_key(x): now for x in data}
    out = {}
    if isinstance(data, dict):
        for k, v in data.items():
            try:
                out[seen_key(k)] = float(v)
            except (TypeError, ValueError):
                out[seen_key(k)] = now
    return out


def save_seen(seen, path=None):
    path = path or config.SEEN_FILE
    c = config.cfg
    now = time.time()
    # Kopija vienu zingsniu: kol vienas saltinis issaugo, kitas (kitoje gijoje) gali
    # prideti nauju irasu – iteruojant tiesiai zodyna tai baigdavosi
    # „dictionary changed size during iteration“ ir nutraukdavo to saltinio patikra.
    seen = dict(seen)
    fresh = {k: v for k, v in seen.items()
             if not k.startswith("__") and now - v <= c["SEEN_MAX_AGE_DAYS"] * 86400}
    newest = sorted(fresh.items(), key=lambda kv: kv[1], reverse=True)[: c["SEEN_MAX_ENTRIES"]]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dict(newest), f)


class State:
    """state.json: {"market": {...}, "telegram_offset": 0, "overrides": {}, "heartbeat": 0}"""

    # Padidinus – sena rinkos istorija isvaloma (pvz. kai pakeiciamos atrankos taisykles)
    MARKET_VERSION = 3

    def __init__(self, data=None):
        data = data or {}
        if data.get("market") and data.get("market_version", 1) < self.MARKET_VERSION:
            print("Rinkos kainu istorija isvalyta (nauja atranka: be sugedusiu ir priedu) – kaupsis is naujo.")
            data = {**data, "market": None}
        self.market = Market(data.get("market"))
        self.telegram_offset = int(data.get("telegram_offset") or 0)
        self.overrides = data.get("overrides") or {}
        self.heartbeat = float(data.get("heartbeat") or 0)
        self.last_run = data.get("last_run") or {}
        self.fail_streak = int(data.get("fail_streak") or 0)
        self.query_offset = int(data.get("query_offset") or 0)
        # {vartotojo_id: {"chat": privataus pokalbio id, "name": vardas,
        #                 "watch": [modeliai], "hide": [pardaveju id]}}
        self.users = data.get("users") or {}
        # {saltinio vardas: kada paskutini karta pranesta apie blokavima}
        self.source_alerts = data.get("source_alerts") or {}
        # {saltinio vardas: kiek paleidimu is eiles negauta nei vieno skelbimo}
        self.source_zero = data.get("source_zero") or {}
        # {saltinio vardas: nuo kada neveikia} – kad atsigavus galetume pranesti
        self.source_down = data.get("source_down") or {}
        # Pranesimu rezultatai (ar nupirkta ir per kiek) – zr. tracker.py
        self.tracker = Tracker(data.get("tracked"))
        self.last_report = float(data.get("last_report") or 0)
        # {uid: {"n": kiek kartu nepavyko atidaryti skelbimo, "t": kada paskutini karta}}
        self.detail_failures = data.get("detail_failures") or {}

    def note_detail_failure(self, uid, now=None):
        """Dar vienas nepavykes skelbimo atidarymas. Grazina, kiek kartu is viso."""
        e = self.detail_failures.get(uid) or {}
        e = {"n": int(e.get("n") or 0) + 1, "t": int(now if now is not None else time.time())}
        self.detail_failures[uid] = e
        return e["n"]

    def forget_detail_failure(self, uid):
        self.detail_failures.pop(uid, None)

    @classmethod
    def load(cls, path=None, seen=None):
        path = path or config.STATE_FILE
        state = None
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = cls(json.load(f))
        except FileNotFoundError:
            state = cls()
        except Exception as e:
            print(f"! {path} sugadintas ({e}) – pradedama nuo tuscio.")
            state = cls()
        if seen and "__heartbeat__" in seen and not state.heartbeat:
            state.heartbeat = seen["__heartbeat__"]
        return state

    def user(self, user_id, name=""):
        u = self.users.setdefault(str(user_id), {"watch": [], "hide": []})
        if name:
            u["name"] = name
        u.setdefault("watch", [])
        u.setdefault("hide", [])
        return u

    def save(self, path=None):
        path = path or config.STATE_FILE
        # Spyna laikoma per visa irasyma: kitas saltinis tuo metu gali rasyti naujus
        # skelbimus, o json.dump ju zodyno keisti nebegali.
        with self.market.lock:
            return self._save(path)

    def _save(self, path):
        self.market.prune()
        week_ago = time.time() - 7 * 86400
        self.detail_failures = {k: v for k, v in dict(self.detail_failures).items()
                                if isinstance(v, dict) and v.get("t", 0) >= week_ago}
        data = {"market_version": self.MARKET_VERSION, "market": self.market.to_dict(),
                "telegram_offset": self.telegram_offset,
                "overrides": self.overrides, "heartbeat": self.heartbeat, "last_run": self.last_run,
                "fail_streak": self.fail_streak, "query_offset": self.query_offset,
                "users": self.users, "source_alerts": self.source_alerts,
                "source_zero": self.source_zero, "source_down": self.source_down,
                "tracked": self.tracker.to_dict(), "last_report": self.last_report,
                "detail_failures": self.detail_failures}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
