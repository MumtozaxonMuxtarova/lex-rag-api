# TZ bo‘yicha tekshiruv

Yakuniy `final-seed-disk` HTTP tekshiruvi o‘tdi. 100 savolga tegishli 10 ta saqlangan batchning barchasida yuqori darajadagi `seed` maydoni 42 ga teng. Maxsus seed qiymati ham POST va GET orqali tekshirildi. Evaluator metrikalar uchun saqlangan o‘nta JSON faylni diskdan qayta o‘qiydi, frozen dataset va mavjud semantik review qarorlarini ishlatadi. Yakuniy test natijasi: 47/47.

Manba: «RAG API — test spetsifikatsiyasi (lex.uz)», 2026-11-03, 11 sahifa.
Quyidagi jadval kod va saqlangan tekshiruv dalillarini bog‘laydi. Sifat chegaralari
PDFda taklif sifatida berilgan; loyiha ichidagi dataset uchun ularning barchasi tekshirildi.
Yakuniy sonlar `FINAL_REPORT.md` da.

| TZ bandi | Amalga oshirish | Dalil |
|---|---|---|
| §1: 100 savol, 10 ketma-ket batch, q001–q100 | `app/runner.py`, `app/evaluate.py` | Yakuniy run ichidagi b01–b10 JSON |
| §1: etalonlar APIga yuborilmaydi | Runner faqat id, question va language maydonlarini yuboradi | `run_batches`, xom javoblar |
| §1: runlarni qayta baholash va solishtirish | Har run alohida saqlanadi, ustiga yozish bloklangan; dataset hashi tekshiriladi | `app/compare_runs.py`, `evaluation/tz-comparison.json` |
| §2: REST + JSON, /v1 | FastAPI endpointlari | `app/main.py`, haqiqiy HTTP acceptance |
| §2: POST batch, GET batch, meta, health | Barchasi mavjud | `tests/test_api.py`, `reports/acceptance.json` |
| §2: Bearer va alohida test kaliti | Server kaliti muhitdan; acceptance tasodifiy vaqtinchalik kalit yaratadi | Auth testlari, acceptance |
| §2: lotin/kirill/rus va UTF-8 | Matn asl yozuvida saqlanadi, qidiruv uchun normalizatsiya qilinadi | Ingest, script va real corpus testlari |
| §2: 1–10 savol, 11 ta bo‘lsa 400 | Pydantic validatsiyasi va 400 handler | `test_validation[eleven]` |
| §2: sync ≤120 s yoki async | 110 s dan keyin 202, ish fonda davom etadi | `test_async_and_failure_isolation` |
| §2: 1 batch/s, 429 va Retry-After | Yangi batchlar uchun limiter; retry keshga murojaat qiladi | `test_rate_limit` |
| §2: temperature=0, seed, deterministik manbalar | Deterministik qidiruv va barqaror tie-break; temperature faqat 0 | Validatsiya, idempotentlik, raw runlar |
| §2: idempotentlik | SQLite tranzaksiyasi, so‘rov hashi, natijani qayta hisoblamaslik | Retry, concurrency va persistence testlari |
| §2: versiyalar | Pipeline, model/null, reranker, rewriter, indeks, kod va tarjima xaritasi hashlari | `/v1/meta`, har bir batchning system obyekti |
| §3: request maydonlari/defaultlar | `app/models.py`, `examples/batch.json` | Request testlari va OpenAPI |
| §3: as_of_date | Tasdiqlangan amal qilish oralig‘i, har hujjat uchun sana qamrovi | Synthetic gap/boundary va 10 haqiqiy tarixiy norma testi |
| §3: answer_language / auto | Savol tilini aniqlash; rasmiy til variantiga modda bo‘yicha bog‘lash | Til aniqlash va requested-language testlari |
| §4: har id aynan bir marta | Har savolga alohida result; runner ham ID to‘plamini tekshiradi | Batch va runner testlari |
| §4: citations va [ref] | Har ishlatilgan modda uchun alohida raqamlangan havola | Single-source va multi-source testlari |
| §4: doc_id, URL, article, part, edition, status, quote | Manbadan olingan metadata; butun modda uchun part=null | Importer, source verification, raw responses |
| §4: contexts, matn, retrieval/rerank ballari | top_k gacha mos kontekst; zaif natijalar bilan to‘ldirilmaydi | Raw responses, relevance regression |
| §4: citation chunk_id contexts ichida | return_contexts=false holatida ham ishlatilgan kontekst saqlanadi | Citation va multisource testlari |
| §4: timing va system | Har savol va batchda mavjud | HTTP runlar va testlar |
| §4: confidence/usage/debug | Confidence va usage ixtiyoriy, yo‘q; debug flag bo‘yicha mavjud | Meta va JSON javoblar |
| §5: bitta savol xatosi boshqalariga ta’sir qilmaydi | Question exception isolation; status/error obyektlari | Async/failure isolation testi |
| §5: 400/401/409/429 va 202/GET | Tegishli handlerlar va saqlangan processing/completed/failed holatlari | API testlari |
| §5: natijani kamida 30 kun saqlash | SQLite avtomatik tozalanmaydi; qayta ishga tushishda yakunlangan natija qoladi | Restart persistence testi; doimiy RAG_DB yo‘riqnomasi |
| §5: testerning retry siyosati | 5/15/45 s, Retry-After, transport retry va bounded GET polling | Runner fault-injection testlari |
| §6: 35/15/15/10/10/10/5 kategoriya | Frozen 100 savollik dataset, har savolda expected_answer | `evaluation/questions.json` |
| §6: 10 o‘zgargan yoki bekor qilingan norma | Haqiqatan o‘zgargan 10 norma tanlangan; 2025 va 2026 rasmiy matnlari saqlangan | historical_evidence, 20 old/current javob tekshiruvi |
| §6: Hit@5 hujjat/modda, Recall va MRR | Doc+article mosligi va ko‘p manbali qamrov | `report.json`; MRR@5 deb aniq ko‘rsatilgan |
| §6: correctness/faithfulness/citation/context precision | Avtomatik proksilar alohida; source-grounded review qarorlari va review loader | `evaluation/tz-semantic-review.json`, yakuniy report |
| §6: no-answer, manba/tahrir, latency, xato ulushi | Alohida sonlar va p50/p95 hisoblanadi | `FINAL_REPORT.md`, `reports/acceptance.json` |
| §7: test base URL va kalit | Lokal base URL READMEda, maxfiy kalit .env da | `start.ps1`, README |
| §7: snapshot, chunking, bekor qilingan hujjat siyosati | Snapshot/qo‘llab-quvvatlangan sanalar ochiq; modda bo‘yicha chunking; repealed doc importi fail-closed | README, importer va coverage |

## Chegaralar va ixtiyoriy qismlar

- `POST /v1/rag/query` PDFda ixtiyoriy; bitta savol batch bilan yuboriladi.
- Muayyan LLM, embedding yoki vektor baza texnologiyasi PDFda majburiy emas.
  Ushbu loyiha rasmiy matndan aynan javob tuzadi; model nomlari to‘qib yozilmagan.
- Butun lex.uz qamrovi talab deb ko‘rsatilmagan. Korpusning ikki kodeks bilan
  chegaralanganligi API va interfeysda ochiq aytiladi.
- Manbalardan tuzilgan dataset va uni tuzatgan yordamchining review bahosi mustaqil
  yuridik ekspert yoki yashirin benchmark o‘rnini bosmaydi. Bu cheklov yakuniy hisobotda ham bor.
- Alohida deployment, ko‘p worker va avtomatik kundalik import ushbu TZ checklistida
  majburiy emas. Hozir bitta worker va qo‘lda qayta import ishlatiladi.
