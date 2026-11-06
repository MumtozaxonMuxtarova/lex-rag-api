# Yakuniy hisobot — 2026-11-06

**Yakuniy qaror: PASS.** `final-seed-disk` runida barcha 10 saqlangan HTTP javobda `seed=42` bor. Alohida test boshqa qiymat (917) POST va GET javoblarida ham qaytishini tekshirdi. Seed so‘rov parametrini qayd etadi.

Metrikalar diskdan qayta ochilgan `b01.json` … `b10.json`, frozen dataset va mavjud review qarorlaridan hisoblandi. Tahrirning amal qilish oralig‘i iqtibos bilan javobda saqlanadi. 100 javob, kontekstlar va ilgari baholangan iqtibos maydonlari avvalgi review runiga aynan mos. Qarorlarning ushbu run uchun nusxasi `evaluation/final-seed-disk/review-decisions.json` da.

Lokal loyiha: `D:\pdp univer 4 kurs\1 semester\AI\06.11.2026\lex-rag-final-2026-11-06`.
Pipeline: `0.4.0`, kod versiyasi: `28230ff628ff3fba`.

## Amalga oshirilgan ishlar

- Ko‘p mavzuli qidiruv va bir nechta moddadan raqamlangan iqtibosli javob.
- Og‘zaki savollar uchun umumiy so‘rovni aniqlashtirish qoidalari; aniq mavzularda ortiqcha kontekstlarni filtrlash.
- Ruscha va o‘zbekcha modda so‘rovlari, kirill tilini avtomatik aniqlash; javob tilini tanlashda rasmiy nusxadan foydalanish.
- Tarixiy tahrirlar, amal qilish oraliqlari va qamrovdagi bo‘shliqlarni tekshirish.
- Haqiqiy o‘zgargan normalar bo‘yicha 10 savol va eski/yangi javoblar uchun 20 ta sana tekshiruvi.
- Qayta urinish, async polling, saqlangan runlarni solishtirish, sifat review fayllari va haqiqiy HTTP tekshiruv vositalari.
- Yangilangan ishga tushirish yo‘riqnomasi va TZ bandlari bo‘yicha dalillar jadvali.

## Dalillar

**47 avtomatik test o‘tdi**, errors=0, failures=0, skipped=0.
Test natijasi: `reports/tests.xml`. Bitta kutubxonaning deprecation ogohlantirishi bor.

Haqiqiy HTTP run: `evaluation/final-seed-disk/b01.json` … `b10.json`.
100 savol ketma-ket 10 batchda yuborilgan; etalonlar APIga yuborilmagan.
Hisobot: `evaluation/final-seed-disk/report.json`; HTTP dalillari: `reports/acceptance.json`.

| Metrika | Natija | TZdagi taklif | Holat |
|---|---:|---:|---|
| Hit@5 (hujjat) | 1.0000 | >= 0.9 | O‘tdi |
| Hit@5 (hujjat + modda) | 1.0000 | >= 0.8 | O‘tdi |
| MRR@5 | 1.0000 | >= 0.7 | O‘tdi |
| Context precision (konservativ) | 0.9300 | >= 0.6 | O‘tdi |
| Answer correctness (0–2) | 2.0000 | >= 1.6 | O‘tdi |
| Faithfulness | 1.0000 | >= 0.95 | O‘tdi |
| Citation accuracy | 1.0000 | >= 0.9 | O‘tdi |
| To‘qilgan manba | 0.0000 | <= 0 | O‘tdi |
| So‘ralgan sanaga mos bo‘lmagan tahrir | 0.0000 | <= 0 | O‘tdi |
| To‘g‘ri no_answer (10 savoldan) | 10.0000 | >= 9 | O‘tdi |
| Savol p50 (ms) | 26.8680 | <= 5000 | O‘tdi |
| Savol p95 (ms) | 63.7470 | <= 12000 | O‘tdi |
| Xato ulushi | 0.0000 | <= 0.02 | O‘tdi |

Retrieval maxraji: 90 javobli savol. Javobsiz 10 savol alohida hisoblangan.
MRR qaytarilgan natijalarning dastlabki 5 tasi bo‘yicha (MRR@5).
15 ko‘p manbali savolning 15 tasida barcha etalon moddalar topilgan.
`top_k` yuqori chegara: past moslikdagi moddalar bilan ro‘yxat sun’iy ravishda to‘ldirilmaydi.
Context precision har savolda amalda qaytgan kontekstlar bo‘yicha o‘rtachalanadi;
faqat tasdiqlangan etalon manbalar relevant deb belgilangan, shuning uchun bu konservativ baho.
Latency serverdagi savol ishlov vaqti; tarmoqdagi yo‘l va server ishga tushish vaqtini o‘z ichiga olmaydi.

## Bahoning chegaralari

100 savol manbalardan tuzilgan rivojlantirish to‘plami; mustaqil/yashirin benchmark emas.
Review muallifi: **Codex, source-grounded development review**. Savol ma’nosi va modda mavzusi solishtirildi;
kanonik javoblarning to‘liqligi, matnning manbadan aynan olinishi va manba mosligi tekshirildi.
Bu o‘sha yordamchi tomonidan berilgan baho; mustaqil LLM-hakam yoki yuridik ekspert xulosasi emas.
Review qarorlari: `evaluation/tz-semantic-review.json`; uning dataset, tizim va javoblarga mosligi
runner tomonidan qayta tekshirildi. Alohida ekspert xohlasa `review-template.json` dan foydalanishi mumkin.

## Korpus

63 rasmiy til/tahrir nusxasi, 29727 modda bo‘lagi;
Mehnat kodeksi va Fuqarolik kodeksi I qismi, uch tilda. Bu butun lex.uz emas.
Snapshot: 2026-11-06. Hashlar: `reports/corpus-verification.json`.
Sana qamrovi: `{"ru": {"from": "2024-12-06", "to": "2026-11-06"}, "uz-Cyrl": {"from": "2024-12-06", "to": "2026-11-06"}, "uz-Latn": {"from": "2024-12-06", "to": "2026-11-06"}}`.
Eskirgan norma o‘rniga hozirgi matn qo‘yilmaydi: so‘ralgan sanada amaldagi matn olinadi.
Qamrab olinmagan sanalar xato bilan qaytariladi. Butunlay bekor qilingan hujjat importer tomonidan
amaldagi hujjat sifatida qabul qilinmaydi. 10 tahrir testi haqiqatan o‘zgargan normalarga tegishli.

Korpus SHA-256: `f7713de8144eee76fa69d8410a80b60040cb94ca206b9e533b0ed9cc0ca744e4`.
Dataset SHA-256: `bc9eeba49ed3706e471688263619dc345361297d6db3adf19028c5bfe69485ec`.

## Oldin va keyin

`evaluation/tz-comparison.json` bir xil dataset va korpusdagi HTTP runlarni solishtiradi.
Kontekst filtri qo‘shilishidan oldingi run: `tz-final-http`; keyingi run: `final-seed-disk`.
Etalon kontekst precision 0.3222 dan 0.9300 ga oshdi;
Hit@5 1.0 bo‘lib qoldi. Dastlabki BM25/single-source holatiga oid eski `before/after`
runlari boshqa korpus/datasetga tegishli: ularni yangi natijalar bilan bevosita solishtirmang.

## Ishga tushirish

`.\start.ps1` — sayt `http://127.0.0.1:8000/`, API hujjati `/docs`.
API kalit `.env` da; hisobotda e’lon qilinmaydi. Test kalitlari vaqtinchalik va alohida.
SQLite faylini doimiy diskda saqlang; natijalar avtomatik o‘chirilmaydi.
Bitta worker ishlatiladi. LLM/embedding yo‘q: javob rasmiy matnlardan aynan tuziladi.
GitHub yoki tashqi hostingga nashr qilinmagan.
