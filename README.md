# iPhone deal finder

Ieško iPhone 8 … 17 Pro Max, kurie pigesni už rinkos kainą, ir siunčia juos į Telegram.
Šaltiniai įjungiami `config.json` → `"SOURCES": ["vinted", "skelbiu"]`.

| Šaltinis | Kaip veikia | Ypatumai |
|---|---|---|
| `vinted` | katalogo API (`api.vinted.lt`) | būklė, pardavėjo įvertinimai, pirkėjo apsaugos mokestis |
| `skelbiu` | įprastas puslapis (API nėra) | įvertinimų nėra, atsiskaitoma tiesiogiai, tad mokesčio pelne nėra |

## Failai

| Failas | Kas tai |
|---|---|
| `vinted_deal_finder.py` | paleidimo failas |
| `vinted/` | kodas (modulis per temą) |
| `tests/` | automatiniai testai (`python -m unittest discover tests`) |
| `config.json` | nustatymai |
| `seen.json`, `state.json` | sukuriami automatiškai, išsaugomi tarp paleidimų |
| `.github/workflows/vinted.yml` | GitHub Actions pavyzdys |

## Kodo struktūra

| Modulis | Atsakingas už |
|---|---|
| `config.py` | nustatymai, Telegram komandų pakeitimai |
| `listing.py` | bendra skelbimo forma (`Listing`, `Detail`) – nepriklauso nuo šaltinio |
| `sources/` | šaltiniai: `base.py` (sąsaja), `vinted_source.py`, `skelbiu.py` |
| `client.py` | Vinted API: sesija, katalogas, skelbimo puslapis, pardavėjas |
| `parsing.py` | kaina, būklė, pardavėjo duomenys, ar skelbimas parduotas |
| `language.py` | kalbos atpažinimas |
| `phone.py` | modelis, priedai, defektai, talpa, baterija, vertė, pelnas |
| `risk.py` | apgavysčių požymiai |
| `market.py` | rinkos kainos, pardavimai, kainų sumažėjimai |
| `state.py` | `seen.json`, `state.json` |
| `telegram.py` | kortelės, žinutės, komandų gavimas |
| `commands.py` | Telegram komandos |
| `finder.py` | pagrindinė eiga |

## Kaip pridėti naują šaltinį (Skelbiu, ES Vinted, ...)

Visa atrankos logika dirba su `Listing` ir `Detail`, o ne su konkrečios svetainės JSON.
Naujas šaltinis – vienas failas `vinted/sources/`:

```python
from ..listing import Listing, Detail
from .base import Source

class SkelbiuSource(Source):
    name = "skelbiu"          # pateks į ID: "skelbiu:123" – vėliau nebekeisti
    label = "Skelbiu"

    def search(self, query, pages, seen=None):
        ...                    # -> [Listing, ...]

    def detail(self, listing):
        ...                    # -> Detail(status, description, condition, seller)

    def status(self, listing_id):
        ...                    # "active" / "sold" / "gone"
```

Toliau įrašyti klasę į `vinted/sources/__init__.py` → `REGISTRY` ir į `config.json` →
`"SOURCES": ["vinted", "skelbiu"]`. Nieko kito keisti nereikia: rinkos kainos, dublikatų
tikrinimas, kortelės ir asmeninės žinutės veikia vienodai visiems šaltiniams.

Kelis kartus iš naujo įkeltas tas pats telefonas atmetamas pagal
`šaltinis | pardavėjas | modelis | talpa | kaina`. Kai pardavėjo nustatyti nepavyksta,
naudojamas paties skelbimo ID — taip geriau praleisti dublikatą nei suplakti į krūvą
du skirtingus žmones, pardavinėjančius tą patį modelį už tą pačią kainą.

### Lygiagretus tikrinimas

Šaltiniai tikrinami **vienu metu**, kiekvienas savo gijoje (`PARALLEL_SOURCES: true`).
Jie eina į skirtingus serverius, tad vienas kito nelaukia ir nedidina blokavimo rizikos —
vienoje svetainėje užklausų kiekis lieka toks pat kaip anksčiau. Kiekvienas šaltinis
gauna visą `MAX_RUN_MINUTES`, o pranešimai krenta iš karto, nelaukiant, kol kitas baigs.

Bendri duomenys — rinkos istorija, matytų sąrašas, `state.json`, Telegram — liečiami
tik per vieną spyną. Be jos, kai vienas šaltinis rašo naują skelbimą, o kitas tuo metu
skaičiuoja rinkos kainą, Python meta `dictionary changed size during iteration`.
Tam yra apkrovos testas (`test_shared_state_survives_concurrent_sources`), patikrintas
spyną laikinai išjungus — be jos jis iš tiesų lūžta.

Vieno šaltinio gedimas kito nenutraukia: klaida patenka į log'ą, o likęs šaltinis
baigia darbą.

Išjungus (`PARALLEL_SOURCES: false`) šaltiniai eina paeiliui, laikas dalijamas po lygiai,
o eiliškumas kas paleidimą keičiasi — kitaip antrasis prie ilgo Vinted patikrinimo
niekada neprieitų.

### Skelbiu.lt ypatumai

- Naudojama kategorija **480 (Apple)** — todėl į sąrašą nepatenka ekranų keitimo
  paslaugos, dėklai ir dalys; jos guli atskirose kategorijose.
- `orderBy=1` — naujausi viršuje. ID didėja laikui bėgant, tad kai visas puslapis
  jau matytas, toliau nebeeinama.
- Skelbiu dažnai rašo be žodžio „iPhone" (`13 pro max 256gb`), todėl antraštė
  papildoma — kitaip modelio neatpažintume. Kategorijoje yra tik Apple telefonai,
  tad tai saugu.
- Būklė ten tik „Nauja" / „Naudota". „Naudota" nieko nesako, tad paliekama nežinoma
  ir sprendžiama pagal aprašymą (defektai, baterija).
- Įvertinimų ir atsiliepimų nėra. Pardavėjas vertinamas pagal registracijos datą,
  aktyvių skelbimų kiekį ir patvirtintą tapatybę.
- „Parduota" žymės nėra — dingęs skelbimas laikomas parduotu (`GONE_AS_SOLD`).
  Todėl skelbimo adresas saugomas istorijoje: be jo vėliau jo nerastume.

## Kaip nustatoma rinkos kaina

Eilės tvarka, pirmas tinkamas laimi:

1. **Rankinė kaina** – `config.json` → `MARKET_PRICES` arba `/kaina 13 180`
2. **Tikros pardavimo kainos** – kai to modelio parduota bent `MIN_SOLD_SAMPLES`
3. **Įvertinimas pagal skelbimus** – prašomų kainų percentilis × `ASKING_SALE_FACTOR` × pataisymas
4. **Apytikslė kaina** – retiems modeliams, kai duomenų beveik nėra

Log'e matomos visos keturios; naudojama ta, kuri pažymėta `-> naudojama`.

### Savikalibracija

Vinted prašomos kainos smarkiai didesnės už realias, todėl 3 punktas savaime pervertina.
Kad to nereikėtų taisyti ranka, kiekvienam naujam telefonui išsaugomas tuometinis mūsų
vertinimas (`q`) ir tuomet galiojęs daugiklis (`qf`). Kai tas telefonas parduodamas,
kodas žino, kiek spėjo ir kiek realiai gauta.

`/tikslumas` parodo paklaidą pagal modelius, o pataisymas automatiškai artėja prie
teisingo dydžio – ne daugiau kaip `CALIBRATION_MAX_STEP` per paleidimą.

Skaičiuojama nuo **žalios** skelbimų kainos, o ne nuo jau pataisytos. Priešingu atveju
tas pats pardavimas pataisymą nustumtų kelis kartus iš eilės ir vertinimas persisvertų
į kitą pusę (taip ir buvo pirmame variante – pagavo simuliacija).

Pirmenybė teikiama **patvirtintiems** pardavimams (skelbimo puslapis sako „parduota“).
Tik dingę skelbimai naudojami tada, kai patvirtintų dar per mažai – jie nepatikimi,
nes skelbimas gali būti tiesiog ištrintas.

Išjungti: `/kalibruoti ne` arba `"AUTO_CALIBRATE": false`.

## Telegram komandos

`/pagalba`, `/kaina 13 180`, `/kaina 13 Pro 256 250`, `/kaina 13 trinti`, `/kainos`,
`/nuolaida 20`, `/baterija 80`, `/garsas 30`, `/tvarkingi taip|ne`, `/tikslumas`,
`/kalibruoti taip|ne`, `/statistika`, `/pauze`, `/testi`, `/nustatymai`

### Mygtukai po kortele (kiekvienam vartotojui atskirai)

🔔 **Sekti šį modelį** – tie skelbimai papildomai siunčiami tam žmogui asmeniškai.

Kad asmeninės žinutės veiktų, žmogus botui privačiai turi parašyti `/start`.
Privačiame pokalbyje veikia `/start`, `/mano`, `/stop`.

Nustatymų komandos veikia **tik administratoriui** ir **tik privačiame pokalbyje** su botu.
Savo ID sužinosi parašęs botui `/start`; įrašyk jį į `config.json` → `"ADMIN_IDS": [123456789]`.
Grupėje kitų žmonių komandos tyliai ignoruojamos.

Komandos įvykdomos kito paleidimo metu. Botas turi būti grupėje, o jei naudotas webhook – jį reikia išjungti.
