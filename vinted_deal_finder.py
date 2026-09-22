# -*- coding: utf-8 -*-
"""
iPhone deal finder v20.

Iesko iPhone 8 … 17 Pro Max, kurie pigesni uz rinkos kaina (ivertinus bukle,
baterija ir defektus), ir siuncia juos i Telegram.

Saltiniai ijungiami config.json rakte "SOURCES" (dabar: vinted, skelbiu). Naujas saltinis –
vienas failas vinted/sources/, zr. README.

Paleidimas:   python vinted_deal_finder.py
Reikia:       pip install requests curl_cffi
Aplinka:      BOT_TOKEN, CHAT_ID (GitHub Secrets)
Failai:       config.json (nustatymai), seen.json ir state.json (issaugomi tarp paleidimu)
Testai:       python -m unittest discover tests
"""

from vinted.finder import main

if __name__ == "__main__":
    main()
