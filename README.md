# Lex RAG API

lex.uz test spetsifikatsiyasiga mos REST API va mahalliy web interfeys. Savollar
o‘zbek lotin, kirill va rus tilida qabul qilinadi. Javoblar rasmiy matnlardan aynan
olinadi va modda/tahrir havolalari bilan beriladi. Pipeline: BM25, sarlavha bo‘yicha
reranking, og‘zaki so‘rovlarni aniqlashtirish, ko‘p mavzuli qidiruv va iqtibosli javob.
LLM va embedding ishlatilmaydi; bu nomlar `/v1/meta` da `null`. TZ muayyan modelni
majburiy belgilamaydi. Manbadan tashqari bilim qo‘shilmaydi.

## Ishga tushirish

Loyiha papkasida PowerShell orqali:

```powershell
.\start.ps1
```

Sayt: **http://127.0.0.1:8000/**. API: **http://127.0.0.1:8000/v1**.
Swagger: **http://127.0.0.1:8000/docs**.
Saytdagi «APIga ulanish» oynasiga `.env` ichidagi `RAG_API_KEY` qiymatini kiriting.
Kalitni boshqalarga yubormang. Tekshiruvlar alohida vaqtinchalik kalit ishlatadi.
Kalit brauzerning doimiy xotirasida saqlanmaydi.

Python 3.11+ kerak. Skript birinchi ishga tushirishda kutubxonalarni `.runtime` ga
o‘rnatadi va zarur bo‘lsa yangi kalit yaratadi. Serverni to‘xtatish: **Ctrl+C**.
Parametrlar: `-NoBrowser`, `-Port 8001`, `-PythonPath 'C:\...\python.exe'`.
Tayyor korpus bilan qidiruv internet talab qilmaydi.

Qo‘lda o‘rnatish: `python -m pip install -r requirements.txt`.
GitHub nusxasidagi tayyor korpusni avval oching:
`python -m zipfile -e data/corpus.zip data`.
`start.ps1` buni avtomatik bajaradi. Arxiv korpus, manifest va asl HTML manbalarni saqlaydi.
Keyin `RAG_API_KEY` ni muhit o‘zgaruvchisi qilib belgilang va:

```powershell
python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Qo‘lda ishga tushirganda `.env` avtomatik o‘qilmaydi. Qo‘llanadigan o‘zgaruvchilar:
`RAG_API_KEY`, `RAG_DB`, `RAG_CORPUS`. Bitta worker ishlating.

## Korpus va sanalar

- Mehnat kodeksi va Fuqarolik kodeksining birinchi qismi; butun lex.uz bazasi emas.
- Har biri lotin, kirill va rus tilida: 6 ta til varianti.
- 63 ta rasmiy til/tahrir nusxasi, 29 727 ta modda bo‘lagi.
- Snapshot: **2026-11-06**. Tahrirlar 2025-yil boshidan snapshotgacha ketma-ket import qilingan.
- Haqiqiy uzluksiz sana qamrovi `/v1/coverage` da. Sana qamrovi hujjatlar kesishmasidan olinadi.
- `as_of_date` bo‘yicha amal qiladigan bitta tahrir tanlanadi. Qamrab olinmagan sana
  `SNAPSHOT_DATE_UNAVAILABLE` qaytaradi; boshqa davrdagi matn bilan almashtirilmaydi.
- `answer_language` o‘zgartirilsa, topilgan moddaning o‘sha sanadagi rasmiy til
  varianti olinadi. Tasdiqlangan nusxa bo‘lmasa `TRANSLATION_UNAVAILABLE` qaytadi.
- Chunk butun modda bo‘lsa `part=null`: xatboshi raqami huquqiy qism deb taxmin qilinmaydi.

Manbalar: `sources/lex.json`; korpus: `data/lex.jsonl`; SHA-256 va nusxalar ro‘yxati:
`data/lex.manifest.json`; asl HTML: `data/raw/`. Hujjat IDlari lex.uz raqamlariga
bog‘langan. Ruscha rasmiy nusxaning IDsi lotin nusxasidan farq qilishi mumkin.

Yangilash yoki tarixiy bazani qayta qurish:

```powershell
python -m app.ingest --snapshot-date 2026-11-06 --history-since 2025-01-01
python -m app.verify_corpus
```

Importer barcha nusxalar tekshirilmaguncha korpusni almashtirmaydi. Oldingi HTML
nusxalaridan foydalanadi, topilmaganini rasmiy saytdan yuklaydi. Baza yangilangach
serverni qayta ishga tushiring. Avtomatik kundalik yangilash o‘rnatilmagan.
Bekor qilingan butun hujjat importi tekshiruv xatosi bilan to‘xtaydi; u amaldagi
norma sifatida belgilab yuborilmaydi. Testlarda haqiqatan o‘zgargan normalar bor.

## API shartnomasi

| Endpoint | Vazifa | Himoya |
|---|---|---|
| `GET /v1/health` | Servis va indeks tayyorligi | Ochiq |
| `GET /v1/meta` | Pipeline, qidiruv, indeks, kod va snapshot versiyalari | Bearer |
| `GET /v1/coverage` | Manbalar va tasdiqlangan sana oraliqlari | Bearer |
| `POST /v1/rag/batch` | 1–10 savol | Bearer |
| `GET /v1/rag/batch/{batch_id}` | Saqlangan yoki davom etayotgan batch | Bearer |

Namuna: `examples/batch.json`. `items` 1–10 ta, savol 1–2000 belgi; takroriy savol
IDsi, bo‘sh savol, noto‘g‘ri til va boshqa validatsiya xatolari `400` qaytaradi.
Takroriy `batch_id` va bir xil mazmun oldingi natijani qaytaradi; mazmun o‘zgarsa
`409`. Standart limit 1 yangi batch/soniya; oshsa `429` va `Retry-After`.

Har bir savol mustaqil qayta ishlanadi; xato qolgan savollarni to‘xtatmaydi.
Javobdagi `[1]`, `[2]` belgilar `citations[].ref` ga mos keladi; barcha iqtiboslar
`contexts` ichidagi haqiqiy matnlardan olinadi. `return_contexts=false` bo‘lganda
ham iqtibos berilgan kontekstlar saqlanadi. `top_k` qaytariladigan kontekstlarning
yuqori chegarasi. Bir nechta mavzuni `;` bilan ajratish mumkin; huquqlar va
majburiyatlar kabi umumiy qo‘shma so‘rovlar ham ajratiladi.

110 soniya ichida tugamagan batch `202 processing` qaytaradi va fonda davom etadi.
GET bilan natija olinadi. SQLite natijalarni avtomatik o‘chirmaydi: kamida 30 kunlik
saqlash uchun `RAG_DB` faylini doimiy diskda qoldiring. Server qayta ishga tushsa,
tugallanmagan ishlar `failed / PROCESS_RESTARTED` bo‘ladi; yakunlanganlari saqlanadi.

## Test va baholash

`start.ps1` o‘rnatgan kutubxonalar bilan qo‘lda tekshirishdan avval:

```powershell
$env:PYTHONPATH = "$PWD\.runtime\packages;$PWD"
$env:TEMP = "$PWD\.runtime\temp"
$env:TMP = $env:TEMP
```

```powershell
python -m pytest -q
python -m app.verify_corpus
python -m app.acceptance --label mening-yangi-runim
```

Oxirgi buyruq haqiqiy mahalliy HTTP serverni ishga tushiradi, 100 savolni ketma-ket
10 batchda yuboradi, natijalarni saqlaydi va tekshiruv serverini to‘xtatadi.
O‘zingiz ishlatayotgan serverni baholash:

```powershell
python -m app.evaluate --label mening-http-runim --base-url http://127.0.0.1:8000
```

Bunda `RAG_API_KEY` muhitda berilishi kerak. Runner `429`, servis va transport
xatolarini qayta urinadi, `202` ni kutadi; etalon javoblarni APIga yubormaydi.
Har safar yangi run nomini ishlating: eski natijalar ustiga yozilmaydi.

100 savol tarkibi: 35 faktik, 15 raqamli, 15 ko‘p manbali, 10 o‘zgargan norma,
10 rus/kirill, 10 javobsiz, 5 noaniq. Etalon javoblar va eski/yangi tahrir dalillari
`evaluation/questions.json` da. Bu manbadan tuzilgan rivojlantirish to‘plami;
mustaqil yoki yashirin benchmark emas. Etalonlar API tomonidan o‘qilmaydi.

Har bir run papkasida `b01.json` ... `b10.json`, `report.json` va semantik baholash
uchun `review-template.json` bor. Hisobot Hit@5 (hujjat/modda), Recall@5, MRR@5,
javobsizlik, xatolar, p50/p95, manba va tahrir tekshiruvlarini hisoblaydi.
Aniq matn mosligi va faqat etalondagi manbalar bilan hisoblangan precision
avtomatik proksi hisoblanadi; ularni mustaqil semantik baho deb talqin qilmang.
To‘ldirilgan semantik review fayli `--review FILE` orqali beriladi.

Saqlangan review qarorlarini aynan shu dataset/tizim/javoblar bilan qayta tekshirish:

```powershell
python -m app.acceptance --label mening-review-runim --review evaluation/tz-semantic-review.json
python -m app.compare_runs tz-final-http tz-release
```

Yakuniy dalillar: `evaluation/tz-release/`, `reports/tests.xml`,
`reports/corpus-verification.json`. 45 avtomatik test o‘tgan. Rivojlantirish
to‘plamida Hit@5=100%, javobsiz savollar=10/10, konservativ context precision=93%.
Reviewni ushbu o‘zgarishlarni qilgan Codex yordamchisi bergan; mustaqil ekspert bahosi emas.

Korpus o‘zgartirilganda yangi etalon versiyasini yaratish: `python -m app.prepare_evaluation`.
U boshlang‘ich datasetni `evaluation/questions-original.json` dan oladi. Runlarni
taqqoslashda esa datasetni qayta yaratmang; dataset va korpus hashlari bir xil bo‘lsin.
Oldingi natijalar boshqa dataset/korpusga tegishli bo‘lsa bevosita taqqoslanmaydi.

TZ bandlari va yakuniy tekshiruv natijalari: `TZ_COMPLIANCE.md`, `FINAL_REPORT.md`.
Avvalgi README va hisobotlar `reports/*-before-tz.md` da saqlangan.

## Xavfsizlik

- `.env` hech qachon arxivga, GitHubga yoki chatga qo‘shilmaydi. Faqat `.env.example` topshiriladi.
- `start.ps1` birinchi ishga tushirishda tasodifiy kalitni o‘zi yaratib, `.env` ga yozadi.
- Kalit tasodifan oshkor bo‘lsa: `.env` ni o‘chiring va `start.ps1` ni qayta ishga tushiring — yangi kalit yaratiladi.
- `.runtime/`, `__pycache__/`, `data/raw/` arxivga kiritilmaydi (qayta yaratiladi): raw uchun `python -m app.ingest`.
