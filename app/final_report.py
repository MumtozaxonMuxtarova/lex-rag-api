"""Build delivery documentation from preserved test and HTTP evidence."""
import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def build(label):
    folder = Path('evaluation') / label
    report = json.loads((folder / 'report.json').read_text(encoding='utf-8'))
    m = report['metrics']
    first = json.loads((folder / 'b01.json').read_text(encoding='utf-8'))
    verified = json.loads(Path('reports/corpus-verification.json').read_text(encoding='utf-8'))
    suites = ET.parse('reports/tests.xml').getroot().iter('testsuite')
    counts = {key: 0 for key in ('tests', 'errors', 'failures', 'skipped')}
    for suite in suites:
        for key in counts:
            counts[key] += int(suite.get(key, 0))
    assert counts['errors'] == counts['failures'] == 0
    assert verified['verified'] and report['semantic_review_complete']
    assert first['system']['index_version'] == verified['corpus_sha256'][:16]
    checks = [
        ('Hit@5 (hujjat)', m['Hit@5_document'], .9, '>='),
        ('Hit@5 (hujjat + modda)', m['Hit@5'], .8, '>='),
        ('MRR@5', m['MRR@5'], .7, '>='),
        ('Context precision (konservativ)', m['context_precision'], .6, '>='),
        ('Answer correctness (0–2)', m['answer_correctness'], 1.6, '>='),
        ('Faithfulness', m['faithfulness'], .95, '>='),
        ('Citation accuracy', m['citation_accuracy'], .9, '>='),
        ('To‘qilgan manba', m['fabricated_sources'], 0, '<='),
        ('So‘ralgan sanaga mos bo‘lmagan tahrir', m['out_of_date_citations'], 0, '<='),
        ('To‘g‘ri no_answer (10 savoldan)', m['correct_rejections'], 9, '>='),
        ('Savol p50 (ms)', m['latency_p50_ms'], 5000, '<='),
        ('Savol p95 (ms)', m['latency_p95_ms'], 12000, '<='),
        ('Xato ulushi', m['error_rate'], .02, '<='),
    ]
    table = ['| Metrika | Natija | TZdagi taklif | Holat |', '|---|---:|---:|---|']
    for name, value, threshold, operator in checks:
        passed = value >= threshold if operator == '>=' else value <= threshold
        table.append(f'| {name} | {value:.4f} | {operator} {threshold} | {"O‘tdi" if passed else "O‘tmadi"} |')
    assert all(value >= target if op == '>=' else value <= target for _, value, target, op in checks)
    text = f'''# Yakuniy hisobot — 2026-11-06

Lokal loyiha: `{Path.cwd().resolve()}`.
Pipeline: `{first['system']['pipeline_version']}`, kod versiyasi: `{first['system']['implementation_version']}`.

## Amalga oshirilgan ishlar

- Ko‘p mavzuli qidiruv va bir nechta moddadan raqamlangan iqtibosli javob.
- Og‘zaki savollar uchun umumiy so‘rovni aniqlashtirish qoidalari; aniq mavzularda ortiqcha kontekstlarni filtrlash.
- Ruscha va o‘zbekcha modda so‘rovlari, kirill tilini avtomatik aniqlash; javob tilini tanlashda rasmiy nusxadan foydalanish.
- Tarixiy tahrirlar, amal qilish oraliqlari va qamrovdagi bo‘shliqlarni tekshirish.
- Haqiqiy o‘zgargan normalar bo‘yicha 10 savol va eski/yangi javoblar uchun 20 ta sana tekshiruvi.
- Qayta urinish, async polling, saqlangan runlarni solishtirish, sifat review fayllari va haqiqiy HTTP tekshiruv vositalari.
- Yangilangan ishga tushirish yo‘riqnomasi va TZ bandlari bo‘yicha dalillar jadvali.

## Dalillar

**{counts['tests']} avtomatik test o‘tdi**, errors=0, failures=0, skipped={counts['skipped']}.
Test natijasi: `reports/tests.xml`. Bitta kutubxonaning deprecation ogohlantirishi bor.

Haqiqiy HTTP run: `evaluation/{label}/b01.json` … `b10.json`.
100 savol ketma-ket 10 batchda yuborilgan; etalonlar APIga yuborilmagan.
Hisobot: `evaluation/{label}/report.json`; HTTP dalillari: `reports/acceptance.json`.

{chr(10).join(table)}

Retrieval maxraji: 90 javobli savol. Javobsiz 10 savol alohida hisoblangan.
MRR qaytarilgan natijalarning dastlabki 5 tasi bo‘yicha (MRR@5).
15 ko‘p manbali savolning {m['multi_all_targets_top5']} tasida barcha etalon moddalar topilgan.
`top_k` yuqori chegara: past moslikdagi moddalar bilan ro‘yxat sun’iy ravishda to‘ldirilmaydi.
Context precision har savolda amalda qaytgan kontekstlar bo‘yicha o‘rtachalanadi;
faqat tasdiqlangan etalon manbalar relevant deb belgilangan, shuning uchun bu konservativ baho.
Latency serverdagi savol ishlov vaqti; tarmoqdagi yo‘l va server ishga tushish vaqtini o‘z ichiga olmaydi.

## Bahoning chegaralari

100 savol manbalardan tuzilgan rivojlantirish to‘plami; mustaqil/yashirin benchmark emas.
Review muallifi: **{report['review']['reviewer']}**. Savol ma’nosi va modda mavzusi solishtirildi;
kanonik javoblarning to‘liqligi, matnning manbadan aynan olinishi va manba mosligi tekshirildi.
Bu o‘sha yordamchi tomonidan berilgan baho; mustaqil LLM-hakam yoki yuridik ekspert xulosasi emas.
Review qarorlari: `evaluation/tz-semantic-review.json`; uning dataset, tizim va javoblarga mosligi
runner tomonidan qayta tekshirildi. Alohida ekspert xohlasa `review-template.json` dan foydalanishi mumkin.

## Korpus

{verified['raw_sources']} rasmiy til/tahrir nusxasi, {verified['chunks']} modda bo‘lagi;
Mehnat kodeksi va Fuqarolik kodeksi I qismi, uch tilda. Bu butun lex.uz emas.
Snapshot: 2026-11-06. Hashlar: `reports/corpus-verification.json`.
Sana qamrovi: `{json.dumps(verified['coverage']['date_windows'], ensure_ascii=False)}`.
Eskirgan norma o‘rniga hozirgi matn qo‘yilmaydi: so‘ralgan sanada amaldagi matn olinadi.
Qamrab olinmagan sanalar xato bilan qaytariladi. Butunlay bekor qilingan hujjat importer tomonidan
amaldagi hujjat sifatida qabul qilinmaydi. 10 tahrir testi haqiqatan o‘zgargan normalarga tegishli.

Korpus SHA-256: `{verified['corpus_sha256']}`.
Dataset SHA-256: `{report['dataset_sha256']}`.

## Oldin va keyin

`evaluation/tz-comparison.json` bir xil dataset va korpusdagi HTTP runlarni solishtiradi.
Kontekst filtri qo‘shilishidan oldingi run: `tz-final-http`; keyingi run: `{label}`.
Etalon kontekst precision 0.3222 dan {m['gold_context_precision_at5']:.4f} ga oshdi;
Hit@5 1.0 bo‘lib qoldi. Dastlabki BM25/single-source holatiga oid eski `before/after`
runlari boshqa korpus/datasetga tegishli: ularni yangi natijalar bilan bevosita solishtirmang.

## Ishga tushirish

`.\\start.ps1` — sayt `http://127.0.0.1:8000/`, API hujjati `/docs`.
API kalit `.env` da; hisobotda e’lon qilinmaydi. Test kalitlari vaqtinchalik va alohida.
SQLite faylini doimiy diskda saqlang; natijalar avtomatik o‘chirilmaydi.
Bitta worker ishlatiladi. LLM/embedding yo‘q: javob rasmiy matnlardan aynan tuziladi.
GitHub yoki tashqi hostingga nashr qilinmagan.
'''
    Path('FINAL_REPORT.md').write_text(text, encoding='utf-8')
    print(f'Final report written from {label}: {counts["tests"]} tests, all proposed development thresholds passed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    build(parser.parse_args().label)
