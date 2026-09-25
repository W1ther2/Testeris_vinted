# iPhone deal finder

Ieško iPhone 8 … 17 Pro Max, kurie pigesni už rinkos kainą, ir siunčia juos į Telegram.
Šaltiniai įjungiami `config.json` → `"SOURCES": ["vinted", "pirkpard"]` (galimi: `vinted`, `pirkpard`, `skelbiu`).

## Kas nauja v39

**Vinted LT sąrašas nėra lietuviškas.** Išmatuota gyvai 2026-09-25 (`api.vinted.lt`,
paieška „iphone“, 45 telefonai): **PL 31, FI 6, LT 5, LV 2, EE 1** – Lietuvos vos ~11 %.

Dar svarbiau: naujasis katalogo API pardavėjo objekte grąžina **tik** `business`, `id` ir
`login` – nei šalies, nei miesto. Šalis paaiškėdavo tik atidarius skelbimą, t. y. **jau po**
`market.observe()`. Todėl užsienio skelbimas, atmestas ankstesniame etape (pvz. „ne tarp
pigiausių“), iki šalies patikros taip ir nepriedavo ir **likdavo Lietuvos rinkos istorijoje
kaip vietinė kaina**. Kadangi PL kainos sistemiškai žemesnės (jos perskaičiuotos iš PLN),
Lietuvos rinkos kaina buvo nuvertinta, o „pigiausių 15 %“ skaičiuojami lenkų atžvilgiu –
tikri LT dealai atmesti kaip vidutiniai.

- **Šalis nustatoma prieš rinkos statistiką** (`Run.resolve_countries`). Užsienio skelbimas
  iškart gauna `skip_reason` ir į istoriją nebepatenka visai; tai matosi ir `/statistika`
  (`salis (PL): 24`).
- **Pardavėjų šalys įsimenamos** (`state.json` → `sellers`), tad pardavėjas su 20 skelbimų
  kainuoja vieną užklausą, ne dvidešimt. Antrame paleidime jau pusė šalių ateina iš atminties.
- **Užklausų riba** – `SELLER_COUNTRY_LOOKUPS` (40). Gyvai matyta, kad po ~45 užklausų iš
  eilės `www.vinted.lt/api/v2/users/<id>` atsako **HTTP 429**, o `api.vinted.lt` to adreso
  **neturi visai** (visada 404) – anksčiau kiekvienas pardavėjas kainavo dvi užklausas, iš
  kurių antra beviltiška. Dabar: 429 → šiame paleidime nebeklausiama, 404 → antro adreso
  nebandome.
- **Nepatikrinta ≠ lietuviška.** Kol šalis nežinoma, skelbimas rinkos kainoje
  neskaičiuojamas (`state.json` → `"x": "salis?"`), o į jį pačią pretenduojama tik jei tekste
  yra tikrai lietuviškų žodžių (`UNKNOWN_COUNTRY_NEEDS_LT_TEXT`). „iPhone 12 64g“ be nė vieno
  lietuviško žodžio dažniausiai yra lenkų skelbimas, kurio kalbos filtras nepagauna.
- **Neprarandami dėl ribos.** Jei šalies nepavyko nustatyti *tik* dėl užklausų ribos ar 429,
  skelbimas nežymimas matytu ir tikrinamas dar iki `DETAIL_RETRIES` kartų. Likusios
  užklausos atiduodamos jau matytiems, bet dar nepatikrintiems skelbimams – kiekvienas
  patikrintas grąžina į rinkos kainą dar vieną tikrą lietuvišką kainą.
- **Ribotos užklausos eina protingiau:** pirma tikrinamos apvalios kainos. Perskaičiuota PLN
  kaina beveik visada su centais (692,64 €), o tikra lietuviška – apvali (550 €). Iš 31
  lenkiško skelbimo **visi 31** buvo su centais, o iš tikrų LT telefonų – nė vienas.
- **`VINTED_BROWSE_PAGES: 3 → 6`.** Kadangi lietuviškų sąraše tik ~11 %, 3 puslapiai duoda
  vos ~30 vietinių – „pigiausių“ palyginimui (`RANK_RECENT_DAYS`) tokių pat telefonų
  nesusidaro. Puslapiai pigūs, o jau matyti skelbimai pardavėjų užklausų nebereikalauja.

> **Pirmą dieną rinkos kainos bus „apytikslės“.** Sena istorija buvo sudaryta iš mišraus
> sąrašo, o naujoji auga tik iš patvirtintų lietuviškų. Kol susikaups `MIN_SAMPLES` (8) vieno
> modelio kainų, log'e matysi `-> naudojama: … (apytiksl.)` ir `(retas modelis – vertinta
> pagal nuolaidą)`. Per kelias valandas (backfill po ~40 patikrų per paleidimą) tai susitvarko.

## Kas nauja v38

Antroji kodo peržiūra (2026-09). Visi punktai turi testus (`tests/test_limits.py`).

- **Būsena nebegali sugesti nutrūkus paleidimui.** `state.json` ir `seen.json` rašomi į
  laikiną failą ir tik tada pervadinami (`os.replace`) – arba visas, arba nieko. Anksciau
  GitHub'ui nutraukus darbą (laiko limitas, `cancel`) failas likdavo pusiau įrašytas, ir
  kitas paleidimas pradėdavo nuo nulio: dingdavo visa rinkos istorija, kalibracija ir
  sekami pranešimai. Papildomai laikoma `.bak` kopija – jei pagrindinis failas vis tiek
  būtų sugadintas, paimama ji.
- **Būsena nebekaupiama kodo šakoje.** Anksčiau `state.json` (~1 MB) buvo commit'inamas į
  tą pačią šaką kas 10 min. – 144 commit'ai per dieną, kelios šimtos MB per mėnesį, kurių
  iš git istorijos nebeišimsi. Dabar ji gyvena šakoje **`busena`**, kuri kas kartą
  perrašoma (`push --force`): ten visada lieka vienas commit'as. Žr. „Būsenos šaka“.
- **Nepavykęs Telegram siuntimas nebesunaikina dealo.** Jei Telegram neatsako (tinklo
  klaida), skelbimas anksčiau vis tiek būdavo pažymimas matytu ir „pranešu“ – geras
  pasiūlymas dingdavo visam laikui. Dabar žymės nuimamos ir kitas paleidimas bando dar kartą.
- **Pranešimų lavinos apsauga** – `MAX_ALERTS_PER_RUN` (20; 0 – be ribos). Jei būsena kada
  nors pasimestų, visi skelbimai atrodytų nauji ir Telegram gautų dešimtis kortelių iš karto
  (o grupėje leidžiama 20 žinučių per minutę). Likusieji nepažymimi matytais – juos įvertina
  kitas paleidimas.
- **Bot'o token'as nebepatenka į logą.** `requests` klaidos tekste yra visas adresas, o
  jame – token'as (`.../bot123:ABC/sendMessage`). Dabar jis pakeičiamas `***`.
- **Tas pats skelbimas nebetikrinamas dukart.** „Pardavimų patikra“ ir „pranešimų
  rezultatai“ tikrino tą pačią būseną atskirai – Vinted tai dvi užklausos ir dvi pauzės tam
  pačiam puslapiui. Dabar per paleidimą užklausiama kartą, o rezultatų patikros žinia iškart
  patenka ir į rinkos istoriją (savikalibracija pamato pardavimą per minutes, ne po 2 dienų).
- **Sugedusi komanda nebesiciklina.** Klaida vykdant Telegram komandą nutraukdavo visą
  žingsnį, `telegram_offset` nebūdavo įrašytas, ir ta pati komanda būdavo vykdoma kas
  10 min. be galo. Dabar klaida praneša tik apie save, o offset įrašomas visada.
- **`/start` su papildoma eilute** („/start\nlabas“) anksčiau nebuvo atpažįstamas, ir žmogus
  negaudavo asmeninių žinučių, nors ir parašė botui.
- **Pauzė (`/pauze`) nebeleidžia darbo veltui**: patikrinama prieš skelbimo puslapį, tad
  kainų istorija toliau kaupiasi, bet dešimtys puslapių su pauzėmis nebekraunami.

## Kas nauja v37

Pataisymai po kodo peržiūros (2026-09). Visi turi testus (`tests/test_robustness.py`,
`tests/test_market_quality.py`, `RealPhrasesTest` faile `tests/test_phone.py`).

- **Tvarkingi telefonai nebeatmetami dėl žodžių.** „Parduodu iPhone 13 telefoną“ nebelaikoma lotu,
  „reikia pinigų“ – užrakintu kodu, „nebuvo daužtas / taisytas / sulytas“ – defektais,
  „atrištas nuo iCloud“, „iCloud švarus“ – iCloud užraktu, „laikytas tik dėkle“, „čekio kopija“,
  „ne kopija“ – ne telefonu. Tikri defektai gaudomi kaip ir anksčiau.
- **Neatsidaręs skelbimas nebesiunčiamas aklai.** Jei puslapio gauti nepavyksta (403, laiko limitas,
  patikros puslapis), skelbimas nesiunčiamas be aprašymo patikros – bandoma kituose paleidimuose
  (`DETAIL_RETRIES`, numatyta 3).
- **Kiekvieno šaltinio būsena.** Jei Vinted neveikia, o Pirkpard veikia, apie tai dabar pranešama
  (po `FAIL_ALERT_RUNS` paleidimų be skelbimų arba iškart, jei aiškus blokas). Įspėjimas kartojamas
  ne dažniau nei kas `SOURCE_ALERT_HOURS`, o atsigavus ateina „✅ … vėl veikia“.
  Anksčiau, kai neveikė viskas, įspėjimas kartodavosi kas 30 min.
- **Lūžimai.** Būsena išsaugoma visada (`finally`), vieno šaltinio klaida nenutraukia paleidimo ir
  vieno šaltinio režime, papildomų darbų (kalibravimas, pardavimų patikra…) klaida praneša kartą per
  valandą, „SKRIPTAS UZLUZO“ – ne dažniau nei kas valandą. Programa grąžina klaidos kodą (1 – lūžo,
  2 – nėra BOT_TOKEN), tad GitHub parodo raudonai ir atsiunčia laišką.
- **Rinkos duomenys:** laipsniškas atpigimas (300 → 290 → 280) matuojamas nuo kainos, už kurią
  vertinta paskutinį kartą; atmesti skelbimai (užrakinti, sugedę, ne telefonai, užsienio) išimami iš
  „pigiausių“ palyginimo ir rinkos kainos; iš naujo įkeltas skelbimas nebelaikomas pardavimu;
  „parduotų“ kaina pirmiausia skaičiuojama iš patvirtintų pardavimų; kalibruojama kartą per dieną.
- **Pirkpard:** jei būsenos sąrašas gautas ne visas, nerastas skelbimas laikomas „nežinoma“, o ne
  „parduotas“.
- **Telegram:** ilga kortelė trumpinama nepjaunant HTML; 429 (per daug žinučių) – palaukiama ir
  kartojama; sugadintas HTML – siunčiama paprastu tekstu; grupėje ne dažniau nei kas 3 s.
- **Modeliai:** „iPhone 17 Air“ = Air, „iPhone 128GB“ nebe iPhone 12; baterija „89 proc.“ atpažįstama.
- **Rankinė kaina:** pavyzdinė `"13": 180` pašalinta iš `config.json`; jei rankinė kaina
  nuo rinkos skiriasi daugiau nei 25 %, kartą per parą ateina įspėjimas.
- **GitHub Actions:** bibliotekos iš `requirements.txt` (su versijų ribomis ir pip cache), testai
  paleidžiami atskirai įkėlus kodą (`tests.yml`), o ne kas 10 min. kartu su botu.

| Šaltinis | Kaip veikia | Ypatumai |
|---|---|---|
| `vinted` | katalogo API (`api.vinted.lt`) | būklė, pardavėjo įvertinimai, pirkėjo apsaugos mokestis |
| `pirkpard` | vieša JSON API (`/api/v1/products`) | aprašymas ateina su sąrašu, tad visam paleidimui užtenka vienos užklausos |
| `skelbiu` | įprastas puslapis (API nėra) | įvertinimų nėra, atsiskaitoma tiesiogiai, tad mokesčio pelne nėra |

> **Skelbiu šiuo metu išjungtas.** Ne dėl kodo — jis veikia. Skelbiu naudoja Cloudflare,
> kuris iš duomenų centrų IP (tarp jų GitHub Actions) reikalauja išspręsti iššūkį:
> atsakyme matomas `cf-mitigated: challenge`. Iš įprasto namų interneto puslapis
> atsidaro be jokių kliūčių, tad kodą galima paleisti iš savo kompiuterio —
> `config.json` → `"SOURCES": ["vinted", "skelbiu"]`.
>
> Botų apsaugos apėjimas čia nedaromas sąmoningai: tai svetainės savininko pastatyta
> užtvara, o ir techniškai tai būtų nesibaigiančios lenktynės.

## Failai

| Failas | Kas tai |
|---|---|
| `vinted_deal_finder.py` | paleidimo failas |
| `requirements.txt` | bibliotekos (`pip install -r requirements.txt`) |
| `vinted/` | kodas (modulis per temą) |
| `tests/` | automatiniai testai (`python -m unittest discover -s tests -t .`) |
| `config.json` | nustatymai |
| `seen.json`, `state.json` | sukuriami automatiškai, išsaugomi tarp paleidimų |
| `.github/workflows/vinted.yml` | botas kas 10 min. (GitHub Actions) |
| `.github/workflows/tests.yml` | testai, kai įkeli naują kodą |

### Būsenos šaka (`busena`)

GitHub'e `seen.json` ir `state.json` išsaugomi **atskiroje šakoje `busena`**, kuri kas kartą
perrašoma iš naujo (`push --force`), tad joje visada lieka vienas commit'as. Taip kodo
istorija nebeauga: anksčiau būsena buvo commit'inama į kodo šaką kas 10 min., o `state.json`
yra apie 1 MB – per mėnesį susidarydavo keli šimtai MB, kurių iš git istorijos nebeišimsi.

Pirmas paleidimas po atnaujinimo šakos dar neranda ir paima tai, kas įkelta repozitorijoje,
tad niekas nedingsta. Po jo:

1. patikrink, ar Actions log'e rašo `Busena issaugota sakoje 'busena'`;
2. tada seni `seen.json` / `state.json` kodo šakoje nebenaudojami – juos gali ištrinti
   (bet **tik po** 1 punkto: kol šakos nėra, jie yra vienintelė būsena).

Šakos turinį pamatysi GitHub'e pasirinkęs šaką `busena`. Norint pradėti nuo nulio –
tą šaką ištrink. Grįžti prie senos tvarkos: pašalink `vinted.yml` žingsnius
„Atsiusti busena“ / „Issaugoti busena“ ir grąžink commit'inimą į kodo šaką.

## Kodo struktūra

| Modulis | Atsakingas už |
|---|---|
| `config.py` | nustatymai, Telegram komandų pakeitimai |
| `listing.py` | bendra skelbimo forma (`Listing`, `Detail`) – nepriklauso nuo šaltinio |
| `sources/` | šaltiniai: `base.py` (sąsaja), `vinted_source.py`, `pirkpard.py`, `skelbiu.py` |
| `client.py` | Vinted API: sesija, katalogas, skelbimo puslapis, pardavėjas |
| `parsing.py` | kaina, būklė, pardavėjo duomenys, ar skelbimas parduotas |
| `language.py` | kalbos atpažinimas |
| `phone.py` | modelis, priedai, defektai, talpa, baterija, vertė, pelnas |
| `risk.py` | apgavysčių požymiai |
| `market.py` | rinkos kainos, pardavimai, kainų sumažėjimai |
| `tracker.py` | pranešimų rezultatai: ar nupirkta ir per kiek, savaitės ataskaita |
| `state.py` | `seen.json`, `state.json` (saugus įrašymas), pardavėjų šalių atmintis |
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
baigia darbą. Taip yra ir paeiliui, ir vieno šaltinio režime (iki v37 – tik lygiagrečiai).

Lygiagrečiai vyksta **abi** dalys — ir skelbimų paieška, ir pardavimų patikra.
Pastaroji svarbi todėl, kad Vinted kiekvienam senam skelbimui atidaro atskirą puslapį,
o Pirkpard visų būseną gauna viena užklausa; be lygiagretumo Pirkpard be reikalo
lauktų, kol Vinted apeis savo sąrašą.

Kad tai nebūtų tik teorija, `tests/test_parallel.py` matuoja tikrą sieninio laikrodžio
laiką su realiomis (trumpomis) pauzėmis ir tikrina, kad lygiagretus paleidimas būtų
pastebimai greitesnis, o šaltiniai suktųsi skirtingose gijose.

Išjungus (`PARALLEL_SOURCES: false`) šaltiniai eina paeiliui, laikas dalijamas po lygiai,
o eiliškumas kas paleidimą keičiasi — kitaip antrasis prie ilgo Vinted patikrinimo
niekada neprieitų.

### Vinted ypatumai

- **Raktažodžiai nenaudojami po vieną modelį** (`VINTED_BROWSE_ALL: true`). Patikrinta
  gyvai su `api.vinted.lt`: viena paieška `search_text=iphone` grąžina visus modelius
  viename sąraše — nuo iPhone 6 plus iki 15 Pro. 34 atskiros paieškos duoda tą patį,
  tik daro 69 užklausas vietoj 6 ir trunka 4 min vietoj 20 sekundžių.
- `order=newest_first` veikia, bet tarp rezultatų įterpiami reklamuojami skelbimai,
  todėl sąrašas nėra griežtai surikiuotas (gyvai: 53 mažėjančios poros iš 95). Dėl to
  log'e rašo `rikiuota nuo naujausiu: NE` ir ankstyvas stabdymas neįjungiamas — tai
  teisinga, nes sustoję per anksti praleistume naujus skelbimus. Su viena paieška tai
  nebeskauda: 5 puslapiai = 480 naujausių skelbimų, o tai kelios dienos Vinted apyvartos.
- **Giliau nei 10 puslapių Vinted neleidžia** — 11-as grąžina `HTTP 400 INVALID_REQUEST`
  (matyta gyvai). Todėl `VINTED_MAX_PAGES: 10`, o 400 po pirmo puslapio laikomas sąrašo
  pabaiga, ne klaida.
- Atsakyme yra `total_item_price` — tiksli suma su pirkėjo apsaugos mokesčiu.
  Ji naudojama pelnui skaičiuoti vietoj `BUYER_FEE_*` spėjimo (jis lieka atsargai).
- API nebeturi `catalog_id`, `brand_id` ir įkėlimo laiko, todėl kategorijos filtras
  ir „Įkelta prieš X" eilutė Vinted skelbimams neveikia. Būklė imama iš
  `item_box.second_line`.
- **Pardavėjo šalies kataloge nėra** (`user` = tik `business`, `id`, `login`), o sąraše
  Lietuvos skelbimų tik ~11 %. Šalis imama iš `/api/v2/users/<id>` dar prieš rinkos
  statistiką – žr. „Kas nauja v39“ ir `Run.resolve_countries`.

### Pirkpard.lt ypatumai

- Naudojama ta pati vieša JSON API, kuria remiasi ir pati svetainė; prisijungimo nereikia.
- **Aprašymas ateina kartu su sąrašu**, tad atskiro skelbimo puslapio traukti nereikia —
  visas paleidimas telpa į vieną užklausą, o `DETAIL_SLEEP_SECONDS` pauzė praleidžiama.
- API tiesiogiai sako, kas parduota (`sold_out`, `marked_sold_at`). To nesako nei Vinted,
  nei Skelbiu, tad tai patikimiausi duomenys vertinimo tikslumui matuoti.
- Pardavimų patikra peržiūri `PIRKPARD_STATUS_PAGES` puslapių. Jei sąrašas gautas ne visas
  (puslapis nepavyko arba jų daugiau), sąraše nerastas skelbimas laikomas „nežinoma“.
- Aukcionai praleidžiami: ten kaina reiškia dabartinį pasiūlymą, ne pardavimo kainą
  (`PIRKPARD_SKIP_AUCTIONS`). Taip pat praleidžiamos dalys, rezervuoti ir paslaugų skelbimai.
- Pardavėjo el. paštas, telefonas, vardas ir nuotrauka API atsakyme **yra**, bet jų
  neimame ir nesaugome — deal'ui įvertinti jie nereikalingi.
- Be atsiliepimų įvertinimas API'je yra `"0.00"`. Tai nežinia, o ne blogas pardavėjas,
  tad tokiu atveju įvertinimo išvis nenaudojame.
- Apimtis nedidelė: apie 65 aktyvūs iPhone skelbimai, 1–3 nauji per dieną. Bet kaina —
  viena užklausa per paleidimą, o konkurencija ten mažesnė nei Vinted.

### Skelbiu.lt ypatumai

- Naudojama kategorija **480 (Apple)** — todėl į sąrašą nepatenka ekranų keitimo
  paslaugos, dėklai ir dalys; jos guli atskirose kategorijose.
- **Raktažodžiai nenaudojami** (`SKELBIU_BROWSE_ALL: true`). Ta kategorija jau *yra*
  „Apple telefonai", tad vienas sąrašas grąžina visus naujausius iPhone skelbimus —
  34 atskiros paieškos duotų tą patį, tik 34 kartus lėčiau. Be to jos praleistų
  skelbimus, kurių pavadinimas nesutampa su raktažodžiu („Parduodu telefona 128gb").
  Vienas puslapis (24 skelbimai) apima apie 11 valandų, tad paleidžiant kas 15 min.
  užtenka pirmo puslapio. `false` grąžina paiešką pagal `SEARCH_QUERIES`.
- `orderBy=1` — naujausi viršuje. ID didėja laikui bėgant, tad kai visas puslapis
  jau matytas, toliau nebeeinama.
- Skelbiu dažnai rašo be žodžio „iPhone" (`13 pro max 256gb`), todėl antraštė
  papildoma — kitaip modelio neatpažintume. Kategorijoje yra tik Apple telefonai,
  tad tai saugu.
- Būklė ten tik „Nauja" / „Naudota". „Naudota" nieko nesako, tad paliekama nežinoma
  ir sprendžiama pagal aprašymą (defektai, baterija).
- Įvertinimų ir atsiliepimų nėra. Pardavėjas vertinamas pagal registracijos datą,
  aktyvių skelbimų kiekį ir patvirtintą tapatybę.
- „Parduota" žymės nėra — dingęs skelbimas laikomas parduotu (`GONE_AS_SOLD`), nebent tas pats
  pardavėjas tuo metu turi naujesnį tokį pat skelbimą (tada tai pakartotinis įkėlimas).
  Todėl skelbimo adresas saugomas istorijoje: be jo vėliau jo nerastume.

## Kaip sprendžiama, ar skelbimas pigus

**Numatytasis būdas — „pigiausi dabar"** (`DEAL_MODE: "rank"`). Skelbimas siunčiamas,
jei jis tarp `RANK_TOP_PCT` (15 %) pigiausių **šiuo metu parduodamų** tokių pat telefonų —
to paties modelio ir, kai jų pakanka, tos pačios talpos.

Kodėl taip: tam nereikia žinoti rinkos kainos. Jei mediana išpūsta 20 %, senasis
kriterijus („10 % pigiau nei vertė") pradeda siųsti telefonus, kurie realiai nėra pigūs.
Pigiausi 15 % dabartinių skelbimų lieka pigiausiais nepriklausomai nuo to, ar mūsų
vertinimas teisingas. Tai patikrina testas `test_rank_ignores_inflated_manual_price`:
su dirbtinai išpūsta 400 € kaina nuolaidos būdas 300 € telefoną laiko dealu, šis — ne.

Kodėl skelbimas atėjo, kortelėje rašoma įjungus `"SHOW_RANK": true`: *„2-as pigiausias iš 23
dabar parduodamų tokių pat (128 GB), 140–280 €"*. Numatytai išjungta, kad kortelė būtų
trumpesnė – atrankai vieta naudojama visada, o log'e ji matoma ir taip.
Su garsu siunčiamas tik pats pigiausias.

„Dabar parduodami" reiškia matytus kataloge per paskutines `RANK_RECENT_DAYS` (2) dienas.
Pirmoje versijoje čia buvo 30 dienų, ir į palyginimą patekdavo jau seniai parduoti
telefonai — gyvai log'as rodė „3-as pigiausias iš 231". Pigūs telefonai parduodami
greičiausiai, tad seni pigūs įrašai nustumdavo tikrus dealus į vidurį ir jie būdavo
atmetami. Tam yra testas `test_same_data_with_old_window_would_bury_the_deal`.

Užsienio skelbimai (Vinted rodo ir Lenkijos: „Sprzedam, stan idealny") atpažįstami
dviem būdais, abu — prieš atidarant skelbimo puslapį: iš pavadinimo kalbos ir iš pardavėjo
šalies (`/api/v2/users/<id>`). Jie atmetami ir **neįtraukiami į rinkos kainas bei
palyginimą**, nes kita šalis — kita rinka. Tai ne smulkmena: sąraše jų ~89 % (žr. „Kas nauja v39“).

Kokybės filtrai (defektai, baterija, būklė, kalba, šalis) lieka — kitaip pigiausi
visada būtų sugedę telefonai. Ilgai kabantys skelbimai (`ASKING_MAX_AGE_DAYS`) į
palyginimą neįtraukiami: jie per brangūs, ir su jais lyginant viskas atrodytų pigu.

Kai palyginti per mažai (mažiau nei `RANK_MIN_PEERS` = 8 aktyvių skelbimų — pvz.
16e, 14 Plus, Air), naudojamas senasis nuolaidos būdas. Log'e tai matosi kaip
`(retas modelis – vertinta pagal nuolaidą)`.

Apytiksliai: siunčiamas kas 7-as naujas tvarkingas skelbimas (15 %). Mažiau
pranešimų — `/pigiausi 10`, daugiau — `/pigiausi 25`. Grįžti prie seno būdo —
`/rezimas nuolaida`.

### Papildomi filtrai (v36)

- **Minimalus pelnas** – `MIN_PROFIT_EUR` (15 €): nesiunčiama, jei perpardavus uždirbtum mažiau.
  Komanda `/minpelnas 10` (0 – netikrinti).
- **Įtartinai pigu** – palyginama su *kitu* pigiausiu tokiu pat telefonu. Pigiau nei 60 % jo kainos –
  atmetama (dažniausiai užrakintas, be dalies ar apgavystė); 60–75 % – siunčiama su ⚠️ įspėjimu.
  Nustatymai `SUSPICIOUS_REJECT_RATIO`, `SUSPICIOUS_WARN_RATIO`.
- **Priedai bet kurioje pavadinimo vietoje** – „iPhone 17 Pro case“, „MagSafe dėklas“ atpažįstami kaip
  priedai, o „iPhone 13 + dėklas“, „su dėkliuku“, „dėklas dovanų“ – kaip telefonai.

## Kaip nustatoma rinkos kaina

Eilės tvarka, pirmas tinkamas laimi:

1. **Rankinė kaina** – `config.json` → `MARKET_PRICES` arba `/kaina 13 180`
2. **Tikros pardavimo kainos** – kai to modelio parduota bent `MIN_SOLD_SAMPLES`
   (pirmiausia tik patvirtinti pardavimai; dingę skelbimai – tik kai patvirtintų per mažai)
3. **Įvertinimas pagal skelbimus** – prašomų kainų percentilis × `ASKING_SALE_FACTOR` × pataisymas
4. **Apytikslė kaina** – retiems modeliams, kai duomenų beveik nėra

Log'e matomos visos keturios; naudojama ta, kuri pažymėta `-> naudojama`.

### Savikalibracija

Vinted prašomos kainos smarkiai didesnės už realias, todėl 3 punktas savaime pervertina.
Kad to nereikėtų taisyti ranka, kiekvienam naujam telefonui išsaugomas tuometinis mūsų
vertinimas (`q`) ir tuomet galiojęs daugiklis (`qf`). Kai tas telefonas parduodamas,
kodas žino, kiek spėjo ir kiek realiai gauta.

`/tikslumas` parodo paklaidą pagal modelius, o pataisymas automatiškai artėja prie
teisingo dydžio – ne daugiau kaip `CALIBRATION_MAX_STEP` per dieną (iki v37 – per paleidimą,
t. y. iki 144 žingsnių per parą).

Skaičiuojama nuo **žalios** skelbimų kainos, o ne nuo jau pataisytos. Priešingu atveju
tas pats pardavimas pataisymą nustumtų kelis kartus iš eilės ir vertinimas persisvertų
į kitą pusę (taip ir buvo pirmame variante – pagavo simuliacija).

Pirmenybė teikiama **patvirtintiems** pardavimams (skelbimo puslapis sako „parduota“).
Tik dingę skelbimai naudojami tada, kai patvirtintų dar per mažai – jie nepatikimi,
nes skelbimas gali būti tiesiog ištrintas.

Išjungti: `/kalibruoti ne` arba `"AUTO_CALIBRATE": false`.

## Pranešimų rezultatai (ar nupirkta ir per kiek)

Kiekvienas išsiųstas skelbimas sekamas 7 dienas: pirmas 48 val. tikrinama kas paleidimą
(~kas 10 min.), vėliau kas 6 val. Rezultatas – **parduotas**, **rezervuotas** (kažkas jau perka),
**ištrintas** arba **neparduotas per 7 d.** Nupirktais laikomi parduoti ir rezervuoti.

- Kas 7 dienas botas pats atsiunčia ataskaitą: kiek pranešta, kiek nupirkta, per kiek laiko
  (per 1 val. / 6 val. / parą, mediana), galimas pelnas iš nupirktų, greičiausiai nupirkti.
- `/rezultatai` – ataskaita bet kada (`/rezultatai 30` – per 30 dienų).
- Duomenys laikomi `state.json` (raktas `tracked`) 90 dienų.
- Nustatymai: `TRACK_RESULTS`, `TRACK_DAYS`, `REPORT_EVERY_DAYS` (0 – ataskaitos nesiųsti).

## Telegram komandos

`/pagalba`, `/kaina 13 180`, `/kaina 13 Pro 256 250`, `/kaina 13 trinti`, `/kainos`,
`/nuolaida 20`, `/baterija 80`, `/garsas 30`, `/tvarkingi taip|ne`, `/tikslumas`,
`/kalibruoti taip|ne`, `/statistika`, `/pauze`, `/testi`, `/nustatymai`

### Mygtukai po kortele (kiekvienam vartotojui atskirai)

🔔 **Sekti šį modelį** – tie skelbimai papildomai siunčiami tam žmogui asmeniškai.

Kad asmeninės žinutės veiktų, žmogus botui privačiai turi parašyti `/start`.
Privačiame pokalbyje veikia `/start`, `/mano`, `/stop`.

Nustatymų komandos veikia **tik administratoriui** – privačiame pokalbyje su botu ir grupėje.
Savo ID sužinosi parašęs botui `/start`; įrašyk jį į `config.json` → `"ADMIN_IDS": [123456789]`.
Grupėje kitų žmonių komandos tyliai ignoruojamos.

Komandos įvykdomos kito paleidimo metu. Jei `ADMIN_IDS` dar tuščias, botas į pirmą komandą grupėje atsakys, kokį ID įrašyti. Botas turi būti grupėje, o jei naudotas webhook – jį reikia išjungti.
