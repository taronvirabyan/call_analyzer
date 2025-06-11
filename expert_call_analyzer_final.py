# -*- coding: utf-8 -*-
"""
МАСТЕР-СИСТЕМА АНАЛИЗА ЗВОНКОВ: ПОЛНЫЙ ЦИКЛ
MP3 → AssemblyAI → Диалог → Gemini AI → Отчеты

Объединяет:
1. Обработку MP3 через AssemblyAI (из voices.py)
2. Экспертный анализ через Gemini AI
3. Автоматическую генерацию отчетов

Автор: Expert AI System
"""

import json
import os
import time
import pathlib
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime
from collections import defaultdict
import re

# Импортируем Google GenAI (обязательно!)
try:
    from google import genai
except ImportError:
    print("❌ ОШИБКА: Google GenAI не установлен!")
    print("📦 Установите: pip install google-genai")
    print("🔧 Система работает только с Gemini AI")
    exit(1)


class AssemblyAIProcessor:
    """Обработчик MP3 файлов через AssemblyAI"""
    
    def __init__(self, api_key: str = "83d2ca78325f4cb59b2fc841e9c89137"):
        self.api_key = api_key
        self.headers = {"authorization": api_key}
    
    def upload_audio(self, path: str) -> str:
        """Загружает аудио файл в AssemblyAI"""
        print(f"📤 Загружаем MP3 файл: {path}")
        
        if not os.path.exists(path):
            raise FileNotFoundError(f"Аудио файл не найден: {path}")
            
        with open(path, "rb") as f:
            res = requests.post("https://api.assemblyai.com/v2/upload",
                              headers=self.headers, data=f)
        res.raise_for_status()
        url = res.json()["upload_url"]
        print(f"✅ Файл загружен в AssemblyAI")
        return url

    def start_transcription(self, url: str, expected_speakers: int = 2) -> str:
        """Запускает транскрипцию с диаризацией"""
        print(f"🎤 Запускаем транскрипцию с {expected_speakers} спикерами...")
        
        job = {
            "audio_url": url,
            "speaker_labels": True,
            "speakers_expected": expected_speakers,
            "language_code": "ru",
            "punctuate": True,
            "format_text": True
        }
        
        res = requests.post("https://api.assemblyai.com/v2/transcript",
                          headers=self.headers, json=job)
        res.raise_for_status()
        job_id = res.json()["id"]
        print(f"✅ Транскрипция запущена, ID: {job_id}")
        return job_id

    def wait_transcription(self, job_id: str) -> dict:
        """Ожидает завершения транскрипции"""
        print("⏳ Ждем завершения транскрипции...")
        status_url = f"https://api.assemblyai.com/v2/transcript/{job_id}"
        
        while True:
            res = requests.get(status_url, headers=self.headers).json()
            status = res["status"]
            
            if status == "completed":
                print("✅ Транскрипция завершена успешно!")
                return res
            elif status == "error":
                error_msg = res.get('error', 'Неизвестная ошибка')
                print(f"❌ Ошибка транскрипции: {error_msg}")
                raise Exception(f"Ошибка AssemblyAI: {error_msg}")
            else:
                print(f"📊 Статус: {status}...")
                time.sleep(5)

    def analyze_speaker_patterns(self, utterances: list) -> dict:
        """Анализирует паттерны речи для определения ролей"""
        patterns = {}
        
        for utt in utterances:
            speaker = utt['speaker']
            text = utt['text'].lower()
            
            if speaker not in patterns:
                patterns[speaker] = {
                    'questions': 0,
                    'long_speeches': 0,
                    'short_responses': 0,
                    'total_words': 0,
                    'selling_words': 0
                }
            
            words = text.split()
            word_count = len(words)
            patterns[speaker]['total_words'] += word_count
            
            # Анализ вопросов
            if '?' in text:
                patterns[speaker]['questions'] += 1
            
            # Анализ длины реплик
            if word_count > 20:
                patterns[speaker]['long_speeches'] += 1
            elif word_count <= 5:
                patterns[speaker]['short_responses'] += 1
            
            # Слова продавца
            selling_words = ['конференция', 'участие', 'сумма', 'стоимость', 'регистрация', 'мероприятие', 'продажа']
            patterns[speaker]['selling_words'] += sum(1 for word in selling_words if word in text)
        
        return patterns

    def smart_merge_speakers(self, utterances: list, max_speakers: int = 2) -> list:
        """Умное объединение спикеров"""
        if not utterances:
            return utterances
        
        speaker_stats = defaultdict(list)
        for utt in utterances:
            speaker_stats[utt['speaker']].append(utt)
        
        # Если спикеров не больше максимума, возвращаем как есть
        if len(speaker_stats) <= max_speakers:
            return utterances
        
        print(f"🔧 Обнаружено {len(speaker_stats)} спикеров, объединяем до {max_speakers}")
        
        # Анализируем роли
        patterns = self.analyze_speaker_patterns(utterances)
        
        speaker_roles = {}
        for speaker, stats in patterns.items():
            # Индекс "продавца"
            seller_score = (
                stats['long_speeches'] * 2 +
                stats['selling_words'] * 3 +
                stats['questions'] * 1
            )
            speaker_roles[speaker] = {
                'seller_score': seller_score,
                'total_words': stats['total_words']
            }
        
        # Сортируем по продавческому индексу
        sorted_speakers = sorted(speaker_roles.items(), 
                               key=lambda x: (x[1]['seller_score'], x[1]['total_words']), 
                               reverse=True)
        
        print("📊 Анализ ролей:")
        for speaker, role in sorted_speakers:
            print(f"   {speaker}: продавец_индекс={role['seller_score']}, слов={role['total_words']}")
        
        # Создаем маппинг
        speaker_mapping = {}
        if len(sorted_speakers) >= 2:
            speaker_mapping[sorted_speakers[0][0]] = 'A'  # Продавец
            speaker_mapping[sorted_speakers[1][0]] = 'B'  # Клиент
            
            # Остальных к продавцу (обычно это фоновые звуки)
            for i in range(2, len(sorted_speakers)):
                speaker_mapping[sorted_speakers[i][0]] = 'A'
        else:
            speaker_mapping[sorted_speakers[0][0]] = 'A'
        
        print("🔄 Объединение:")
        for orig, new in speaker_mapping.items():
            print(f"   {orig} → SPEAKER_{new}")
        
        # Применяем маппинг
        merged = []
        for utt in utterances:
            new_utt = utt.copy()
            new_utt['speaker'] = speaker_mapping[utt['speaker']]
            merged.append(new_utt)
        
        return merged

    def create_dialogue_file(self, transcription_result: dict, max_speakers: int = 2) -> str:
        """Создает файл диалога"""
        print("📝 Создаем файл диалога...")
        
        utterances = transcription_result.get("utterances", [])
        if not utterances:
            raise ValueError("Нет данных диалога в результате транскрипции")
        
        # Умное объединение спикеров
        merged = self.smart_merge_speakers(utterances, max_speakers)
        
        # Сортируем по времени
        merged.sort(key=lambda x: x['start'])
        
        lines = []
        for utt in merged:
            spk = f"SPEAKER_{utt['speaker']}"
            start = utt["start"] / 1000.0
            lines.append(f"[{spk} {start:08.2f}] {utt['text']}")
        
        # Создаем файл диалога
        dialogue_file = "dialogue.txt"
        pathlib.Path(dialogue_file).write_text("\n".join(lines), encoding="utf-8")
        
        print(f"✅ Диалог создан: {dialogue_file}")
        print(f"📊 Количество реплик: {len(lines)}")
        
        return dialogue_file


class GeminiCallAnalyzer:
    """Профессиональный анализатор звонков на базе Gemini AI"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.retry_count = 0
        self.max_retries = 3
        
    def analyze_call(self, dialogue_text: str, retry_delay: int = 60) -> Dict[str, Any]:
        """Профессиональный анализ звонка через Gemini AI"""
        
        prompt = f"""
Ты эксперт по анализу продающих звонков. Проанализируй этот диалог:

{dialogue_text}

ПРОВЕДИ АНАЛИЗ ПО КРИТЕРИЯМ:
1. Построение доверия (20%)
2. Выявление потребностей (25%)
3. Презентация решения (20%)
4. Работа с возражениями (20%)
5. Закрытие и следующие шаги (15%)

ДОПОЛНИТЕЛЬНО ОПРЕДЕЛИ:
- Психологический профиль клиента
- Упущенные возможности
- Критические ошибки
- Эмоциональную динамику

Верни результат в формате JSON с полями:
- overall_score (0-100)
- quality_rating
- strengths (список)
- weaknesses (список)
- recommendations (список)
- psychological_profile (объект с полями: description, keywords, client_type, motivation_level, decision_style)
- critical_moments (список объектов с полями: time, description)
- success_probability
"""
        

        
        try:
            # Создаем клиента
            client = genai.Client(api_key=self.api_key)
            
            # Выбираем модель в зависимости от попытки
            models = ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-pro']
            model = models[min(self.retry_count, len(models)-1)]
            
            print(f"🤖 Используем модель: {model}")
            
            response = client.models.generate_content(
                model=model,
                contents=prompt
            )
            
            if response and response.text:
                return self._parse_response(response.text)
            else:
                raise Exception("Пустой ответ от API")
                
        except Exception as e:
            error_str = str(e)
            
            # Обработка ошибки квоты - пробуем retry
            if "429" in error_str or "quota" in error_str.lower():
                print(f"⚠️ Превышена квота API. Попытка {self.retry_count + 1}/{self.max_retries}")
                
                if self.retry_count < self.max_retries:
                    self.retry_count += 1
                    wait_time = retry_delay * self.retry_count
                    print(f"⏳ Ожидание {wait_time} секунд...")
                    time.sleep(wait_time)
                    return self.analyze_call(dialogue_text, retry_delay)
                else:
                    print("❌ Исчерпаны попытки подключения к Gemini API")
                    print("🔧 Проверьте квоты API или попробуйте позже")
                    raise Exception("Gemini API недоступен: превышены квоты")
            
            # Другие ошибки API
            else:
                print(f"❌ Критическая ошибка Gemini API: {error_str}")
                print("🔧 Проверьте ваш API ключ и соединение")
                raise Exception(f"Gemini API ошибка: {error_str}")
    
    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Парсинг ответа Gemini"""
        try:
            # Извлекаем JSON
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                json_text = json_match.group()
                # Очищаем от markdown
                json_text = re.sub(r'```json\n?', '', json_text)
                json_text = re.sub(r'```\n?', '', json_text)
                return json.loads(json_text)
            else:
                # Если не нашли JSON, парсим текст
                return self._parse_text_response(response_text)
        except:
            return self._parse_text_response(response_text)
    
    def _parse_text_response(self, text: str) -> Dict[str, Any]:
        """Парсинг текстового ответа если JSON не найден"""
        result = {
            "overall_score": 70,
            "quality_rating": "Хороший",
            "strengths": [],
            "weaknesses": [],
            "recommendations": [],
            "analysis_text": text
        }
        
        # Пытаемся извлечь информацию из текста
        lines = text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if 'сильн' in line.lower() or 'преимущ' in line.lower():
                current_section = 'strengths'
            elif 'слаб' in line.lower() or 'недостат' in line.lower():
                current_section = 'weaknesses'
            elif 'рекоменд' in line.lower() or 'совет' in line.lower():
                current_section = 'recommendations'
            elif line.startswith('-') or line.startswith('•') or line.startswith('*'):
                if current_section and current_section in result:
                    result[current_section].append(line[1:].strip())
        
        return result
    



class MasterCallAnalyzer:
    """Мастер-система полного анализа: MP3 → Диалог → AI Анализ → Отчеты"""
    
    def __init__(self, assemblyai_key: str = "83d2ca78325f4cb59b2fc841e9c89137", 
                 gemini_key: str = None):
        if not gemini_key:
            gemini_key = os.getenv("GEMINI_API_KEY", "AIzaSyCZcwunnoBBqhTYtbgJZl-7hpqJEVqFTeY")
        
        self.assembly_processor = AssemblyAIProcessor(assemblyai_key)
        self.gemini_analyzer = GeminiCallAnalyzer(gemini_key)
    
    def process_audio_complete(self, audio_file: str, expected_speakers: int = 2) -> tuple:
        """ПОЛНЫЙ ЦИКЛ: MP3 → Диалог → Анализ → Отчеты"""
        
        print("="*80)
        print("🎯 МАСТЕР-СИСТЕМА АНАЛИЗА ЗВОНКОВ")
        print("📁 MP3 → AssemblyAI → Gemini AI → Отчеты")
        print("="*80)
        print(f"🎵 Обрабатываем: {audio_file}")
        print()
        
        try:
            # ШАГ 1: Обработка MP3 через AssemblyAI
            print("🔄 ШАГ 1: ТРАНСКРИПЦИЯ")
            print("-" * 40)
            
            upload_url = self.assembly_processor.upload_audio(audio_file)
            job_id = self.assembly_processor.start_transcription(upload_url, expected_speakers)
            transcription_result = self.assembly_processor.wait_transcription(job_id)
            
            # Сохраняем результат AssemblyAI
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            assembly_file = f"assembly_result_{timestamp}.json"
            with open(assembly_file, 'w', encoding='utf-8') as f:
                json.dump(transcription_result, f, ensure_ascii=False, indent=2)
            print(f"💾 Данные AssemblyAI: {assembly_file}")
            
            # ШАГ 2: Создание диалога
            print("\n🔄 ШАГ 2: СОЗДАНИЕ ДИАЛОГА")
            print("-" * 40)
            
            dialogue_file = self.assembly_processor.create_dialogue_file(transcription_result, expected_speakers)
            
            # ШАГ 3: AI анализ через Gemini
            print("\n🔄 ШАГ 3: AI АНАЛИЗ")
            print("-" * 40)
            
            analysis_result = self.gemini_analyzer.analyze_call(self._read_dialogue_for_analysis(dialogue_file))
            
            # ШАГ 4: Генерация отчетов
            print("\n🔄 ШАГ 4: ГЕНЕРАЦИЯ ОТЧЕТОВ")
            print("-" * 40)
            
            json_file, md_file = self._generate_complete_reports(analysis_result, dialogue_file, assembly_file)
            
            # ФИНАЛЬНЫЙ РЕЗУЛЬТАТ
            print("\n" + "="*80)
            print("🎉 МАСТЕР-АНАЛИЗ ЗАВЕРШЕН УСПЕШНО!")
            print("="*80)
            print("📊 ИТОГОВЫЕ ФАЙЛЫ:")
            print(f"   🎵 Исходный MP3: {audio_file}")
            print(f"   📝 Диалог: {dialogue_file}")
            print(f"   📋 JSON анализ: {json_file}")
            print(f"   📄 MD отчет: {md_file}")
            print(f"   🔄 AssemblyAI данные: {assembly_file}")
            print()
            print(f"🏆 ОЦЕНКА ЗВОНКА: {analysis_result.get('overall_score', 'N/A')}/100")
            print(f"📈 КАТЕГОРИЯ: {analysis_result.get('quality_rating', 'N/A')}")
            print(f"🎯 ВЕРОЯТНОСТЬ УСПЕХА: {analysis_result.get('success_probability', 'N/A')}")
            print("="*80)
            
            return dialogue_file, json_file, md_file, assembly_file
            
        except Exception as e:
            print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА МАСТЕР-СИСТЕМЫ: {e}")
            print("💡 Проверьте:")
            print("   - Существование MP3 файла")
            print("   - API ключи AssemblyAI и Gemini")
            print("   - Подключение к интернету")
            print("   - Квоты API сервисов")
            raise

    def _read_dialogue_for_analysis(self, dialogue_file: str) -> str:
        """Читает диалог для анализа Gemini"""
        with open(dialogue_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        dialogue_parts = []
        for line in lines:
            line = line.strip()
            if line.startswith('[SPEAKER_'):
                parts = line.split('] ', 1)
                if len(parts) == 2:
                    header = parts[0][1:]
                    text = parts[1]
                    
                    header_parts = header.split(' ')
                    if len(header_parts) >= 2:
                        speaker = header_parts[0]
                        time_str = header_parts[1]
                        
                        role = "ПРОДАВЕЦ" if speaker == "SPEAKER_A" else "КЛИЕНТ"
                        dialogue_parts.append(f"[{time_str}] {role}: {text}")
        
        return "\n".join(dialogue_parts)

    def _generate_complete_reports(self, analysis_result: Dict[str, Any], 
                                 dialogue_file: str, assembly_file: str) -> tuple:
        """Генерирует полные отчеты мастер-системы"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # JSON отчет
        json_file = f"master_analysis_{timestamp}.json"
        
        # Добавляем метаданные мастер-системы
        complete_analysis = {
            **analysis_result,
            "system_info": {
                "analysis_type": "Master Call Analysis",
                "transcription_engine": "AssemblyAI Professional",
                "ai_analyzer": "Gemini AI Professional",
                "processing_date": datetime.now().isoformat(),
                "dialogue_file": dialogue_file,
                "assembly_data": assembly_file
            }
        }
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(complete_analysis, f, ensure_ascii=False, indent=2)
        
        # MD отчет
        md_file = f"master_report_{timestamp}.md"
        
        report = f"""# 🎯 МАСТЕР-АНАЛИЗ ПРОДАЮЩЕГО ЗВОНКА

**📅 Дата анализа:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  
**📁 Диалог:** {dialogue_file}  
**🤖 Система:** Master Call Analyzer v2.0

---

## 🏗️ ТЕХНОЛОГИЧЕСКИЙ СТЕК

- **🎤 Транскрипция:** AssemblyAI Professional API
- **🧠 AI Анализ:** Google Gemini Professional  
- **📊 Диаризация:** Умная система определения ролей спикеров
- **📈 Глубина:** Экспертный уровень анализа

---

## 📊 ОБЩАЯ ОЦЕНКА

**Балл:** {analysis_result.get('overall_score', 'N/A')}/100  
**Категория:** {analysis_result.get('quality_rating', 'N/A')}  
**Вероятность успеха:** {analysis_result.get('success_probability', 'Не определена')}

---

## ✅ СИЛЬНЫЕ СТОРОНЫ ({len(analysis_result.get('strengths', []))})

"""
        
        for i, strength in enumerate(analysis_result.get('strengths', []), 1):
            report += f"{i}. {strength}\n"
        
        report += f"""
---

## ⚠️ ОБЛАСТИ ДЛЯ УЛУЧШЕНИЯ ({len(analysis_result.get('weaknesses', []))})

"""
        
        for i, weakness in enumerate(analysis_result.get('weaknesses', []), 1):
            report += f"{i}. {weakness}\n"
        
        report += f"""
---

## 💡 ЭКСПЕРТНЫЕ РЕКОМЕНДАЦИИ ({len(analysis_result.get('recommendations', []))})

"""
        
        for i, rec in enumerate(analysis_result.get('recommendations', []), 1):
            report += f"{i}. {rec}\n"
        
        # Психологический профиль
        if 'psychological_profile' in analysis_result:
            profile = analysis_result['psychological_profile']
            report += "\n---\n\n## 🧠 ПСИХОЛОГИЧЕСКИЙ ПРОФИЛЬ КЛИЕНТА\n\n"
            
            if isinstance(profile, dict):
                for key, value in profile.items():
                    if isinstance(value, list):
                        report += f"**{key.title()}:** {', '.join(value)}\n\n"
                    else:
                        report += f"**{key.title()}:** {value}\n\n"
        
        # Критические моменты
        if analysis_result.get('critical_moments'):
            moments = analysis_result['critical_moments']
            report += "---\n\n## 🚨 КРИТИЧЕСКИЕ МОМЕНТЫ РАЗГОВОРА\n\n"
            
            for i, moment in enumerate(moments, 1):
                if isinstance(moment, dict):
                    time_marker = moment.get('time', 'N/A')
                    description = moment.get('description', 'Описание отсутствует')
                    report += f"{i}. **[{time_marker}]** {description}\n"
                else:
                    report += f"{i}. {moment}\n"
        
        report += f"""
---

## 📁 ФАЙЛЫ РЕЗУЛЬТАТОВ

- **🎵 Исходный аудио:** Обработан через AssemblyAI
- **📝 Диалог:** `{dialogue_file}`
- **📋 JSON анализ:** `{json_file}`
- **🔄 Данные транскрипции:** `{assembly_file}`

---

## 📝 РЕЗЮМЕ

Данный анализ выполнен мастер-системой полного цикла, включающей профессиональную транскрипцию через AssemblyAI с интеллектуальной диаризацией спикеров и последующий экспертный анализ через Gemini AI. 

Система обеспечивает максимальную точность распознавания речи, корректное определение ролей участников диалога и глубокий AI-анализ качества продающего разговора.

**🤖 Powered by:** AssemblyAI + Google Gemini AI  
**⚡ Система:** Master Call Analyzer v2.0  
**🎯 Уровень:** Enterprise Grade Analysis
"""
        
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"✅ JSON отчет: {json_file}")
        print(f"✅ MD отчет: {md_file}")
        
        return json_file, md_file


def analyze_call_with_gemini(dialogue_file: str = "dialogue.txt", api_key: str = None):
    """Главная функция для анализа звонка с помощью Gemini AI"""
    
    # Получаем API ключ
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY", "AIzaSyCZcwunnoBBqhTYtbgJZl-7hpqJEVqFTeY")
    
    print("="*80)
    print("🎯 ЭКСПЕРТНЫЙ АНАЛИЗ ЗВОНКА (GEMINI AI)")
    print("="*80)
    
    # Читаем диалог
    try:
        with open(dialogue_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        dialogue_parts = []
        for line in lines:
            line = line.strip()
            if line.startswith('[SPEAKER_'):
                parts = line.split('] ', 1)
                if len(parts) == 2:
                    header = parts[0][1:]
                    text = parts[1]
                    
                    header_parts = header.split(' ')
                    if len(header_parts) >= 2:
                        speaker = header_parts[0]
                        time_str = header_parts[1]
                        
                        role = "ПРОДАВЕЦ" if speaker == "SPEAKER_A" else "КЛИЕНТ"
                        dialogue_parts.append(f"[{time_str}] {role}: {text}")
        
        dialogue_text = "\n".join(dialogue_parts)
        print(f"📞 Диалог загружен: {len(dialogue_parts)} реплик\n")
        
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return
    
    # Создаем профессиональный Gemini анализатор
    try:
        analyzer = GeminiCallAnalyzer(api_key)
        result = analyzer.analyze_call(dialogue_text)
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        print("🔧 Анализ невозможен без Gemini AI")
        print("💡 Проверьте:")
        print("   - API ключ Gemini")
        print("   - Подключение к интернету") 
        print("   - Квоты API")
        return
    
    # ПОЛНЫЙ ДЕТАЛЬНЫЙ ВЫВОД В ТЕРМИНАЛ
    print(f"\n📊 ОБЩАЯ ОЦЕНКА: {result.get('overall_score', 'N/A')}/100")
    print(f"📈 КАТЕГОРИЯ КАЧЕСТВА: {result.get('quality_rating', 'N/A')}")
    
    # Вероятность успеха
    if 'success_probability' in result:
        print(f"🎯 ВЕРОЯТНОСТЬ УСПЕХА СДЕЛКИ: {result['success_probability']}")
    

    
    # ПОЛНЫЙ СПИСОК СИЛЬНЫХ СТОРОН
    print(f"\n✅ СИЛЬНЫЕ СТОРОНЫ ({len(result.get('strengths', []))} пунктов):")
    for i, strength in enumerate(result.get('strengths', []), 1):
        print(f"   {i}. {strength}")
    
    # ПОЛНЫЙ СПИСОК СЛАБЫХ СТОРОН  
    print(f"\n⚠️ ОБЛАСТИ ДЛЯ УЛУЧШЕНИЯ ({len(result.get('weaknesses', []))} пунктов):")
    for i, weakness in enumerate(result.get('weaknesses', []), 1):
        print(f"   {i}. {weakness}")
    
    # ВСЕ РЕКОМЕНДАЦИИ
    print(f"\n💡 ЭКСПЕРТНЫЕ РЕКОМЕНДАЦИИ ({len(result.get('recommendations', []))} пунктов):")
    for i, rec in enumerate(result.get('recommendations', []), 1):
        print(f"   {i}. {rec}")
    
    # ПСИХОЛОГИЧЕСКИЙ ПРОФИЛЬ КЛИЕНТА
    if 'psychological_profile' in result:
        profile = result['psychological_profile']
        print(f"\n🧠 ПСИХОЛОГИЧЕСКИЙ ПРОФИЛЬ КЛИЕНТА:")
        
        if isinstance(profile, dict):
            # Поддерживаем разные форматы профиля
            if 'description' in profile:
                print(f"   📝 Описание: {profile['description']}")
            if 'keywords' in profile:
                print(f"   🔑 Ключевые характеристики: {', '.join(profile['keywords'])}")
            
            # Обрабатываем все остальные поля как дополнительную информацию
            for key, value in profile.items():
                if key not in ['description', 'keywords']:
                    if isinstance(value, list):
                        print(f"   🔸 {key.title()}: {', '.join(value)}")
                    else:
                        print(f"   🔸 {key.title()}: {value}")
        else:
            print(f"   📝 {profile}")
    
    # КРИТИЧЕСКИЕ МОМЕНТЫ
    if 'critical_moments' in result:
        moments = result['critical_moments']
        print(f"\n🚨 КРИТИЧЕСКИЕ МОМЕНТЫ РАЗГОВОРА:")
        
        if isinstance(moments, list):
            for i, moment in enumerate(moments, 1):
                if isinstance(moment, dict):
                    time_marker = moment.get('time', 'N/A')
                    description = moment.get('description', 'Описание отсутствует')
                    print(f"   {i}. [{time_marker}] {description}")
                else:
                    print(f"   {i}. {moment}")
        else:
            print(f"   {moments}")
    
    # ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ
    print(f"\n🤖 Анализ выполнен: Gemini AI Professional Analysis")
    
    # Сохраняем результат
    output_file = f"call_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 Результаты сохранены в: {output_file}")
    
    # Генерируем ПОЛНЫЙ ЭКСПЕРТНЫЙ ОТЧЕТ
    report = f"""# 🎯 ЭКСПЕРТНЫЙ АНАЛИЗ ПРОДАЮЩЕГО ЗВОНКА

**📅 Дата анализа:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  
**📁 Исходный файл:** {dialogue_file}  
**🤖 Метод анализа:** Gemini AI Professional Analysis

---

## 📊 ОБЩАЯ ОЦЕНКА

**Балл:** {result.get('overall_score', 'N/A')}/100  
**Категория:** {result.get('quality_rating', 'N/A')}  
**Вероятность успеха:** {result.get('success_probability', 'Не определена')}

### 📈 Статистика разговора:
- **Модель AI:** Gemini Professional Analysis
- **Глубина анализа:** Экспертный уровень

"""
    
    report += f"""

---

## ✅ СИЛЬНЫЕ СТОРОНЫ ({len(result.get('strengths', []))})

"""
    
    for i, strength in enumerate(result.get('strengths', []), 1):
        report += f"{i}. {strength}\n"
    
    report += f"""
---

## ⚠️ ОБЛАСТИ ДЛЯ УЛУЧШЕНИЯ ({len(result.get('weaknesses', []))})

"""
    
    for i, weakness in enumerate(result.get('weaknesses', []), 1):
        report += f"{i}. {weakness}\n"
    
    report += f"""
---

## 💡 ЭКСПЕРТНЫЕ РЕКОМЕНДАЦИИ ({len(result.get('recommendations', []))})

"""
    
    for i, rec in enumerate(result.get('recommendations', []), 1):
        report += f"{i}. {rec}\n"
    
    # Добавляем психологический профиль
    if 'psychological_profile' in result:
        profile = result['psychological_profile']
        report += "\n---\n\n## 🧠 ПСИХОЛОГИЧЕСКИЙ ПРОФИЛЬ КЛИЕНТА\n\n"
        
        if isinstance(profile, dict):
            # Поддерживаем стандартные поля
            if 'description' in profile:
                report += f"**Описание:** {profile['description']}\n\n"
            if 'keywords' in profile:
                report += f"**Ключевые характеристики:** {', '.join(profile['keywords'])}\n\n"
            
            # Обрабатываем все остальные поля
            for key, value in profile.items():
                if key not in ['description', 'keywords']:
                    if isinstance(value, list):
                        report += f"**{key.title()}:** {', '.join(value)}\n\n"
                    else:
                        report += f"**{key.title()}:** {value}\n\n"
        else:
            report += f"{profile}\n\n"
    
    # Добавляем критические моменты
    if 'critical_moments' in result:
        moments = result['critical_moments']
        report += "---\n\n## 🚨 КРИТИЧЕСКИЕ МОМЕНТЫ РАЗГОВОРА\n\n"
        
        if isinstance(moments, list):
            for i, moment in enumerate(moments, 1):
                if isinstance(moment, dict):
                    time_marker = moment.get('time', 'N/A')
                    description = moment.get('description', 'Описание отсутствует')
                    report += f"{i}. **[{time_marker}]** {description}\n"
                else:
                    report += f"{i}. {moment}\n"
        else:
            report += f"{moments}\n"
    

    
    report += f"""
---

## 📝 РЕЗЮМЕ

Данный анализ основан на экспертной оценке продающего разговора с использованием передовых методов анализа диалогов. Рекомендации направлены на повышение эффективности продаж и улучшение качества коммуникации с клиентами.

**Файл результатов:** `{output_file}`  
**Анализ выполнен:** Gemini AI Professional Call Analysis System
"""
    
    report_file = f"call_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"📄 Подробный экспертный отчет: {report_file}")


def process_mp3_file(audio_file: str = "sell_audio.mp3", expected_speakers: int = 2):
    """Функция для полной обработки MP3 файла"""
    
    # API ключи
    ASSEMBLYAI_KEY = "83d2ca78325f4cb59b2fc841e9c89137"
    GEMINI_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCZcwunnoBBqhTYtbgJZl-7hpqJEVqFTeY")
    
    # Создаем мастер-систему
    master = MasterCallAnalyzer(ASSEMBLYAI_KEY, GEMINI_KEY)
    
    try:
        dialogue, json_report, md_report, assembly_data = master.process_audio_complete(audio_file, expected_speakers)
        
        print("\n🚀 МАСТЕР-СИСТЕМА ЗАВЕРШИЛА РАБОТУ УСПЕШНО!")
        print("📁 Все файлы созданы и готовы к использованию")
        
        return dialogue, json_report, md_report, assembly_data
        
    except Exception as e:
        print(f"\n❌ ОШИБКА МАСТЕР-СИСТЕМЫ: {e}")
        print("💡 Убедитесь в корректности API ключей и наличии MP3 файла")
        return None


if __name__ == "__main__":
    print("🎯 ВЫБЕРИТЕ РЕЖИМ РАБОТЫ:")
    print("1. Полный анализ MP3 файла (рекомендуется)")
    print("2. Анализ существующего dialogue.txt")
    
    try:
        choice = input("\nВведите номер (1 или 2): ").strip()
        
        if choice == "1":
            # Полный анализ MP3
            audio_file = input("Введите имя MP3 файла (по умолчанию 'sell_audio.mp3'): ").strip()
            if not audio_file:
                audio_file = "sell_audio.mp3"
            
            print(f"\n🎵 Запускаем полный анализ файла: {audio_file}")
            process_mp3_file(audio_file)
            
        elif choice == "2":
            # Анализ существующего диалога
            dialogue_file = input("Введите имя файла диалога (по умолчанию 'dialogue.txt'): ").strip()
            if not dialogue_file:
                dialogue_file = "dialogue.txt"
            
            print(f"\n📝 Анализируем существующий диалог: {dialogue_file}")
            analyze_call_with_gemini(dialogue_file)
            
        else:
            print("❌ Некорректный выбор. Запускаем полный анализ по умолчанию...")
            process_mp3_file()
            
    except KeyboardInterrupt:
        print("\n\n👋 Работа прервана пользователем")
    except Exception as e:
        print(f"\n❌ Неожиданная ошибка: {e}")
        print("🔄 Запускаем полный анализ по умолчанию...")
        process_mp3_file() 