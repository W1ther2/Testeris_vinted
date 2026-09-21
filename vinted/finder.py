# -*- coding: utf-8 -*-
"""Pagrindine logika: saltiniai -> vertinimas -> Telegram."""

import hashlib
import html
import time
import traceback

from . import config, commands
from .language import detect_foreign_language
from .listing import split_uid
from .phone import (detect_model, is_accessory, find_defects, extract_storage, extract_battery,
                    CONDITION_FACTOR, estimate_value, estimate_profit, MODEL_ORDER, condition_ok,
                    description_not_phone, min_price)
from .risk import assess_risk, PICKUP_LABEL
from .sources import build_sources
from .sources.vinted_source import VintedSource
from .state import State, load_seen, save_seen
from .telegram import Telegram
from .util import human_age


class Run:
    def __init__(self, sources, telegram, sleep=time.sleep):
        # Suderinamumas: perdavus viena klienta (senas budas / testai) apvyniojam Vinted saltiniu.
        if not isinstance(sources, (list, tuple)):
            sources = [VintedSource(client=sources)]
        self.started = time.time()
        self.sources = list(sources)
        self.tg = telegram
        self.sleep = sleep
        self.totals = {}
        self.examples = []
        self.alerts = []
        self.last_error = ""

    def reject(self, reason, example=None):
        self.totals[reason] = self.totals.get(reason, 0) + 1
        if example and len(self.examples) < 5:
            self.examples.append(f"{reason}: {example}")

    # --- vieno skelbimo vertinimas ---------------------------------------------
    def evaluate(self, source, listing, drops):
        c = config.cfg
        uid = listing.uid
        title = listing.title or "?"
        price = listing.price
        drop_from = None

        if uid in self.new_seen:
            prev = drops.get(uid)
            if not (c["PRICE_DROP_ALERTS"] and prev and price is not None
                    and price <= prev * (1 - c["PRICE_DROP_MIN"])):
                return self.reject("jau matyti")
            if self.state.market.already_alerted_at(uid, price):
                return self.reject("jau matyti")
            drop_from = prev

        model = detect_model(title)
        if model and hasattr(source, "note_ids"):
            source.note_ids(listing)      # renkam ID tik tikriems telefonams – pagal juos nustatysim filtra
        if not model or is_accessory(title) or price is None:
            self.new_count += 0 if drop_from else 1
            self.new_seen[uid] = time.time()
            return self.reject("ne telefonas / kitas modelis")

        # 1) Greitas patikrinimas pagal rinkos kaina (be skelbimo puslapio)
        storage = extract_storage(title)
        quote = self.state.market.quote(model, storage)
        if quote is None:
            # nezymim kaip matyto – kai atsiras duomenu, ivertinsim
            return self.reject("per mazai kainu duomenu",
                               f"iPhone {model} ({self.state.market.sample_count(model)} skelb.)")
        if not drop_from:
            self.new_count += 1
        cat_condition = listing.condition
        if c["TIDY_ONLY"] and not condition_ok(cat_condition, c["MIN_CONDITION"]):
            self.new_seen[uid] = time.time()
            return self.reject(f"būklė {cat_condition}")
        best_case = quote.price * CONDITION_FACTOR.get(cat_condition, 1.08) * 1.03
        if price > best_case * (1 - c["MIN_DISCOUNT"]):
            self.new_seen[uid] = time.time()
            return self.reject("per brangu")
        # Riba: 40% rinkos kainos arba modelio minimali kaina – kuri mazesne (kad
        # apytiksle kaina ar mano ivertinta minimali kaina neatmestu tikru pigiu telefonu)
        floor = min(quote.price * c["HARD_MIN_PRICE_RATIO"], min_price(model) or float("inf"))
        if price < floor:
            self.new_seen[uid] = time.time()
            return self.reject("per pigu (sugedęs / dalims / ne telefonas?)",
                               f"{title[:40]} {price:.0f}€ (riba {floor:.0f}€, rinka {quote.price:.0f}€)")
        self.new_seen[uid] = time.time()

        # 2) Skelbimo puslapis
        detail = source.detail(listing)
        self.sleep(c["DETAIL_SLEEP_SECONDS"])
        if detail.status in ("sold", "gone"):
            self.state.market.set_status(uid, detail.status)
            return self.reject("jau parduotas" if detail.status == "sold" else "skelbimo nebėra")
        description = detail.description or ""
        if description_not_phone(description) or detect_model(detail.title or title) is None:
            return self.reject("ne telefonas (pagal aprašymą)", f"{title[:40]} | {description[:60]}")

        if c["ONLY_LITHUANIAN_TEXT"]:
            lang = detect_foreign_language(detail.title or title, description)
            if lang and lang not in config.allowed_languages():
                return self.reject("kalba", f"{lang}: {title[:40]} | {description[:50]}")

        defects = find_defects(title, description)
        if any(f == 0 for _, f in defects):
            return self.reject("neveikiantis / užrakintas / netestuotas", f"{title[:40]} {[d for d, _ in defects]}")
        if c["TIDY_ONLY"]:
            allowed = set(c["ALLOWED_DEFECTS"])
            bad = [d for d, _ in defects if d not in allowed]
            if bad:
                return self.reject("defektai", f"{title[:40]} {bad}")
        condition = detail.condition or cat_condition
        if c["TIDY_ONLY"] and not condition_ok(condition, c["MIN_CONDITION"]):
            return self.reject(f"būklė {condition}")

        storage = storage or extract_storage(description)
        quote = self.state.market.quote(model, storage) or quote
        battery = extract_battery(title, description)
        value = estimate_value(quote.price, condition, battery, defects)
        discount = 1 - price / value
        if discount < c["MIN_DISCOUNT"]:
            how = f"tik {discount:.0%} pigiau" if discount > 0 else f"{-discount:.0%} brangiau"
            return self.reject("ne pakankamai pigu", f"iPhone {model} {price:.0f}€, vertė {value:.0f}€ ({how})")

        # Baterija: nurodyta ir per maza – atmetam, nebent kaina tikrai gera.
        # Nenurodyta – praleidziam, bet kortelėje parasom "nenurodyta".
        battery_low = False
        if c["MIN_BATTERY"] and battery is not None and battery < c["MIN_BATTERY"]:
            if discount < c["LOW_BATTERY_MIN_DISCOUNT"]:
                return self.reject("baterija", f"{title[:40]} {battery}%")
            battery_low = True

        # 3) Pardavejas
        seller = detail.seller or listing.seller or {}
        country = seller.get("country")
        if c["FILTER_BY_COUNTRY"]:
            ok = (country in c["ALLOWED_COUNTRY_CODES"]) if country else (not c["REQUIRE_KNOWN_COUNTRY"])
            if not ok:
                return self.reject("salis", f"{country}: {title[:40]}")
        rating, reviews = seller.get("rating"), seller.get("reviews")
        if rating is not None and reviews is not None and (
                rating < c["MIN_SELLER_RATING"] or reviews < c["MIN_SELLER_REVIEWS"]):
            return self.reject("pardavejas", f"{rating}/5, {reviews} atsil.: {title[:40]}")

        fp = "fp:" + hashlib.sha1(
            f"{listing.seller_id}|{model}|{storage}|{price:.0f}".encode()).hexdigest()[:16]
        if fp in self.new_seen:
            return self.reject("dublikatai")

        risk_level, risk_reasons = assess_risk(detail.title or title, description, price, quote.price,
                                               seller, listing.photo_count)
        profit = estimate_profit(price, value, pickup_only=PICKUP_LABEL in risk_reasons)

        deal = {
            "id": uid, "source": source.name, "source_label": getattr(source, "label", source.name),
            "model": model, "seller_id": listing.seller_id, "storage": storage, "title": title,
            "price": price, "url": listing.url, "photo": listing.photo or detail.photo,
            "description": description, "condition": condition, "battery": battery,
            "battery_low": battery_low, "defects": [d for d, _ in defects],
            "quote": quote, "value": value, "discount": discount, "profit": profit,
            "seller": seller, "risk_level": risk_level, "risk_reasons": risk_reasons,
            "drop_from": drop_from, "created_at": listing.created_at,
            "age": human_age(listing.created_at),
        }
        if c["PAUSED"]:
            return self.reject("pauzė (/testi – įjungti)")
        self.new_seen[fp] = time.time()
        return deal

    # --- visas paleidimas --------------------------------------------------------
    def out_of_time(self):
        limit = config.cfg["MAX_RUN_MINUTES"]
        return limit > 0 and (time.time() - self.started) / 60 >= limit

    def send_personal(self, deal):
        """Asmenines zinutes tiems, kas paspaude 🔔 ties siuo modeliu."""
        for uid, u in self.state.users.items():
            chat = u.get("chat")
            if not chat or deal["model"] not in (u.get("watch") or []):
                continue
            if deal.get("seller_id") and deal["seller_id"] in (u.get("hide") or []):
                continue
            self.tg.send_deal(deal, chat_id=chat)
            print(f"     -> asmeniskai: {u.get('name') or uid}")

    def process_commands(self):
        if not config.cfg["TELEGRAM_COMMANDS"]:
            return
        messages, callbacks, offset = self.tg.get_updates(self.state.telegram_offset)
        for m in messages:
            if m["private"]:
                reply = commands.handle_private(m, self.state)
                print(f"Asmenine komanda ({m['name']}): {m['text'][:40]}")
                self.tg.send_message(reply, chat_id=m["chat"])
            elif commands.is_admin(m["user"]):
                reply = commands.handle(m["text"], self.state)
                if reply:
                    print(f"Komanda ({m['name']}): {m['text'][:50]}")
                    self.tg.send_message(reply)
            else:
                # Grupeje komandos is kitu zmoniu ignoruojamos – nieko neatskleidziam
                print(f"Ignoruota komanda grupeje ({m['name']}): {m['text'][:40]}")
        for cb in callbacks:
            answer = commands.handle_callback(cb, self.state)
            print(f"Mygtukas ({cb['name']}): {cb['data']} -> {answer[:40]}")
            self.tg.answer_callback(cb["id"], answer)
        if offset != self.state.telegram_offset:
            self.state.telegram_offset = offset
            self.state.save()

    def check_sold(self):
        """Senus skelbimus tikrinam tame saltinyje, is kurio jie atejo."""
        by_name = {s.name: s for s in self.sources}
        found = {"sold": 0, "gone": 0}
        for uid in self.state.market.sold_check_candidates():
            if self.out_of_time():
                break
            source_name, local_id = split_uid(uid)
            source = by_name.get(source_name)
            if source is None:
                continue
            st = source.status(local_id)
            self.state.market.set_status(uid, st)
            if st in found:
                found[st] += 1
            self.sleep(config.cfg["DETAIL_SLEEP_SECONDS"])
        if any(found.values()):
            extra = " (dingusius laikom parduotais)" if config.cfg["GONE_AS_SOLD"] else ""
            print(f"Pardavimu patikra: parduota {found['sold']}, dingo {found['gone']}{extra}")

    def rotated(self, queries):
        """Kiekviena paleidima pradedam nuo kito modelio – kad tie patys nebutu
        visada tikrinami paskutiniai (ir apie ju dealus suzinotum veliausiai)."""
        c = config.cfg
        if not c["ROTATE_QUERIES"] or not queries:
            return list(queries)
        start = self.state.query_offset % len(queries)
        return list(queries[start:]) + list(queries[:start])

    def scan(self, source, seen, pages):
        """Viena saltinio perziura. Grazina, kiek skelbimu gauta."""
        c = config.cfg
        fetched = 0
        source.start()
        queries = self.rotated(source.queries())
        if c["ROTATE_QUERIES"] and queries:
            print(f"[{source.label}] pradedama nuo: '{queries[0]}'")
        for q in queries:
            if self.out_of_time():
                print(f"! Pasiektas laiko limitas ({c['MAX_RUN_MINUTES']} min.) – "
                      "likusius modelius tikrinsiu kitame paleidime.")
                break
            if source.blocked_queries >= c["STOP_AFTER_BLOCKED_QUERIES"]:
                print(f"! {source.label} blokuoja uzklausas ({source.blocked_queries} paieskos is eiles) – "
                      "baigiu si saltini, tesim kitame paleidime.")
                break
            print(f"Tikrinama [{source.label}]: '{q}'...")
            listings = source.search(q, pages, seen)
            self.last_error = source.last_error or self.last_error
            fetched += len(listings)
            drops = self.state.market.observe(listings)
            self.examples, sent_before = [], len(self.alerts)
            for listing in listings:
                if self.out_of_time():
                    break
                deal = self.evaluate(source, listing, drops)
                if not deal:
                    continue
                self.alerts.append(deal)
                self.state.market.mark_alerted(deal["id"], deal["price"])
                silent = deal["discount"] < c["LOUD_DISCOUNT"]
                self.tg.send_deal(deal, silent=silent)
                self.send_personal(deal)
                tag = f"atpigo nuo {deal['drop_from']:.0f}, " if deal["drop_from"] else ""
                print(f"  -> [{source.label}] iPhone {deal['model']} {deal['price']:.0f} EUR "
                      f"({tag}-{deal['discount']:.0%}{', tyliai' if silent else ''}): {deal['title'][:45]}")
                save_seen(self.new_seen)
                self.state.save()
                self.sleep(1)
            print(f"  Gauta: {len(listings)}, tinkama: {len(self.alerts) - sent_before}")
            for ex in self.examples:
                print(f"    atmesta – {ex}")
            self.sleep(c["SLEEP_SECONDS"])
        source.finish(self)
        return fetched

    def run(self):
        c = config.cfg
        seen = load_seen()
        self.state = State.load(seen=seen)
        config.apply_overrides(self.state.overrides)
        self.process_commands()

        self.new_seen = dict(seen)
        self.new_seen.pop("__heartbeat__", None)
        self.new_count = 0

        pages = c["PAGES"] if seen else max(c["PAGES"], c["FULL_SCAN_PAGES"])
        if not seen:
            print(f"seen.json tuscias – pilnas perziurejimas ({pages} psl. kiekvienai paieskai)")

        fetched = 0
        for i, source in enumerate(self.sources):
            if i and self.out_of_time():
                break
            fetched += self.scan(source, seen, pages)

        queries = config.cfg["SEARCH_QUERIES"]
        if c["ROTATE_QUERIES"] and queries:
            start = self.state.query_offset % len(queries)
            self.state.query_offset = (start + max(1, len(queries) // 3)) % len(queries)

        if c["USE_SOLD_PRICES"]:
            self.check_sold()

        self.print_market()
        summary = ", ".join(f"{k}: {n}" for k, n in sorted(self.totals.items(), key=lambda kv: -kv[1]))
        print(f"IS VISO: gauta {fetched}, tinkama {len(self.alerts)}. Atmesta – {summary}")
        self.heartbeat(fetched, summary)
        self.state.last_run = {"time": int(time.time()), "fetched": fetched, "new": self.new_count,
                               "sent": len(self.alerts), "totals": self.totals}
        if fetched == 0:
            self.state.fail_streak += 1
            print(f"! Negauta skelbimu ({self.state.fail_streak} paleidimas is eiles): {self.last_error}")
            # Vienkartinis 403 = laikinas blokas serverio IP; pranesam tik jei kartojasi
            if self.state.fail_streak >= c["FAIL_ALERT_RUNS"]:
                self.tg.send_message(
                    f"<b>ISPEJIMAS</b>: {self.state.fail_streak} paleidimus is eiles negauta nei vieno "
                    "skelbimo.\nGalimai pasikeite API arba saltinis blokuoja – patikrink logus.\n"
                    f"Priezastis: <code>{html.escape(self.last_error or 'nezinoma')}</code>")
                self.state.fail_streak = 0
        else:
            self.state.fail_streak = 0

        self.state.save()
        save_seen(self.new_seen)

        print(f"Issiusta {len(self.alerts)} alert'u." if self.alerts else "Nauju deal'u nera.")

    def print_market(self):
        manual = config.market_prices()
        rows = {m: r for m, *r in self.state.market.summary()}
        print("Rinkos kainos (rankinė / parduotų mediana / prasomu kainu percentilis):")
        for model in MODEL_ORDER:
            if model not in rows and model not in manual:
                continue
            a, n, s, ns = rows.get(model, (None, 0, None, 0))
            print(f"  iPhone {model:<11} rankinė: {manual.get(model, 0):>4.0f}  "
                  f"parduoti: {s or 0:>4.0f} ({ns})  skelbimai: {a or 0:>4.0f} ({n})")

    def heartbeat(self, fetched, summary):
        hours = config.cfg["HEARTBEAT_HOURS"]
        if hours <= 0 or time.time() - self.state.heartbeat < hours * 3600:
            return
        sources = ", ".join(s.label for s in self.sources)
        self.tg.send_message("✅ <b>Skriptas veikia</b>\n"
                             f"Šaltiniai: {html.escape(sources)}\n"
                             f"Šis paleidimas: gauta {fetched} skelb., naujų {self.new_count}, "
                             f"išsiųsta {len(self.alerts)}.\n"
                             f"<i>Atmesta – {html.escape(summary or 'nieko')}</i>", silent=True)
        self.state.heartbeat = time.time()


def main():
    config.load()
    if not config.BOT_TOKEN or not config.CHAT_ID:
        print("Nenurodyti BOT_TOKEN / CHAT_ID (GitHub Secrets)!")
        return
    tg = Telegram()
    try:
        Run(build_sources(), tg).run()
    except Exception as e:
        print(traceback.format_exc())
        tg.send_message("<b>SKRIPTAS UZLUZO</b>\n" + html.escape(str(e)[:400]))
