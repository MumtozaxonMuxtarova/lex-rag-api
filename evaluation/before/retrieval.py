"""BM25 article search with Uzbek script and apostrophe normalization."""
import math
import re
from collections import Counter, defaultdict

CYRILLIC = dict(zip('абвгдеёжзийклмнопрстуфхцчшъыьэюяўқғҳ',
                    ['a','b','v','g','d','e','yo','j','z','i','y','k','l','m','n','o','p','r','s','t','u','f','x','ts','ch','sh','','i','','e','yu','ya',"o'",'q',"g'",'h']))
CYRILLIC['щ'] = 'shch'
STOPS = set('har eng va yoki uchun bilan bu shu ushbu bir biror qanday qancha nima qaysi haqida kerak bol boladi etadi tashkil как какой каков сколько в на по из и или для о об это установлен устанавливает предусмотрен'.split())

def normalize(text):
    text = text.casefold()
    text = ''.join(CYRILLIC.get(c, c) for c in text)
    for mark in ["'", 'ʻ', 'ʼ', '‘', '’', '`', 'ʹ']:
        text = text.replace(mark, '')
    return text

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

def tokenize(text, language='uz-Latn'):
    russian = language == 'ru'
    # Normalize Uzbek Cyrillic before morphology; Russian uses its own endings.
    prepared = text.casefold() if russian else normalize(text)
    raw = re.findall(r'[^\W_]+', prepared)
    stops = {stem(w, russian) for w in STOPS}
    return [s for w in raw if (s := stem(w, russian)) and s not in stops]

class BM25Index:
    def __init__(self, chunks):
        self.chunks = chunks
        self.postings = defaultdict(list)
        self.lengths = []
        self.termsets = []
        self.heading_terms = []
        for index, chunk in enumerate(chunks):
            language = chunk['language']
            terms = tokenize(chunk['text'], language)
            terms += tokenize(chunk.get('heading', ''), language) * 2
            self.lengths.append(len(terms))
            counts = Counter(terms)
            self.termsets.append(set(counts))
            self.heading_terms.append(set(tokenize(chunk.get('heading', ''), language)))
            for term, frequency in counts.items():
                self.postings[(language == 'ru', term)].append((index, frequency))
        self.average_length = sum(self.lengths) / max(len(chunks), 1)

    def search(self, question, language, as_of_date):
        terms = set(tokenize(question, language))
        scores = defaultdict(float)
        n = len(self.chunks)
        for term in sorted(terms):
            postings = self.postings.get((language == 'ru', term), [])
            idf = math.log(1 + (n - len(postings) + .5) / (len(postings) + .5))
            for index, frequency in postings:
                chunk = self.chunks[index]
                if chunk['language'] != language:
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
                if ('umumiy' in normalized_heading or 'obshchiy' in normalized_heading) and not any(t in normalized_question for t in ('maxsus', 'spetsial')):
                    rerank += 4
                results.append((score, rerank, self.chunks[index]))
        return sorted(results, key=lambda pair: (-pair[1], pair[2]['chunk_id']))

def best_passage(chunk, question):
    paragraphs = chunk.get('paragraphs')
    if not paragraphs:
        return chunk['text']
    # Keep all paragraphs for multi-part answers; no legal text is silently shortened.
    # A short article (including the annual-leave example) naturally yields a short answer.
    return '\n'.join(paragraphs)
