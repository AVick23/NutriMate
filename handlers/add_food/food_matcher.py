# handlers/add_food/food_matcher.py
"""
Улучшенный матчер продуктов для NutriMate.

Поддерживает:
- Лемматизацию через pymorphy2 (для русского языка)
- Trigram-индекс для быстрого fuzzy поиска
- Префиксный поиск для автокомплита
- Token Set Ratio для составных блюд
- BM25-ранжирование результатов
- Фонетический поиск (русский Metaphone)
- Умную кулинарную токенизацию (с биграммами для "с молоком")
- Парсинг количества из текста ("2 яйца", "300г", "полтора банана")
- LRU-кэширование результатов
- Интеграцию с Open Food Facts API
"""

import re
import math
import logging
from typing import Optional, List, Dict, Any, Tuple, Set
from collections import OrderedDict, Counter
from dataclasses import dataclass, field
from enum import Enum

# ✅ ВАЖНО: logger определяется в самом начале, чтобы избежать NameError
logger = logging.getLogger(__name__)

# Внешние зависимости (опциональные)
try:
    import Levenshtein
    HAS_LEVENSHTEIN = True
except ImportError:
    HAS_LEVENSHTEIN = False

try:
    import pymorphy2
    HAS_PYMORPHY = True
except ImportError:
    HAS_PYMORPHY = False


class MatchStrategy(Enum):
    """Стратегии поиска."""
    EXACT = "exact"           # Точное совпадение
    NORMALIZED = "normalized" # После лемматизации
    SYNONYM = "synonym"       # Через синоним
    TYPO = "typo"             # Исправление опечатки
    PHONETIC = "phonetic"     # Фонетическое сходство
    PARTIAL = "partial"       # Частичное совпадение (Token Set)
    PREFIX = "prefix"         # Префиксный поиск (автокомплит)
    TRIGRAM = "trigram"       # Trigram fuzzy поиск
    API = "api"               # Через внешнее API


@dataclass
class MatchResult:
    """Результат поиска."""
    food: Dict[str, Any]
    strategy: MatchStrategy
    confidence: float  # 0.0 - 1.0
    distance: int = 0
    matched_words: List[str] = field(default_factory=list)
    db_index: int = -1  # ✅ Индекс в БД для быстрого доступа (вместо id(food))

    def __repr__(self):
        return f"MatchResult({self.food['name']}, {self.strategy.value}, {self.confidence:.2f})"


class OptimizedFoodMatcher:
    """
    Улучшенный матчер продуктов с множеством стратегий поиска.
    
    Оптимизирован для быстрого поиска в локальной базе (~400 продуктов)
    с fallback на внешнее API (Open Food Facts).
    """

    # ========== КОНСТАНТЫ ==========

    # Синонимы с весами (1.0 = полный синоним, 0.8 = близкий, 0.6 = связанный)
    SYNONYMS: Dict[str, List[Tuple[str, float]]] = {
        "картошка": [("картофель", 1.0), ("пюре", 0.7)],
        "картофель": [("картошка", 1.0), ("пюре", 0.7)],
        "макароны": [("паста", 1.0), ("спагетти", 0.9), ("лапша", 0.8)],
        "паста": [("макароны", 1.0), ("спагетти", 0.9)],
        "гречка": [("гречневая крупа", 1.0), ("греча", 0.9)],
        "курица": [("кура", 0.9), ("курочка", 0.8), ("цыпленок", 0.8)],
        "свинина": [("свининка", 0.9)],
        "говядина": [("говядинка", 0.9), ("телятина", 0.8)],
        "хлеб": [("булка", 0.8), ("батон", 0.8), ("хлебушек", 0.7)],
        "молоко": [("молочко", 0.9)],
        "кефир": [("кефирчик", 0.9)],
        "творог": [("творожок", 0.9)],
        "сыр": [("сырок", 0.9)],
        "яблоко": [("яблочко", 0.9)],
        "банан": [("бананчик", 0.9)],
        "апельсин": [("апельсинка", 0.9)],
        "яйцо": [("яичко", 0.9), ("яйца", 1.0)],
        "омлет": [("яичница", 0.8)],
        "суп": [("супчик", 0.9), ("бульон", 0.7)],
        "котлета": [("котлетка", 0.9), ("биточек", 0.7)],
        "сосиска": [("сарделька", 0.8)],
        "бутерброд": [("сэндвич", 0.9), ("бутик", 0.6)],
        "салат": [("салатик", 0.9)],
        "каша": [("кашка", 0.9)],
    }

    # Опасные пары для коротких слов (чтобы "рис" не стал "сир")
    DANGEROUS_PAIRS: Set[Tuple[str, str]] = {
        ('рис', 'сир'), ('рис', 'суп'), ('сыр', 'сир'),
        ('сок', 'кот'), ('чай', 'щай'), ('сало', 'сила'),
        ('лук', 'сук'), ('жир', 'мир'), ('шок', 'сок'),
        ('суп', 'зуб'), ('кот', 'ток'), ('сон', 'нос'),
    }

    # ✅ РАЗДЕЛЕНО: грамматические стоп-слова (удаляются)
    GRAMMATICAL_STOP_WORDS: Set[str] = {
        'и', 'или', 'а', 'но', 'да', 'же', 'бы', 'ли', 'то'
    }

    # ✅ Кулинарные модификаторы (сохраняются как биграммы: "с_молоком")
    CULINARY_MODIFIERS: Set[str] = {
        'с', 'без', 'под', 'над', 'в', 'на', 'из', 'от', 'до', 'для', 'к', 'по', 'при'
    }

    # Числа словами (для парсинга "два яйца", "полтора банана")
    NUMBER_WORDS: Dict[str, float] = {
        'один': 1, 'одна': 1, 'одно': 1,
        'два': 2, 'две': 2, 'двух': 2,
        'три': 3, 'трёх': 3, 'трех': 3,
        'четыре': 4, 'пять': 5,
        'шесть': 6, 'семь': 7, 'восемь': 8,
        'девять': 9, 'десять': 10,
        'полтора': 1.5, 'полторы': 1.5,
    }

    # Русский алфавит для фонетического кодирования
    RUSSIAN_SOUNDEX_MAP = {
        'а': 'А', 'б': 'Б', 'в': 'В', 'г': 'Г', 'д': 'Д',
        'е': 'Е', 'ё': 'Е', 'ж': 'Ж', 'з': 'З', 'и': 'И',
        'й': 'Й', 'к': 'К', 'л': 'Л', 'м': 'М', 'н': 'Н',
        'о': 'О', 'п': 'П', 'р': 'Р', 'с': 'С', 'т': 'Т',
        'у': 'У', 'ф': 'Ф', 'х': 'Х', 'ц': 'Ц', 'ч': 'Ч',
        'ш': 'Ш', 'щ': 'Щ', 'ъ': '', 'ы': 'Ы', 'ь': '',
        'э': 'Э', 'ю': 'Ю', 'я': 'Я',
    }

    # Фонетические группы (похожие по звучанию буквы)
    PHONETIC_GROUPS = {
        frozenset(['а', 'я']), frozenset(['о', 'ё']),
        frozenset(['у', 'ю']), frozenset(['ы', 'и']),
        frozenset(['э', 'е']), frozenset(['б', 'п']),
        frozenset(['в', 'ф']), frozenset(['г', 'к', 'х']),
        frozenset(['д', 'т']), frozenset(['ж', 'ш', 'щ', 'ч']),
        frozenset(['з', 'с', 'ц']), frozenset(['л', 'р']),
        frozenset(['м', 'н']),
    }

    # ========== ИНИЦИАЛИЗАЦИЯ ==========

    def __init__(self, food_database: List[Dict[str, Any]], api_client=None):
        """
        Инициализация матчера.
        
        Args:
            food_database: список продуктов в формате [{"name": "...", ...}, ...]
            api_client: клиент для внешнего API (опционально)
        """
        self.database = food_database
        self.api_client = api_client

        # Инициализация pymorphy2 (лемматизатор для русского)
        self.morph = None
        if HAS_PYMORPHY:
            try:
                self.morph = pymorphy2.MorphAnalyzer()
                logger.info("pymorphy2 инициализирован успешно")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать pymorphy2: {e}")

        # Кэши
        self._cache: OrderedDict[str, List[MatchResult]] = OrderedDict()
        self._cache_max_size = 100
        self._lemma_cache: Dict[str, str] = {}

        # Базовые индексы (с db_index для быстрого доступа)
        self.by_length: Dict[int, List[Tuple[str, Dict, int]]] = {}
        self.by_first_letter: Dict[str, List[Tuple[str, Dict, int]]] = {}
        self.word_index: Dict[str, Set[int]] = {}
        self.by_lemma: Dict[str, List[Tuple[str, Dict, int]]] = {}
        self.phonetic_index: Dict[str, List[Tuple[str, Dict, int]]] = {}

        # Новые индексы для улучшенного поиска
        self.trigram_index: Dict[str, Set[int]] = {}
        self.prefix_index: Dict[str, List[int]] = {}

        # BM25-индексы
        self.doc_lengths: List[int] = []
        self.avg_doc_length: float = 0
        self.df: Counter = Counter()

        # Счётчик продуктов в БД
        self._db_size: int = 0

        # Строим все индексы один раз при старте
        self._build_all_indexes()

    # ========== ПОСТРОЕНИЕ ИНДЕКСОВ ==========

    def _build_all_indexes(self):
        """Строит все индексы при инициализации."""
        self._db_size = len(self.database)
        self._build_basic_indexes()
        self._build_trigram_index()
        self._build_prefix_index()
        self._build_bm25_index()

    def _build_basic_indexes(self):
        """Строит базовые индексы (длина, первая буква, леммы, слова, фонетика)."""
        # ✅ Очищаем индексы перед перестройкой
        self.by_length.clear()
        self.by_first_letter.clear()
        self.word_index.clear()
        self.by_lemma.clear()
        self.phonetic_index.clear()

        for idx, food in enumerate(self.database):
            name = self._normalize(food["name"])
            lemma_name = self._lemmatize_text(name)

            # Индекс по длине (оригинал + лемма)
            for n in [name, lemma_name]:
                length = len(n)
                if length not in self.by_length:
                    self.by_length[length] = []
                self.by_length[length].append((n, food, idx))

            # Индекс по лемме
            if lemma_name not in self.by_lemma:
                self.by_lemma[lemma_name] = []
            self.by_lemma[lemma_name].append((name, food, idx))

            # Индекс по первой букве
            if name:
                first_letter = name[0]
                if first_letter not in self.by_first_letter:
                    self.by_first_letter[first_letter] = []
                self.by_first_letter[first_letter].append((name, food, idx))

            # Индекс слов (с лемматизацией, без стоп-слов)
            words = lemma_name.split()
            for word in words:
                if len(word) >= 3 and word not in self.GRAMMATICAL_STOP_WORDS:
                    if word not in self.word_index:
                        self.word_index[word] = set()
                    self.word_index[word].add(idx)

            # Фонетический индекс
            phonetic_hash = self._russian_metaphone(lemma_name)
            if phonetic_hash:
                if phonetic_hash not in self.phonetic_index:
                    self.phonetic_index[phonetic_hash] = []
                self.phonetic_index[phonetic_hash].append((name, food, idx))

    def _build_trigram_index(self):
        """Строит trigram-индекс для быстрого fuzzy поиска."""
        self.trigram_index.clear()
        for idx, food in enumerate(self.database):
            name = self._normalize(food["name"])
            for trigram in self._get_trigrams(name):
                if trigram not in self.trigram_index:
                    self.trigram_index[trigram] = set()
                self.trigram_index[trigram].add(idx)

    def _build_prefix_index(self):
        """Строит индекс префиксов для автокомплита."""
        self.prefix_index.clear()
        for idx, food in enumerate(self.database):
            name = self._normalize(food["name"])
            for word in name.split():
                for length in range(2, len(word) + 1):
                    prefix = word[:length]
                    if prefix not in self.prefix_index:
                        self.prefix_index[prefix] = []
                    if idx not in self.prefix_index[prefix]:
                        self.prefix_index[prefix].append(idx)

    def _build_bm25_index(self):
        """Строит BM25-индекс для ранжирования результатов."""
        self.doc_lengths.clear()
        self.df.clear()

        if not self.database:
            self.avg_doc_length = 1
            return

        for food in self.database:
            words = self._tokenize_culinary(food["name"])
            self.doc_lengths.append(len(words))
            for word in set(words):
                self.df[word] += 1

        self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths)

    def _add_to_indexes(self, food: Dict[str, Any], idx: int):
        """
        Инкрементальное добавление одного продукта в индексы.
        Используется при добавлении результатов из API без полной перестройки.
        """
        name = self._normalize(food["name"])
        lemma_name = self._lemmatize_text(name)

        # Базовые индексы
        for n in [name, lemma_name]:
            length = len(n)
            if length not in self.by_length:
                self.by_length[length] = []
            self.by_length[length].append((n, food, idx))

        if lemma_name not in self.by_lemma:
            self.by_lemma[lemma_name] = []
        self.by_lemma[lemma_name].append((name, food, idx))

        if name:
            first_letter = name[0]
            if first_letter not in self.by_first_letter:
                self.by_first_letter[first_letter] = []
            self.by_first_letter[first_letter].append((name, food, idx))

        # Индекс слов
        words = lemma_name.split()
        for word in words:
            if len(word) >= 3 and word not in self.GRAMMATICAL_STOP_WORDS:
                if word not in self.word_index:
                    self.word_index[word] = set()
                self.word_index[word].add(idx)

        # ✅ Фонетический индекс
        phonetic_hash = self._russian_metaphone(lemma_name)
        if phonetic_hash:
            if phonetic_hash not in self.phonetic_index:
                self.phonetic_index[phonetic_hash] = []
            self.phonetic_index[phonetic_hash].append((name, food, idx))

        # Trigrams
        for trigram in self._get_trigrams(name):
            if trigram not in self.trigram_index:
                self.trigram_index[trigram] = set()
            self.trigram_index[trigram].add(idx)

        # Prefixes
        for word in name.split():
            for length in range(2, len(word) + 1):
                prefix = word[:length]
                if prefix not in self.prefix_index:
                    self.prefix_index[prefix] = []
                if idx not in self.prefix_index[prefix]:
                    self.prefix_index[prefix].append(idx)

        # BM25
        words_culinary = self._tokenize_culinary(food["name"])
        self.doc_lengths.append(len(words_culinary))
        for word in set(words_culinary):
            self.df[word] += 1

        # Пересчитываем среднюю длину
        self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths)
        self._db_size += 1

    # ========== ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ==========

    def _get_trigrams(self, text: str) -> Set[str]:
        """Извлекает все trigrams (последовательности из 3 символов) из текста."""
        text = f"  {text}  "  # Добавляем пробелы для границ слов
        return {text[i:i+3] for i in range(len(text) - 2)}

    def _normalize(self, text: str) -> str:
        """Нормализует текст: нижний регистр, удаление лишних пробелов."""
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)
        return text

    def _lemmatize(self, word: str) -> str:
        """Приводит слово к нормальной форме (лемматизация через pymorphy2)."""
        if not self.morph:
            return word
        if word in self._lemma_cache:
            return self._lemma_cache[word]
        try:
            parsed = self.morph.parse(word)
            if parsed:
                lemma = parsed[0].normal_form
                self._lemma_cache[word] = lemma
                return lemma
        except Exception:
            pass
        return word

    def _lemmatize_text(self, text: str) -> str:
        """Лемматизирует весь текст."""
        words = text.split()
        lemmatized_words = []
        for word in words:
            if len(word) <= 2 or word in self.GRAMMATICAL_STOP_WORDS:
                lemmatized_words.append(word.lower())
            else:
                lemmatized_words.append(self._lemmatize(word.lower()))
        return ' '.join(lemmatized_words)

    def _tokenize_culinary(self, text: str) -> List[str]:
        """
        Умная токенизация с учётом кулинарных модификаторов.
        
        Пример:
            "кофе с молоком" → ["кофе", "с_молоком"]
            "салат без майонеза" → ["салат", "без_майонеза"]
        """
        words = self._lemmatize_text(text).split()
        tokens = []
        skip_next = False

        for i, word in enumerate(words):
            if skip_next:
                skip_next = False
                continue

            if word in self.GRAMMATICAL_STOP_WORDS:
                continue

            # ✅ Кулинарный модификатор + следующее слово = биграмма
            if word in self.CULINARY_MODIFIERS and i + 1 < len(words):
                next_word = words[i + 1]
                if next_word not in self.GRAMMATICAL_STOP_WORDS:
                    tokens.append(f"{word}_{next_word}")
                    skip_next = True
                    continue

            if len(word) >= 2:
                tokens.append(word)

        return tokens

    def _russian_metaphone(self, word: str) -> str:
        """Упрощённый фонетический хеш для русского языка."""
        result = []
        prev_char = ''
        for char in word.lower():
            if char in self.RUSSIAN_SOUNDEX_MAP:
                mapped = self.RUSSIAN_SOUNDEX_MAP[char]
                if mapped and mapped != prev_char:
                    # Упрощаем по фонетическим группам
                    for group in self.PHONETIC_GROUPS:
                        if char in group:
                            mapped = ''.join(sorted(group))[0].upper()
                            break
                    result.append(mapped)
                    prev_char = mapped
        return ''.join(result[:4])

    def _token_set_ratio(self, s1: str, s2: str) -> float:
        """
        Сравнивает множества слов, игнорируя порядок и повторы.
        
        Пример: "гречка с котлетой" == "котлета с гречкой" → 1.0
        """
        tokens1 = set(self._tokenize_culinary(s1))
        tokens2 = set(self._tokenize_culinary(s2))
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        return len(intersection) / len(union) if union else 0.0

    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """Вычисляет расстояние Левенштейна."""
        if HAS_LEVENSHTEIN:
            return Levenshtein.distance(s1, s2)
        # Fallback реализация
        if len(s1) < len(s2):
            s1, s2 = s2, s1
        if len(s2) == 0:
            return len(s1)
        previous_row = list(range(len(s2) + 1))
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        return previous_row[-1]

    def _calculate_bm25_score(self, query_words: List[str], food_idx: int) -> float:
        """
        Рассчитывает BM25-скор для блюда.
        
        BM25 учитывает:
        - Частоту слова в документе (TF)
        - Редкость слова в корпусе (IDF)
        - Длину документа
        """
        # ✅ Защита от пустой БД и деления на ноль
        if food_idx < 0 or food_idx >= len(self.doc_lengths) or not self.database:
            return 0.0
        if self.avg_doc_length == 0:
            return 0.0

        k1, b = 1.5, 0.75
        N = len(self.database)
        score = 0.0
        doc_length = self.doc_lengths[food_idx]
        food_words = self._tokenize_culinary(self.database[food_idx]["name"])
        word_counts = Counter(food_words)

        for word in query_words:
            if word not in word_counts:
                continue
            tf = word_counts[word]
            df = self.df.get(word, 0)
            idf = math.log((N - df + 0.5) / (df + 0.5) + 1)
            tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_length / self.avg_doc_length))
            score += idf * tf_norm

        return score

    # ========== СТРАТЕГИИ ПОИСКА ==========

    def _search_exact(self, query: str) -> List[MatchResult]:
        """Точный поиск (полное совпадение)."""
        query = self._normalize(query)
        results = []
        for length in [len(query)]:
            if length not in self.by_length:
                continue
            for db_name, food, idx in self.by_length[length]:
                if db_name == query:
                    results.append(MatchResult(
                        food=food, strategy=MatchStrategy.EXACT,
                        confidence=1.0, distance=0,
                        matched_words=[query], db_index=idx,
                    ))
        return results

    def _search_normalized(self, query: str) -> List[MatchResult]:
        """Поиск по лемматизированной форме."""
        query = self._normalize(query)
        lemma_query = self._lemmatize_text(query)
        results = []
        if lemma_query in self.by_lemma:
            for db_name, food, idx in self.by_lemma[lemma_query]:
                results.append(MatchResult(
                    food=food, strategy=MatchStrategy.NORMALIZED,
                    confidence=0.98, distance=0,
                    matched_words=[lemma_query], db_index=idx,
                ))
        return results

    def _search_prefix(self, query: str) -> List[MatchResult]:
        """Префиксный поиск (автокомплит)."""
        query = self._normalize(query)
        query_words = query.split()
        if not query_words:
            return []
        last_word = query_words[-1]
        if len(last_word) < 2:
            return []

        candidate_indices = self.prefix_index.get(last_word, [])
        results = []
        for idx in candidate_indices[:10]:
            food = self.database[idx]
            results.append(MatchResult(
                food=food, strategy=MatchStrategy.PREFIX,
                confidence=0.95, distance=0,
                matched_words=[last_word], db_index=idx,
            ))
        return results[:5]

    def _search_compound(self, query: str) -> List[MatchResult]:
        """Поиск составных блюд через Token Set Ratio."""
        query_tokens = set(self._tokenize_culinary(query))
        if len(query_tokens) < 2:
            return []

        results = []
        for idx, food in enumerate(self.database):
            food_tokens = set(self._tokenize_culinary(food["name"]))
            if not query_tokens or not food_tokens:
                continue
            intersection = query_tokens & food_tokens
            min_len = min(len(query_tokens), len(food_tokens))
            if len(intersection) >= min_len * 0.5:
                ratio = self._token_set_ratio(query, food["name"])
                if ratio >= 0.6:
                    results.append(MatchResult(
                        food=food, strategy=MatchStrategy.PARTIAL,
                        confidence=ratio,
                        distance=int((1 - ratio) * 10),
                        matched_words=list(intersection), db_index=idx,
                    ))

        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:5]

    def _search_synonyms(self, query: str) -> List[MatchResult]:
        """Поиск через синонимы с весами."""
        query = self._normalize(query)
        lemma_query = self._lemmatize_text(query)
        results = []
        words = self._tokenize_culinary(query)
        lemma_words = self._tokenize_culinary(lemma_query)
        all_words = list(set(words + lemma_words))

        synonym_variants = []
        for word in all_words:
            if word in self.SYNONYMS:
                for syn, weight in self.SYNONYMS[word]:
                    synonym_variants.append((query.replace(word, syn), weight))
                    synonym_variants.append((lemma_query.replace(word, syn), weight))

        for variant, weight in synonym_variants:
            variant_normalized = self._normalize(variant)
            for length in [len(variant_normalized)]:
                if length not in self.by_length:
                    continue
                for db_name, food, idx in self.by_length[length]:
                    if db_name == variant_normalized:
                        results.append(MatchResult(
                            food=food, strategy=MatchStrategy.SYNONYM,
                            confidence=weight, distance=0,
                            matched_words=[variant], db_index=idx,
                        ))
            lemma_variant = self._lemmatize_text(variant_normalized)
            if lemma_variant in self.by_lemma:
                for db_name, food, idx in self.by_lemma[lemma_variant]:
                    results.append(MatchResult(
                        food=food, strategy=MatchStrategy.SYNONYM,
                        confidence=weight * 0.95, distance=0,
                        matched_words=[lemma_variant], db_index=idx,
                    ))
        return results

    def _search_trigram(self, query: str, threshold: float = 0.4) -> List[MatchResult]:
        """Быстрый fuzzy поиск через trigrams (Jaccard similarity)."""
        query_trigrams = self._get_trigrams(query)
        if not query_trigrams:
            return []

        candidate_scores: Dict[int, int] = {}
        for trigram in query_trigrams:
            for idx in self.trigram_index.get(trigram, set()):
                candidate_scores[idx] = candidate_scores.get(idx, 0) + 1

        results = []
        for idx, intersection in candidate_scores.items():
            food = self.database[idx]
            food_trigrams = self._get_trigrams(self._normalize(food["name"]))
            union = len(query_trigrams) + len(food_trigrams) - intersection
            if union == 0:
                continue
            similarity = intersection / union
            if similarity >= threshold:
                results.append(MatchResult(
                    food=food, strategy=MatchStrategy.TRIGRAM,
                    confidence=similarity,
                    distance=int((1 - similarity) * 10),
                    matched_words=[food["name"]], db_index=idx,
                ))

        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:5]

    def _search_phonetic(self, query: str) -> List[MatchResult]:
        """Фонетический поиск (для опечаток типа "корова" → "карова")."""
        query = self._normalize(query)
        lemma_query = self._lemmatize_text(query)
        results = []
        for search_query in [query, lemma_query]:
            query_hash = self._russian_metaphone(search_query)
            if not query_hash:
                continue
            candidates = self.phonetic_index.get(query_hash, [])
            for db_name, food, idx in candidates:
                if abs(len(search_query) - len(db_name)) <= 3:
                    distance = self._levenshtein_distance(search_query, db_name)
                    max_len = max(len(search_query), len(db_name))
                    confidence = (1.0 - distance / max_len) * 0.7
                    confidence = max(0.0, min(1.0, confidence))
                    results.append(MatchResult(
                        food=food, strategy=MatchStrategy.PHONETIC,
                        confidence=confidence, distance=distance,
                        matched_words=[db_name], db_index=idx,
                    ))
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:5]

    # ========== ОСНОВНОЙ ПОИСК ==========

    def search(self, user_input: str, use_api: bool = True) -> List[MatchResult]:
        """
        Основной метод поиска. Пробует все стратегии и возвращает лучшие результаты.
        
        Порядок стратегий:
        1. Точное совпадение
        2. Нормализованное (лемматизация)
        3. Префиксный поиск
        4. Составные блюда (Token Set)
        5. Синонимы
        6. Trigram fuzzy
        7. Фонетический
        """
        user_input = self._normalize(user_input)

        # Проверяем кэш
        cache_key = f"{user_input}:{use_api}"
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]

        all_results: List[MatchResult] = []
        seen_indices: Set[int] = set()  # ✅ Используем db_index вместо id(food)

        strategies = [
            self._search_exact,
            self._search_normalized,
            self._search_prefix,
            self._search_compound,
            self._search_synonyms,
            self._search_trigram,
            self._search_phonetic,
        ]

        for strategy_func in strategies:
            results = strategy_func(user_input)
            for r in results:
                if r.db_index not in seen_indices:
                    seen_indices.add(r.db_index)
                    all_results.append(r)

        # ✅ BM25-ранжирование с нормализацией
        if len(all_results) > 1:
            query_words = self._tokenize_culinary(user_input)
            for result in all_results:
                if result.db_index >= 0:
                    bm25_score = self._calculate_bm25_score(query_words, result.db_index)
                    # Нормализуем BM25 в диапазон [0, 1]
                    normalized_bm25 = min(1.0, bm25_score / 5.0)
                    # ✅ Комбинируем: 60% confidence + 40% BM25
                    result.confidence = 0.6 * result.confidence + 0.4 * normalized_bm25

        # Сортировка по уверенности и приоритету стратегии
        strategy_order = {
            MatchStrategy.EXACT: 0, MatchStrategy.NORMALIZED: 1,
            MatchStrategy.PREFIX: 2, MatchStrategy.PARTIAL: 3,
            MatchStrategy.SYNONYM: 4, MatchStrategy.TRIGRAM: 5,
            MatchStrategy.PHONETIC: 6,
        }
        all_results.sort(key=lambda x: (-x.confidence, strategy_order.get(x.strategy, 10)))

        # Сохраняем в кэш
        self._cache[cache_key] = all_results[:10]
        if len(self._cache) > self._cache_max_size:
            self._cache.popitem(last=False)

        return all_results[:5]

    async def search_with_api_fallback(self, user_input: str) -> List[Dict[str, Any]]:
        """
        Поиск с fallback на внешнее API (Open Food Facts).
        
        Если локальный поиск дал хороший результат (confidence >= 0.7),
        API не вызывается. Иначе — запрос к API и инкрементальное добавление
        найденных продуктов в локальную базу.
        """
        local_results = self.search(user_input, use_api=False)
        if local_results and local_results[0].confidence >= 0.7:
            return [r.food for r in local_results if r.confidence >= 0.5]

        if self.api_client:
            try:
                api_results = await self.api_client.search_products(user_input)
                # ✅ Инкрементальное добавление (без полной перестройки индексов)
                for food in api_results[:3]:
                    if food not in self.database:
                        new_idx = len(self.database)
                        self.database.append(food)
                        self._add_to_indexes(food, new_idx)
                if api_results:
                    return api_results[:5]
            except Exception as e:
                logger.warning(f"API search failed: {e}")

        return [r.food for r in local_results[:5]]

    def get_best_match(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Возвращает лучший результат или None."""
        results = self.search(user_input)
        if results and results[0].confidence >= 0.5:
            return results[0].food
        return None

    def parse_quantity_from_text(self, text: str) -> Tuple[str, Optional[float], Optional[str]]:
        """
        Извлекает количество из текста.
        
        Returns:
            Tuple[str, Optional[float], Optional[str]]:
            (название_блюда, множитель, единица_измерения)
        
        Examples:
            "гречка 300"          → ("гречка", 300.0, "г")
            "банан 2 шт"          → ("банан", 2.0, "шт")
            "молоко 500мл"        → ("молоко", 500.0, "мл")
            "два яйца"            → ("яйца", 2.0, "шт")
            "1.5 кг курицы"       → ("курицы", 1500.0, "г")
            "полтора банана"      → ("банана", 1.5, "шт")
        """
        text = text.strip().lower()
        multiplier = None
        unit = None
        original_text = text

        # ✅ Паттерн 1: Число + явная единица ("300г", "2 шт", "500мл")
        match = re.search(
            r'(\d+(?:[.,]\d+)?)\s*(г|гр|g|gr|кг|kg|мл|ml|л|l|шт|штук|кусок|куска|порц|порции)\b',
            text
        )
        if match:
            multiplier = float(match.group(1).replace(',', '.'))
            raw_unit = match.group(2)

            # Нормализуем единицы
            if raw_unit in ('г', 'гр', 'g', 'gr'):
                unit = 'г'
            elif raw_unit in ('кг', 'kg'):
                unit = 'г'
                multiplier *= 1000  # переводим кг в граммы
            elif raw_unit in ('мл', 'ml'):
                unit = 'мл'
            elif raw_unit in ('л', 'l'):
                unit = 'мл'
                multiplier *= 1000  # переводим литры в мл
            elif raw_unit in ('шт', 'штук', 'кусок', 'куска', 'порц', 'порции'):
                unit = 'шт'

            # Удаляем число и единицу из текста + нормализуем пробелы
            text = re.sub(
                r'\d+(?:[.,]\d+)?\s*(?:г|гр|g|gr|кг|kg|мл|ml|л|l|шт|штук|кусок|куска|порц|порции)\b',
                '', text
            )
            text = re.sub(r'\s+', ' ', text).strip()
            return (text if text else original_text, multiplier, unit)

        # ✅ Паттерн 2: Просто число в конце ("гречка 300") — считаем граммами
        match = re.search(r'(\d+(?:[.,]\d+)?)\s*$', text)
        if match:
            multiplier = float(match.group(1).replace(',', '.'))
            unit = 'г'
            text = text[:match.start()].strip()
            return (text if text else original_text, multiplier, unit)

        # ✅ Паттерн 3: Словесное число ("два яйца", "полтора банана")
        for word, num in self.NUMBER_WORDS.items():
            if word in text:
                multiplier = num
                unit = 'шт'
                text = text.replace(word, '').strip()
                text = re.sub(r'\s+', ' ', text).strip()
                return (text if text else original_text, multiplier, unit)

        return original_text, None, None


class SyncFoodMatcher:
    """Синхронная обёртка для OptimizedFoodMatcher (для удобства использования вне async)."""

    def __init__(self, food_database: List[Dict[str, Any]], api_client=None):
        self._matcher = OptimizedFoodMatcher(food_database, api_client)

    def search(self, user_input: str) -> List[Dict[str, Any]]:
        """Синхронный поиск."""
        results = self._matcher.search(user_input, use_api=False)
        return [r.food for r in results]

    def get_best_match(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Синхронное получение лучшего совпадения."""
        return self._matcher.get_best_match(user_input)

    def parse_quantity_from_text(self, text: str) -> Tuple[str, Optional[float], Optional[str]]:
        """Синхронный парсинг количества из текста."""
        return self._matcher.parse_quantity_from_text(text)