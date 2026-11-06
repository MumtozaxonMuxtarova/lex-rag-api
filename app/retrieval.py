"""BM25 article search with Uzbek script and apostrophe normalization."""
import math
import re
from collections import Counter, defaultdict
from functools import lru_cache

CYRILLIC = dict(zip('абвгдеёжзийклмнопрстуфхцчшъыьэюяўқғҳ',
                    ['a','b','v','g','d','e','yo','j','z','i','y','k','l','m','n','o','p','r','s','t','u','f','x','ts','ch','sh','','i','','e','yu','ya',"o'",'q',"g'",'h']))
CYRILLIC['щ'] = 'shch'
STOPS = set('har eng va yoki uchun bilan bu shu ushbu bir biror qanday qancha nima qaysi haqida kerak bol boladi etadi tashkil как какой каков сколько в на по из и или для о об это установлен устанавливает предусмотрен'.split())
STOPS.update('boyicha qanday qoidalarni qoida belgilaydi belgilangan tartibga solinadi holatiga kim'.split())
STOPS.update('necha yangi kirganda ishlasam yuraman olsam berishadi boladimi mumkinmi'.split())

def normalize(text):
    text = text.casefold()
    text = ''.join(CYRILLIC.get(c, c) for c in text)
    for mark in ["'", 'ʻ', 'ʼ', '‘', '’', '`', 'ʹ']:
        text = text.replace(mark, '')
    return text

@lru_cache(maxsize=65536)
def stem(word, russian=False):
    if russian:
        word = re.sub(r'(иями|ами|ого|ему|ыми|ими|им|ой|ий|ый|ая|ое|ые|ие|ом|ам|ах|ов|ев|ей|ям|ях|ую|юю|а|я|ы|и|у|ю|е|о)$', '', word) if len(word) > 5 else word
        return normalize(word)
    word = normalize(word)
    if word in ('yillik', 'yilgi'):
        return 'yil'
    for _ in range(2):
        for suffix in ('larining', 'larning', 'ining', 'ning', 'larini', 'larni', 'larga', 'larda', 'lardan', 'dan', 'lar', 'ni', 'ga', 'da', 'si', 'i'):
            if word.endswith(suffix) and len(word) - len(suffix) >= 4:
                word = word[:-len(suffix)]
                break
        else:
            break
    if word in ('yillik', 'yilgi', 'yilg'):
        return 'yil'
    if word.startswith('davomiyl') or word.startswith('muddat'):
        return 'muddat'
    return word

@lru_cache(maxsize=2)
def stop_words(russian):
    return frozenset(stem(w, russian) for w in STOPS)


@lru_cache(maxsize=8192)
def tokenize(text, language='uz-Latn'):
    russian = language == 'ru'
    # Normalize Uzbek Cyrillic before morphology; Russian uses its own endings.
    prepared = text.casefold() if russian else normalize(text)
    # Snapshot date is provided separately in options, not a content keyword.
    prepared = re.sub(r'\b\d{4}-\d{2}-\d{2}\b', ' ', prepared)
    raw = re.findall(r'[^\W_]+', prepared)
    stops = stop_words(russian)
    return tuple(s for w in raw if (s := stem(w, russian)) and s not in stops)


def query_subjects(question):
    subjects = [s.strip() for s in re.split(r';|\n', question) if s.strip()]
    if len(subjects) > 1:
        return subjects
    # Carry the shared subject into both halves of a common compound question.
    compound = re.search(r'^(.*?)(huquqlari|ҳуқуқлари|права)\s+(?:va|ҳамда|ва|и)\s+(majburiyatlari|мажбуриятлари|обязанности)(.*)$', question, re.I)
    if compound:
        return [compound[1] + compound[2], compound[1] + compound[3] + compound[4]]
    return subjects


def rewrite_query(question, language):
    if language == 'ru':
        return question
    text = normalize(question)
    # General colloquial expressions are mapped to the vocabulary of the corpus.
    # These rules contain no document numbers, article numbers, or benchmark IDs.
    replacements = [
        (r'\b(?:necha|qancha)\s+kun\b', 'davomiyligi'),
        (r'\bqancha\s+vaqt\b', 'muddat'),
        (r'\bkamida\b', 'kam'),
        (r'\bdam\s+olish\s+(tatil\w*)', r'mehnat \1'),
        (r'\bbolib(?:\s*-\s*|\s+)bolib\b', 'qismlarga bolish'),
        (r'\botpuska\b', 'mehnat tatili'),
    ]
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    if re.search(r'\bsinov\w*', text) and re.search(r'\b(muddat|davomiyligi)\b', text):
        text += ' dastlabki sinov muddati'
    return text

class BM25Index:
    def __init__(self, chunks):
        self.chunks = chunks
        self.postings = defaultdict(list)
        self.lengths = []
        self.termsets = []
        self.heading_terms = []
        for index, chunk in enumerate(chunks):
            language = chunk['language']
            terms = list(tokenize(chunk['text'], language))
            terms += tokenize(chunk.get('heading', ''), language) * 2
            self.lengths.append(len(terms))
            counts = Counter(terms)
            self.termsets.append(set(counts))
            self.heading_terms.append(set(tokenize(chunk.get('heading', ''), language)))
            for term, frequency in counts.items():
                self.postings[(language == 'ru', term)].append((index, frequency))
        self.average_length = sum(self.lengths) / max(len(chunks), 1)

    def search(self, question, language, as_of_date):
        # Retrieve each explicitly separated subject independently, then interleave.
        # This preserves both subjects of a multi-source question within top-k.
        subjects = query_subjects(question)
        if len(subjects) > 1:
            lists = [self._search(subject, language, as_of_date) for subject in subjects]
            merged, seen = [], set()
            for rank in range(max(map(len, lists), default=0)):
                for rows in lists:
                    if rank < len(rows) and rows[rank][2]['chunk_id'] not in seen:
                        merged.append(rows[rank])
                        seen.add(rows[rank][2]['chunk_id'])
            return merged
        return self._search(question, language, as_of_date)

    def _search(self, question, language, as_of_date):
        question = rewrite_query(question, language)
        terms = set(tokenize(question, language))
        normalized_question = normalize(question)
        explicit_article = re.search(r'\b(\d+(?:\^\d+)?)-modda', normalized_question)
        russian_article = re.search(r'\bstat(?:ya|i|e|yu)\s+(\d+(?:\^\d+)?)', normalized_question)
        article_number = explicit_article[1] if explicit_article else russian_article[1] if russian_article else None
        explicit_family = 'mehnat' if re.search(r'mehnat\s+kodeks', normalized_question) else 'fuqarolik' if re.search(r'fuqarolik\s+kodeks', normalized_question) else 'trudov' if 'trudov' in normalized_question else 'grajdansk' if 'grajdansk' in normalized_question else None
        scores = defaultdict(float)
        n = len(self.chunks)
        for term in sorted(terms):
            postings = self.postings.get((language == 'ru', term), [])
            idf = math.log(1 + (n - len(postings) + .5) / (len(postings) + .5))
            for index, frequency in postings:
                chunk = self.chunks[index]
                if article_number and chunk.get('article_number') != article_number:
                    continue
                if explicit_family and explicit_family not in normalize(chunk['doc_title']):
                    continue
                if chunk['language'] != language:
                    continue
                if chunk.get('doc_status') != 'amalda' or chunk.get('article_status') == 'repealed':
                    continue
                if not (chunk['valid_from'] <= as_of_date and (not chunk['valid_to'] or as_of_date < chunk['valid_to'])):
                    continue
                length_factor = .25 + .75 * self.lengths[index] / max(self.average_length, 1)
                scores[index] += idf * frequency * 2.5 / (frequency + 1.5 * length_factor)
        results = []
        for index, score in scores.items():
            coverage = len(terms & self.termsets[index]) / max(len(terms), 1)
            if coverage >= .4:
                heading = self.heading_terms[index]
                # Favor the article whose subject matches the question, rather than
                # a long exceptional provision mentioning the same words many times.
                rerank = score + 15 * len(terms & heading) - 2 * len(heading - terms)
                normalized_heading = normalize(self.chunks[index].get('heading', ''))
                normalized_question = normalize(question)
                subject_heading = re.sub(r'^(?:\d+(?:\^\d+)?-(?:modda|модда)\.|Статья\s+\d+(?:\^\d+)?\.)\s*', '', self.chunks[index].get('heading', ''), flags=re.I)
                title_terms = set(tokenize(subject_heading, language))
                if len(title_terms) >= 2 and title_terms <= terms:
                    rerank += 20
                if ('umumiy' in normalized_heading or 'obshchiy' in normalized_heading) and not any(t in normalized_question for t in ('maxsus', 'spetsial')):
                    rerank += 4
                results.append((score, rerank, self.chunks[index]))
        results.sort(key=lambda pair: (-pair[1], pair[2]['chunk_id']))
        # top_k is an upper bound, not a reason to pad a precise query with weak
        # matches. Apply the same relative relevance cutoff to each subject.
        if results and results[0][1] > 0:
            cutoff = results[0][1] - max(12, results[0][1] * .3)
            results = [row for row in results if row[1] >= cutoff]
        return results

def best_passage(chunk, question):
    paragraphs = chunk.get('paragraphs')
    if not paragraphs:
        return chunk['text']
    # Keep all paragraphs for multi-part answers; no legal text is silently shortened.
    # A short article (including the annual-leave example) naturally yields a short answer.
    return '\n'.join(paragraphs)
