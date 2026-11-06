# Yakuniy hisobot — 2026-11-06

33 avtomatik test o‘tdi. 100 savol oldin va keyin 10 tadan batchlarda baholandi.

| Metrika | Oldin | Keyin |
|---|---:|---:|
| Hit@1 | 0.8444 | 0.9333 |
| Hit@5 | 0.8667 | 0.9667 |
| MRR@5 | 0.8556 | 0.9472 |
| expected_missing_top5 | 12.0000 | 3.0000 |
| wrong_top1_answerable | 14.0000 | 6.0000 |
| no_result_answerable | 0.0000 | 0.0000 |
| correct_rejections | 9.0000 | 10.0000 |
| errors | 0.0000 | 0.0000 |

Dataset SHA-256: 2430a56e37bafdd424939dd9cd9d521c3f4d37404be97e96f848617431925221

Maxraj 90 javobli savol; 10 ta qamrovdan tashqari savol alohida. MRR faqat top-5 bo‘yicha. Ko‘p manbali savolda Hit istalgan tegishli manba; barcha etalon top-5 da: 13/15.

Etalonlar asl korpusdan olingan iqtiboslar; APIga etalon yuborilmadi. Bu manbadan tuzilgan rivojlantirish to‘plami, mustaqil benchmark emas. 10 tarixiy/bekor qilingan norma testi o‘rniga mavjud snapshot tahriri tekshirildi; tarixiy qamrov TZga to‘liq mos emas.

Qolgan xatolar: q007/q008/q044 da etalon birinchi emas; q012/q024/q060 da top-5 ichida ham yo‘q. LLM ulanmagan, ko‘p moddani sintez qilmaydi; javob birinchi manbaning asl matni. Generatsiya correctness va to‘liq tezlik p50/p95 bahosi berilmadi.

Korpus: faqat Mehnat kodeksi va Fuqarolik kodeksi I qismi; 3 tilda 2937 bo‘lak. Snapshot 2026-11-06. Eski arxiv va asl loyiha o‘chirilmagan.

D: ga yozish ikki ruxsat so‘rovida berilmadi. D: ga saqlash talabi BAJARILMAGAN. Arxiv yakuniy topshirish deb ko‘rsatilmaydi.

Haqiqiy yakuniy lokal papka: C:/Users/polaponim/Documents/Codex/2026-11-06/men/outputs/lex-rag-final-2026-11-06

Ishga tushirish: .\start.ps1. Sayt http://127.0.0.1:8000/. Mahalliy kalit birinchi ishga tushishda yangi .env fayliga yaratiladi. GitHub push qilinmagan.

Yakuniy ishga tushirish aynan yangi papkadan bajarildi; HTTP, autentifikatsiya, frontend va 33-modda qidiruvi jonli tekshirildi. 6 asl HTML va korpus hashi qayta tasdiqlandi. Tafsilot: reports/final-checks.json.
