# handlers/add_food/food_matcher.py
import re
import asyncio
from typing import Optional, List, Dict, Any, Tuple, Set
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum

# Внешние зависимости
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
    NORMALIZED = "normalized"  # После лемматизации
    SYNONYM = "synonym"        # Через синоним
    TYPO = "typo"              # Исправление опечатки
    PHONETIC = "phonetic"      # Фонетическое сходство
    PARTIAL = "partial"        # Частичное совпадение
    API = "api"                # Через внешнее API


@dataclass
class MatchResult:
    """Результат поиска."""
    food: Dict[str, Any]
    strategy: MatchStrategy
    confidence: float  # 0.0 - 1.0
    distance: int = 0
    matched_words: List[str] = field(default_factory=list)
    
    def __repr__(self):
        return f"MatchResult({self.food['name']}, {self.strategy.value}, {self.confidence:.2f})"


class OptimizedFoodMatcher:
    """
    Улучшенный матчер продуктов с поддержкой:
    - Лемматизации через pymorphy2 (приведение к нормальной форме)
    - Адаптивного алгоритма Левенштейна/Дамерау-Левенштейна
    - Синонимов с весами
    - Разбиения составных запросов
    - Фонетического поиска (Metaphone для русского)
    - Кэширования результатов
    - Интеграции с внешним API
    """
    
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
    
    # Опасные пары для коротких слов
    DANGEROUS_PAIRS: Set[Tuple[str, str]] = {
        ('рис', 'сир'), ('рис', 'суп'), ('сыр', 'сир'),
        ('сок', 'кот'), ('чай', 'щай'), ('сало', 'сила'),
        ('лук', 'сук'), ('жир', 'мир'), ('шок', 'сок'),
        ('суп', 'зуб'), ('кот', 'ток'), ('сон', 'нос'),
    }
    
    # Стоп-слова, которые игнорируем при поиске
    STOP_WORDS: Set[str] = {
        'с', 'без', 'под', 'над', 'в', 'на', 'и', 'или',
        'из', 'от', 'до', 'для', 'к', 'по', 'при',
        'а', 'но', 'да', 'же', 'бы', 'ли', 'то',
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
        frozenset(['а', 'я']),
        frozenset(['о', 'ё']),
        frozenset(['у', 'ю']),
        frozenset(['ы', 'и']),
        frozenset(['э', 'е']),
        frozenset(['б', 'п']),
        frozenset(['в', 'ф']),
        frozenset(['г', 'к', 'х']),
        frozenset(['д', 'т']),
        frozenset(['ж', 'ш', 'щ', 'ч']),
        frozenset(['з', 'с', 'ц']),
        frozenset(['л', 'р']),
        frozenset(['м', 'н']),
    }
    
    def __init__(self, food_database: List[Dict[str, Any]], api_client=None):
        """
        Инициализация матчера.
        
        Args:
            food_database: список продуктов в формате [{"name": "...", ...}, ...]
            api_client: клиент для внешнего API (опционально)
        """
        self.database = food_database
        self.api_client = api_client
        
        # Инициализация pymorphy2
        self.morph = None
        if HAS_PYMORPHY:
            try:
                self.morph = pymorphy2.MorphAnalyzer()
                logger.info("pymorphy2 инициализирован успешно")
            except Exception as e:
                logger.warning(f"Не удалось инициализировать pymorphy2: {e}")
        
        # Кэш результатов поиска (LRU)
        self._cache: OrderedDict[str, List[MatchResult]] = OrderedDict()
        self._cache_max_size = 100
        
        # Кэш лемматизации
        self._lemma_cache: Dict[str, str] = {}
        
        # Группировка по длине нормализованного названия
        self.by_length: Dict[int, List[Tuple[str, Dict]]] = {}
        
        # Индекс по первым буквам для быстрого поиска
        self.by_first_letter: Dict[str, List[Tuple[str, Dict]]] = {}
        
        # Индекс слов для частичного поиска (с лемматизацией)
        self.word_index: Dict[str, Set[int]] = {}
        
        # Индекс лемматизированных названий
        self.by_lemma: Dict[str, List[Tuple[str, Dict]]] = {}
        
        # Фонетические хеши
        self.phonetic_index: Dict[str, List[Tuple[str, Dict]]] = {}
        
        self._build_indexes()
    
    def _lemmatize(self, word: str) -> str:
        """
        Приводит слово к нормальной форме (лемматизация).
        Например: "яблоки" -> "яблоко", "ел" -> "есть"
        """
        if not self.morph:
            return word
        
        # Проверяем кэш
        if word in self._lemma_cache:
            return self._lemma_cache[word]
        
        try:
            # Получаем нормальную форму
            parsed = self.morph.parse(word)
            if parsed:
                # Берём самый вероятный вариант
                lemma = parsed[0].normal_form
                self._lemma_cache[word] = lemma
                return lemma
        except Exception:
            pass
        
        return word
    
    def _lemmatize_text(self, text: str) -> str:
        """
        Лемматизирует весь текст, приводя каждое слово к нормальной форме.
        """
        words = text.split()
        lemmatized_words = []
        
        for word in words:
            # Не лемматизируем короткие слова и стоп-слова
            if len(word) <= 2 or word.lower() in self.STOP_WORDS:
                lemmatized_words.append(word.lower())
            else:
                lemmatized_words.append(self._lemmatize(word.lower()))
        
        return ' '.join(lemmatized_words)
    
    def _build_indexes(self):
        """Строит все индексы для быстрого поиска."""
        for idx, food in enumerate(self.database):
            name = self._normalize(food["name"])
            
            # Лемматизированное название
            lemma_name = self._lemmatize_text(name)
            
            # Индекс по длине (используем оригинальное и лемматизированное)
            for n in [name, lemma_name]:
                length = len(n)
                if length not in self.by_length:
                    self.by_length[length] = []
                self.by_length[length].append((n, food))
            
            # Индекс по лемме
            if lemma_name not in self.by_lemma:
                self.by_lemma[lemma_name] = []
            self.by_lemma[lemma_name].append((name, food))
            
            # Индекс по первой букве
            if name:
                first_letter = name[0]
                if first_letter not in self.by_first_letter:
                    self.by_first_letter[first_letter] = []
                self.by_first_letter[first_letter].append((name, food))
            
            # Индекс слов (с лемматизацией)
            words = lemma_name.split()
            for word in words:
                if len(word) >= 3 and word not in self.STOP_WORDS:
                    if word not in self.word_index:
                        self.word_index[word] = set()
                    self.word_index[word].add(idx)
            
            # Фонетический индекс (используем лемматизированное название)
            phonetic_hash = self._russian_metaphone(lemma_name)
            if phonetic_hash:
                if phonetic_hash not in self.phonetic_index:
                    self.phonetic_index[phonetic_hash] = []
                self.phonetic_index[phonetic_hash].append((name, food))
    
    def _normalize(self, text: str) -> str:
        """Нормализует текст: нижний регистр, удаление лишних пробелов."""
        text = text.lower().strip()
        text = re.sub(r'\s+', ' ', text)
        return text
    
    def _tokenize(self, text: str) -> List[str]:
        """Разбивает текст на значимые слова с лемматизацией."""
        text = self._lemmatize_text(text)
        words = text.split()
        return [w for w in words if w not in self.STOP_WORDS and len(w) >= 2]
    
    def _russian_metaphone(self, word: str) -> str:
        """
        Упрощённый фонетический хеш для русского языка.
        Учитывает фонетические группы букв.
        """
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
        
        return ''.join(result[:4])  # Берём первые 4 символа
    
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
    
    def _damerau_levenshtein_distance(self, s1: str, s2: str) -> int:
        """Вычисляет расстояние Дамерау-Левенштейна."""
        if HAS_LEVENSHTEIN:
            return int((1 - Levenshtein.ratio(s1, s2)) * max(len(s1), len(s2)))
        
        # Fallback реализация
        d = {}
        lenstr1, lenstr2 = len(s1), len(s2)
        
        for i in range(-1, lenstr1 + 1):
            d[(i, -1)] = i + 1
        for j in range(-1, lenstr2 + 1):
            d[(-1, j)] = j + 1
        
        for i in range(lenstr1):
            for j in range(lenstr2):
                cost = 0 if s1[i] == s2[j] else 1
                d[(i, j)] = min(
                    d[(i - 1, j)] + 1,
                    d[(i, j - 1)] + 1,
                    d[(i - 1, j - 1)] + cost,
                )
                if i and j and s1[i] == s2[j - 1] and s1[i - 1] == s2[j]:
                    d[(i, j)] = min(d[(i, j)], d[(i - 2, j - 2)] + 1)
        
        return d[(lenstr1 - 1, lenstr2 - 1)]
    
    def _calculate_distance(self, s1: str, s2: str) -> int:
        """
        Адаптивно выбирает алгоритм в зависимости от длины слов.
        """
        len1, len2 = len(s1), len(s2)
        
        # Очень короткие слова (2-4 буквы) — только Левенштейн
        if len1 <= 4 and len2 <= 4:
            return self._levenshtein_distance(s1, s2)
        
        # Длинные слова (6+ букв) — Дамерау-Левенштейн (учитывает транспозиции)
        if len1 >= 6 and len2 >= 6:
            return self._damerau_levenshtein_distance(s1, s2)
        
        # Средние — комбинируем
        lev = self._levenshtein_distance(s1, s2)
        dam = self._damerau_levenshtein_distance(s1, s2)
        
        # Проверяем опасные пары
        if dam < lev:
            pair = tuple(sorted([s1, s2]))
            if pair in self.DANGEROUS_PAIRS:
                return lev
        
        return min(lev, dam)
    
    def _calculate_confidence(self, distance: int, max_len: int, strategy: MatchStrategy) -> float:
        """
        Вычисляет уверенность в совпадении (0.0 - 1.0).
        """
        # Базовая уверенность от расстояния
        base_confidence = 1.0 - (distance / max(1, max_len))
        base_confidence = max(0.0, min(1.0, base_confidence))
        
        # Модификаторы по стратегии
        modifiers = {
            MatchStrategy.EXACT: 1.0,
            MatchStrategy.NORMALIZED: 0.98,
            MatchStrategy.SYNONYM: 0.95,
            MatchStrategy.TYPO: 0.85,
            MatchStrategy.PHONETIC: 0.7,
            MatchStrategy.PARTIAL: 0.6,
            MatchStrategy.API: 0.8,
        }
        
        return base_confidence * modifiers.get(strategy, 0.5)
    
    def _search_exact(self, query: str) -> List[MatchResult]:
        """Точный поиск."""
        query = self._normalize(query)
        results = []
        
        for length in [len(query)]:
            if length not in self.by_length:
                continue
            for db_name, food in self.by_length[length]:
                if db_name == query:
                    results.append(MatchResult(
                        food=food,
                        strategy=MatchStrategy.EXACT,
                        confidence=1.0,
                        distance=0,
                        matched_words=[query]
                    ))
        
        return results
    
    def _search_normalized(self, query: str) -> List[MatchResult]:
        """Поиск по лемматизированной форме."""
        query = self._normalize(query)
        lemma_query = self._lemmatize_text(query)
        results = []
        
        if lemma_query in self.by_lemma:
            for db_name, food in self.by_lemma[lemma_query]:
                results.append(MatchResult(
                    food=food,
                    strategy=MatchStrategy.NORMALIZED,
                    confidence=0.98,
                    distance=0,
                    matched_words=[lemma_query]
                ))
        
        return results
    
    def _search_synonyms(self, query: str) -> List[MatchResult]:
        """Поиск через синонимы."""
        query = self._normalize(query)
        lemma_query = self._lemmatize_text(query)
        results = []
        
        # Проверяем синонимы для каждого слова
        words = self._tokenize(query)
        lemma_words = self._tokenize(lemma_query)
        all_words = list(set(words + lemma_words))
        
        synonym_variants = []
        
        for word in all_words:
            if word in self.SYNONYMS:
                for syn, weight in self.SYNONYMS[word]:
                    variant = query.replace(word, syn)
                    synonym_variants.append((variant, weight))
                    # Также пробуем лемматизированный вариант
                    lemma_variant = lemma_query.replace(word, syn)
                    synonym_variants.append((lemma_variant, weight))
        
        for variant, weight in synonym_variants:
            variant_normalized = self._normalize(variant)
            
            # Ищем точное совпадение
            for length in [len(variant_normalized)]:
                if length not in self.by_length:
                    continue
                for db_name, food in self.by_length[length]:
                    if db_name == variant_normalized:
                        results.append(MatchResult(
                            food=food,
                            strategy=MatchStrategy.SYNONYM,
                            confidence=weight,
                            distance=0,
                            matched_words=[variant]
                        ))
            
            # Ищем по лемме
            lemma_variant = self._lemmatize_text(variant_normalized)
            if lemma_variant in self.by_lemma:
                for db_name, food in self.by_lemma[lemma_variant]:
                    results.append(MatchResult(
                        food=food,
                        strategy=MatchStrategy.SYNONYM,
                        confidence=weight * 0.95,
                        distance=0,
                        matched_words=[lemma_variant]
                    ))
        
        return results
    
    def _search_typo(self, query: str, max_distance: int = 2) -> List[MatchResult]:
        """Поиск с исправлением опечаток."""
        query = self._normalize(query)
        lemma_query = self._lemmatize_text(query)
        results = []
        
        # Ищем по обоим вариантам
        for search_query in [query, lemma_query]:
            query_len = len(search_query)
            
            # Определяем диапазон длин
            min_len = max(2, query_len - 2)
            max_len = query_len + 2
            
            # Оптимизация: ищем только среди слов, начинающихся с той же буквы
            first_letter = search_query[0] if search_query else ''
            candidates = self.by_first_letter.get(first_letter, [])
            
            # Если по первой букве мало, расширяем поиск
            if len(candidates) < 5:
                for length in range(min_len, max_len + 1):
                    if length in self.by_length:
                        candidates.extend(self.by_length[length])
            
            for db_name, food in candidates:
                db_len = len(db_name)
                if db_len < min_len or db_len > max_len:
                    continue
                
                distance = self._calculate_distance(search_query, db_name)
                
                if distance <= max_distance:
                    confidence = self._calculate_confidence(
                        distance,
                        max(query_len, db_len),
                        MatchStrategy.TYPO
                    )
                    results.append(MatchResult(
                        food=food,
                        strategy=MatchStrategy.TYPO,
                        confidence=confidence,
                        distance=distance,
                        matched_words=[db_name]
                    ))
        
        # Убираем дубликаты и сортируем
        seen = set()
        unique_results = []
        for r in sorted(results, key=lambda x: x.confidence, reverse=True):
            food_id = id(r.food)
            if food_id not in seen:
                seen.add(food_id)
                unique_results.append(r)
        
        return unique_results[:5]
    
    def _search_phonetic(self, query: str) -> List[MatchResult]:
        """Фонетический поиск."""
        query = self._normalize(query)
        lemma_query = self._lemmatize_text(query)
        results = []
        
        for search_query in [query, lemma_query]:
            query_hash = self._russian_metaphone(search_query)
            if not query_hash:
                continue
            
            candidates = self.phonetic_index.get(query_hash, [])
            
            for db_name, food in candidates:
                # Проверяем, не слишком ли разные по длине
                if abs(len(search_query) - len(db_name)) <= 3:
                    distance = self._calculate_distance(search_query, db_name)
                    confidence = self._calculate_confidence(
                        distance,
                        max(len(search_query), len(db_name)),
                        MatchStrategy.PHONETIC
                    )
                    
                    results.append(MatchResult(
                        food=food,
                        strategy=MatchStrategy.PHONETIC,
                        confidence=confidence * 0.9,
                        distance=distance,
                        matched_words=[db_name]
                    ))
        
        results.sort(key=lambda x: x.confidence, reverse=True)
        return results[:5]
    
    def _search_partial(self, query: str) -> List[MatchResult]:
        """Частичный поиск (по отдельным словам)."""
        query = self._normalize(query)
        query_words = self._tokenize(query)
        results = []
        
        if not query_words:
            return results
        
        # Находим продукты, содержащие хотя бы одно слово из запроса
        candidate_indices: Set[int] = set()
        for word in query_words:
            if word in self.word_index:
                candidate_indices.update(self.word_index[word])
            else:
                # Пробуем найти похожие слова
                for idx_word in self.word_index:
                    if self._calculate_distance(word, idx_word) <= 1:
                        candidate_indices.update(self.word_index[idx_word])
        
        scored_results = []
        for idx in candidate_indices:
            food = self.database[idx]
            db_name = self._normalize(food["name"])
            db_words = set(self._tokenize(db_name))
            
            # Считаем, сколько слов совпало
            matched = set(query_words) & db_words
            match_ratio = len(matched) / max(len(query_words), len(db_words))
            
            if match_ratio >= 0.4:  # Снизили порог
                confidence = self._calculate_confidence(
                    int((1 - match_ratio) * 10),
                    10,
                    MatchStrategy.PARTIAL
                )
                scored_results.append(MatchResult(
                    food=food,
                    strategy=MatchStrategy.PARTIAL,
                    confidence=confidence * match_ratio,
                    distance=int((1 - match_ratio) * 10),
                    matched_words=list(matched)
                ))
        
        scored_results.sort(key=lambda x: x.confidence, reverse=True)
        return scored_results[:5]
    
    def search(self, user_input: str, use_api: bool = True) -> List[MatchResult]:
        """
        Основной метод поиска. Пробует все стратегии и возвращает лучшие результаты.
        """
        user_input = self._normalize(user_input)
        
        # Проверяем кэш
        cache_key = f"{user_input}:{use_api}"
        if cache_key in self._cache:
            self._cache.move_to_end(cache_key)
            return self._cache[cache_key]
        
        all_results: List[MatchResult] = []
        seen_foods: Set[int] = set()
        
        # Стратегии в порядке приоритета
        strategies = [
            self._search_exact,
            self._search_normalized,
            self._search_synonyms,
            self._search_typo,
            self._search_phonetic,
            self._search_partial,
        ]
        
        for strategy_func in strategies:
            results = strategy_func(user_input)
            for r in results:
                food_id = id(r.food)
                if food_id not in seen_foods:
                    seen_foods.add(food_id)
                    all_results.append(r)
        
        # Сортируем по уверенности и приоритету стратегии
        strategy_order = {
            MatchStrategy.EXACT: 0,
            MatchStrategy.NORMALIZED: 1,
            MatchStrategy.SYNONYM: 2,
            MatchStrategy.TYPO: 3,
            MatchStrategy.PHONETIC: 4,
            MatchStrategy.PARTIAL: 5,
        }
        
        all_results.sort(key=lambda x: (
            -x.confidence,
            strategy_order.get(x.strategy, 10)
        ))
        
        # Сохраняем в кэш
        self._cache[cache_key] = all_results[:10]
        if len(self._cache) > self._cache_max_size:
            self._cache.popitem(last=False)
        
        return all_results[:5]
    
    async def search_with_api_fallback(self, user_input: str) -> List[Dict[str, Any]]:
        """
        Поиск с fallback на внешнее API.
        """
        # Сначала ищем локально
        local_results = self.search(user_input, use_api=False)
        
        if local_results and local_results[0].confidence >= 0.7:
            # Хорошее локальное совпадение
            return [r.food for r in local_results if r.confidence >= 0.5]
        
        # Пробуем API если есть
        if self.api_client:
            try:
                api_results = await self.api_client.search_products(user_input)
                
                # Добавляем в локальную базу для будущих запросов
                for food in api_results[:3]:
                    if food not in self.database:
                        self.database.append(food)
                        self._build_indexes()
                
                if api_results:
                    return api_results[:5]
            except Exception as e:
                logger.warning(f"API search failed: {e}")
        
        # Возвращаем локальные результаты
        return [r.food for r in local_results[:5]]
    
    def get_best_match(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Возвращает лучший результат или None."""
        results = self.search(user_input)
        if results and results[0].confidence >= 0.5:
            return results[0].food
        return None


# Логгер для модуля
import logging
logger = logging.getLogger(__name__)


# Синхронная обёртка для удобства
class SyncFoodMatcher:
    """Синхронная обёртка для OptimizedFoodMatcher."""
    
    def __init__(self, food_database: List[Dict[str, Any]], api_client=None):
        self._matcher = OptimizedFoodMatcher(food_database, api_client)
    
    def search(self, user_input: str) -> List[Dict[str, Any]]:
        """Синхронный поиск."""
        results = self._matcher.search(user_input, use_api=False)
        return [r.food for r in results]
    
    def get_best_match(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Синхронное получение лучшего совпадения."""
        return self._matcher.get_best_match(user_input)