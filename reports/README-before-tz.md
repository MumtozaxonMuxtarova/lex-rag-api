# Lex RAG API

## Yakuniy tekshiruv (2026-11-06)

100 savol `evaluation/questions.json` da. Har bir javobli savolning etalon manbasi
va aynan korpusdan olingan iqtibosi `expected_sources` da. Javobsiz 10 savolda
expected_doc_id/expected_article=null. Savollar manbadan tuzilgan rivojlantirish
to'plami; mustaqil yoki yashirin benchmark emas. 10 tarixiy/bekor qilingan norma
testi o'rniga mavjud snapshot tahririni tekshiruvchi savollar qo'yilgan: tarixiy
korpus yo'q. Bu TZning tarixiy qamrovi to'liq bajarilgan degani emas.

| Ko'rsatkich | Oldin | Keyin |
|---|---:|---:|
| Hit@1 (90 javobli savol) | 84.44% | 93.33% |
| Hit@5 | 86.67% | 96.67% |
| MRR@5 | 0.8556 | 0.9472 |
| Kutilgan modda top-5 da yo'q | 12 | 3 |
| Birinchi modda etalonga mos emas | 14 | 6 |
| Javobli savolda bo'sh natija | 0 | 0 |
| Qamrovdan tashqari savol to'g'ri rad etildi | 9/10 | 10/10 |
| Texnik savol xatosi | 0 | 0 |

MRR faqat qaytgan top-5 bo'yicha (MRR@5); to'liq indeks bo'yicha MRR emas.
Ko'p manbali savolda Hit/MRR kamida bitta to'g'ri hujjat+moddani talab qiladi.
Barcha kerakli manbalar top-5 da: oldin 8/15, keyin 13/15. Javob generatsiyasi
avvalgidek faqat birinchi modda matnini qaytaradi; ko'p manbani birlashtirmaydi.
Qolgan xatolar: q007/q008/q044 noto'g'ri birinchi o'rin;
q012/q024/q060 uchun etalon top-5 da ham yo'q. Etalonlar cheklangan va ayrim
savollarda boshqa moddalar ham tegishli bo'lishi mumkin. Natija yuridik ekspert
tomonidan mustaqil to'g'rilik bahosi emas.

Zarur tuzatishlar: umumiy so'roq so'zlari va ISO snapshot sanasini qidiruv
kalitlaridan chiqarish; aniq kodeks+modda so'rovida boshqa kodeksning xuddi shu
raqamli moddasini aralashtirmaslik. Arxitektura va LLM o'zgarmadi.

33 avtomatik test o'tdi (1 ta kutubxona deprecation ogohlantirishi).
10 batchning har biri 10 savoldan iborat; etalonlar APIga yuborilmaydi.
Oldin/keyin bir xil dataset SHA-256 bilan solishtirilgan.
Xom API javoblari `evaluation/before/b01.json` ... `b10.json` va `after/` da.
Hisobotlar: `evaluation/comparison.json`, `FINAL_REPORT.md`.
Oldingi qidiruv kodi `evaluation/before/retrieval.py` da saqlangan.

Qayta baholash va testlar (loyiha papkasida, kutubxonalar o'rnatilgach):

```powershell
python -m app.evaluate --label verification
python -m pytest -q
```

`start.ps1` yaratgan mahalliy kutubxonalar bilan ishlasangiz avval:
`$env:PYTHONPATH = "$PWD\.runtime\packages;$PWD"`.
Backend va frontend bitta buyruq bilan: `.\start.ps1`.
Qo'lda: `$env:RAG_API_KEY='kamida-16-belgili-kalit'; python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000`.
Sayt `http://127.0.0.1:8000/`, API hujjati `/docs`.

lex.uz RAG test spetsifikatsiyasiga asoslangan loyiha: mavjud qidiruvga ulangan web interfeys.

## Eng oson ishga tushirish

ZIPni alohida `lex-rag-api` papkasiga oching. Shu papkada PowerShell ochib:

```powershell
.\start.ps1
```

Skript Pythonni tekshiradi, birinchi safar kutubxonalarni `.runtime/` ichiga
o'rnatadi, `.env` ichiga tasodifiy mahalliy API kalitini yozadi va backend tayyor
bo'lgach brauzerni ochadi. Sayt: **http://127.0.0.1:8000**.
Saytda **APIga ulanish** tugmasini bosib, `.env` faylidagi `RAG_API_KEY=` dan
keyingi qiymatni kiriting. Keyin til/sanani tanlab savol bering.
Kalit URLga, brauzer doimiy xotirasiga yoki lex.uz saytiga yuborilmaydi.

Birinchi o'rnatishda internet kerak. Keyingi ishga tushirishlarda tayyor baza bilan
qidiruv internetga murojaat qilmaydi; faqat rasmiy manba havolasini ochish internet talab qiladi.
`start.ps1 -NoBrowser -Port 8001` brauzer ochmasdan boshqa portda ishga tushiradi.
Python avtomatik topilmasa `-PythonPath 'C:\...\python.exe'` parametrini bering.
Serverni to'xtatish: **Ctrl+C**. Kodda alohida frontend build yoki Node.js serveri kerak emas.

### D: papkaga joylash

Arxivni `D:\pdp univer 4 kurs\1 semester\AI\06.11.2026` ichiga ochishingiz mumkin.
Loyihani boshqa joyda ochgan bo'lsangiz, loyiha papkasida `.\copy-to-d.ps1` ni
ishga tushiring: u shu D: manzilda `lex-rag-api` papkasini yaratib, kod, tayyor
korpus, asl HTML, test va hisobotlarni ko'chiradi. Mavjud `lex-rag-api` papkasi
ustiga yozmaydi. Mahalliy kalit, vaqtinchalik baza va kutubxona keshi ko'chirilmaydi.
Keyin D: dagi loyiha papkasida `.\start.ps1` ni ishga tushiring.

## Hozirgi holat

Ishlaydi: FastAPI, Bearer autentifikatsiya, 1-10 savollik batch, 400 validatsiya,
SQLite saqlash, takroriy so'rovlar uchun idempotentlik va 409, 429/Retry-After,
110 soniyadan so'ng 202 va natijani GET orqali olish, savol xatolarini ajratish,
meta/health, BM25 qidiruvi, sarlavha bo'yicha deterministik reranking va aynan manbadan olingan javob.
Natijalar avtomatik o'chirilmaydi; SQLite faylini doimiy diskda saqlang.

**Haqiqiy lex.uz korpusi ulangan:** Mehnat kodeksi va Fuqarolik kodeksining birinchi
qismi, har biri o'zbek lotin, o'zbek kirill va rus tillarida. 2026-11-06 snapshotida
6 ta til varianti va 2 937 ta modda bo'lagi mavjud. Bu butun lex.uz bazasi emas.
Manbalar ro'yxati `sources/lex.json`, sanalar va hashlar `data/lex.manifest.json` da.

Bu hali yakuniy semantik RAG emas: embedding va LLM ulanmagan. BM25 + sarlavha
mosligi ishlaydi; javob birinchi topilgan moddaning asl xatboshilaridan iborat.
Til orasida tarjima qilmaydi. Avtomatik til aniqlash sodda; `items[].language` ni bering.
TZdagi mustaqil 100 savollik sifat metrikalari hali o'lchanmagan.

## Ishga tushirish (PowerShell, Python 3.11+)

Quyida qo'lda ishga tushirish varianti. Bunda `.env` avtomatik o'qilmaydi;
yuqoridagi `start.ps1` esa o'zi yaratgan `.env` dan faqat API kalitini o'qiydi.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
# GitHub'dan olganda yoki bazani yangilaganda:
python -m app.ingest
$env:RAG_API_KEY = 'uzun-va-tasodifiy-test-kalitini-kiriting'
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Interaktiv API: http://127.0.0.1:8000/docs . Authorize tugmasiga API kalitini kiriting.
`.env.example` namuna. Qo'lda ishga tushirganda muhit o'zgaruvchilarini o'rnating.
Bir jarayonda ishlating (`--workers 1`); ko'p worker hozir qo'llab-quvvatlanmaydi.

ZIP ichida 2026-11-06 bazasi bor; shu baza uchun namuna so'rov sanasi ham shunday.
Yangi snapshot import qilganda `options.as_of_date` ni yangi sanaga o'zgartiring yoki
olib tashlang (default - serverning bugungi sanasi). To'liq qamrab olinmagan sana
`SNAPSHOT_DATE_UNAVAILABLE` qaytaradi; bazani yangilash kerak.

```powershell
$headers = @{Authorization = "Bearer $env:RAG_API_KEY"}
$body = Get-Content -Raw -Encoding utf8 examples/batch.json
Invoke-RestMethod http://127.0.0.1:8000/v1/rag/batch -Method Post -Headers $headers -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body))
Invoke-RestMethod http://127.0.0.1:8000/v1/rag/batch/first-run-b01 -Headers $headers
```

## Korpus formati

```powershell
# Aniq sanadagi tahrirlarni rasmiy sahifadan qayta olish:
python -m app.ingest --snapshot-date 2026-11-06
# Yetti savollik mahalliy tekshiruv va to'liq API javobini saqlash:
python -m app.smoke
```

Importer har hujjatning sana ro'yxatidan snapshotdan kech bo'lmagan eng oxirgi
tahrirni tanlaydi. Sahifa kelajak tahririda ochilsa, `ONDATE` bilan qayta yuklaydi.
Har sahifaning asl HTML nusxasi `data/raw/` da saqlanadi. SHA-256 asl saqlangan
fayl baytlariga mos. Menyu, sharh, indeks va tahrir izohlari modda matniga kiritilmaydi.
Hamma manba tekshiruvdan o'tgandan keyingina yangi korpus nashr qilinadi.
Kutilgan HTML tuzilishi yoki til yozuvi o'zgarsa import xato bilan to'xtaydi.

`data/lex.jsonl` faylida har qatorda bitta JSON obyekt. Faqat tekshirilgan lex.uz
matnlarini kiriting. Maydonlar:

| Maydon | Mazmuni |
|---|---|
| chunk_id | Hujjat + modda + qism + tahrir uchun yagona ID |
| doc_id | `lex:` va hujjatning haqiqiy raqami |
| doc_title, doc_type | Nomi va turi |
| url | `https://lex.uz/docs/` va aynan shu raqam |
| article, part | Modda; to'liq modda uchun part=null (huquqiy qism raqami taxmin qilinmaydi) |
| edition_date | Tahrir sanasi, YYYY-MM-DD |
| valid_from, valid_to | Amal qilish oralig'i [boshi, oxiri); oxiri bo'lmasa null |
| snapshot_date | Manba olingan sana |
| doc_status | Manbaning tekshirilgan holati |
| text | Modda/qismning asl matni |
| language | uz-Latn, uz-Cyrl yoki ru |

`as_of_date` shu oraliq bo'yicha filtrlaydi; uning to'g'riligi import qilingan
metadata sifatiga bog'liq. Import faqat tanlangan tahrirdan snapshot sanasigacha
bo'lgan qamrovni tasdiqlaydi; keyingi kunlar yoki eski tahrirlar taxmin qilinmaydi.
Hozir tarixiy holat uchun doc_status qayta hisoblanmaydi. Bekor qilingan hujjat
importi alohida tarixiy ishlov talab qiladi. `edition_date` butun hujjat tahriri sanasi;
har bir moddaning alohida o'zgartirilgan sanasi emas.
Importdan so'ng serverni qayta ishga tushiring. Indeks versiyasi korpus hashidan olinadi.
`return_contexts=false` bo'lsa ham havola berilgan chunk saqlanadi: citation kontekstsiz qolmaydi.

## Tuzilishi va endpointlar

| Fayl/papka | Vazifasi |
|---|---|
| app/main.py | FastAPI, autentifikatsiya, batch, static interfeys |
| app/engine.py, app/retrieval.py | Mavjud BM25 qidiruv va manbadan javob olish |
| app/coverage.py | Haqiqiy korpus sonlari va umumiy sana oralig'i |
| app/ingest.py | lex.uz dan tahrirlarni import qilish |
| app/store.py | SQLite, idempotent natijalar |
| app/models.py | Request validatsiyasi |
| app/web/ | index.html, style.css, app.js; responsive interfeys |
| app/launch.py, start.ps1 | Backend va saytni birga ishga tushirish |
| sources/, data/ | Manba ro'yxati, tayyor korpus va asl HTML |
| tests/, reports/ | Avtomatik testlar va tekshiruv natijalari |

| Endpoint | Vazifasi | Kalit |
|---|---|---|
| GET / | Web interfeys | Yo'q |
| GET /v1/health | Backend/baza tayyorligini tekshirish | Yo'q |
| GET /v1/meta | Model va indeks versiyalari | Bearer |
| GET /v1/coverage | 6 til varianti, sonlar va mavjud sanalar | Bearer |
| POST /v1/rag/batch | 1-10 savol, mavjud qidiruv | Bearer |
| GET /v1/rag/batch/{batch_id} | Saqlangan yoki davom etayotgan natija | Bearer |
| GET /docs | Swagger interaktiv API tavsifi | Ochiladi; API chaqiruvlari kalit bilan |

Frontend o'sha serverdagi `/v1/rag/batch` ga bitta savol yuboradi. Uzoq ishlansa
202 javobidan so'ng mavjud GET endpoint orqali natijani kutadi. 429, noto'g'ri
kalit, aloqa uzilishi, bazada yo'q sana va topilmagan javob holatlari alohida ko'rsatiladi.
Qidiruv natijasida modda, tahrir sanasi, asl iqtibos, topilgan kontekstlar va
o'sha tahrirdagi lex.uz havolasi chiqadi. Matn HTML sifatida bajarilmaydi.
Interfeys birinchi ulanishda sanani bazadagi snapshotga moslaydi;
979 modda o'rni uch tildagi variantlari bilan 2 937 bo'lakni tashkil qiladi.

## Ushbu bosqichdagi o'zgarishlar

- Mavjud qidiruv, rate limit va batch saqlash algoritmi almashtirilmadi.
- `main.py` ga `/`, `/assets` va himoyalangan `/v1/coverage` qo'shildi;
  standart data manzili loyiha papkasiga bog'landi.
- `engine.py` citationiga faqat `edition_label` qo'shildi, masalan `15.10.2026 01`;
  lex.uz ning bir kundagi farqli tahrir belgisini havolada yo'qotmaslik uchun.
- Yangi frontend bitta serverda xizmat qiladi. Kalit faqat sahifa xotirasida turadi.
- Ishga tushirish skripti va qo'shimcha 6 ta web/API testi qo'shildi.
- LLM, embedding, boshqa kodeks yoki yangi huquqiy ma'lumot qo'shilmadi.

## Testlar

```powershell
python -m pytest -q
```

Testlar autentifikatsiya, validatsiya, saqlash, konflikt, parallel retry, async,
rate limit, sana filtri, HTML tozalash, manba hashlarini saqlash, yozuvlarni
normalizatsiya qilish, manba-kontekst mosligi va savol xatosi izolyatsiyasini tekshiradi.
Korpus bo'lsa, haqiqiy ma'lumotlar bilan API integratsiyasi ham tekshiriladi;
korpus bo'lmasa shu ikki test o'tkazib yuboriladi. `reports/smoke.json` yetti savollik
rivojlantirish tekshiruvi; bu mustaqil benchmark yoki TZ sifat kafolati emas.

Web integratsiyasidan keyin **30 ta test o'tdi** (avvalgi 24 + yangi 6).
`reports/web-review.json` da haqiqiy mahalliy HTTP endpoint tekshiruvi saqlangan.
Brauzerda 1440x1000 va 390x844 o'lchamlari, o'zbekcha/ruscha manbali javob,
topilmagan javob hamda noto'g'ri kalit holati tekshirildi. 6 ta asl HTML va korpus
SHA-256 qiymatlari mos. `reports/desktop.png` va `reports/mobile.png` da ekran ko'rinishlari bor.
`start.ps1` mahalliy mos paket keshi bilan ham ishga tushirilib, autentifikatsiya
va 2 937 bo'lakli bazani yuklashi tekshirildi; yangi o'rnatishdagi yuklash internet tezligiga bog'liq.

## Keyingi bosqichlar

1. Yana hujjatlar va ularning tarixiy tahrirlarini qo'shish, huquqiy qism chegaralarini aniqlash.
2. Ko'p tilli embedding, vektor indeks va semantik reranker.
3. Manbaga tayangan LLM, til tanlash, javobsizlik va timeout nazorati.
4. 100 savollik baholash to'plami, batch runner, Hit@5/MRR va sifat hisoboti.
5. Joylashtirish uchun doimiy navbat, umumiy rate limit va ko'p worker qo'llovi.

## GitHub

API kalitlar, SQLite va korpus fayllari `.gitignore` orqali chiqarilgan.
Asl HTML ham Git'ga kiritilmaydi. Korpus importer orqali qayta yaratiladi; ZIPda tayyor baza bor.
GitHub akkaunti va repo nomi foydalanuvchi bilan aniqlangandan keyingina push qilinadi.

## Hujjatlar

- FastAPI: https://fastapi.tiangolo.com/tutorial/
- Pydantic validatorlar: https://pydantic.dev/docs/validation/latest/concepts/validators/
- Mehnat kodeksi: https://lex.uz/docs/-6257288
- Fuqarolik kodeksi (birinchi qism): https://lex.uz/docs/-111189
