import vk_api
import json
import csv
import re
import time

def clean_name(name):
    """Очищаем название от технических кодов и улучшаем поиск"""
    # Убираем коды типа 'v4ng6', '8qbfm' и т.д.
    cleaned = re.sub(r'\s+[a-z0-9]{4,6}$', '', name)
    # Убираем двойные пробелы
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # Заменяем сокращения
    replacements = {
        'picca': 'пицца',
        'pizza': 'пицца',
        'osteria': 'остерия',
        'paolo': 'паоло',
        'express': 'экспресс',
        'burger': 'бургер',
        'sushi': 'суши'
    }
    
    for eng, rus in replacements.items():
        cleaned = re.sub(r'\b' + eng + r'\b', rus, cleaned, flags=re.IGNORECASE)
    
    return cleaned.strip()

def is_relevant_group(group_name, original_name):
    """Проверяем, релевантна ли группа пиццерии и возвращаем оценку"""
    name_lower = group_name.lower()
    original_lower = original_name.lower()
    
    score = 0
    
    # Ключевые слова связанные с пиццей и едой (разные веса)
    food_keywords = {
        'пицц': 3, 'pizz': 3, 'пицца': 3, 'pizza': 3,
        'суши': 2, 'sushi': 2, 'ролл': 2, 
        'еда': 2, 'food': 2, 'ресторан': 2, 'restaurant': 2,
        'кафе': 2, 'cafe': 2, 'доставка': 2, 'delivery': 2,
        'кухн': 1, 'кулин': 1, 'едим': 1, 'вкусн': 1,
        'заказ': 1, 'menu': 1, 'меню': 1, 'бургер': 1,
        'шаурм': 1, 'шаверм': 1, 'кофе': 1, 'coffee': 1
    }
    
    # Бонусы за ключевые слова
    for keyword, weight in food_keywords.items():
        if keyword in name_lower:
            score += weight
    
    # Бонус за московскую локацию
    moscow_keywords = ['москв', 'moscow', 'мск', 'msk', 'московск']
    for moscow_word in moscow_keywords:
        if moscow_word in name_lower:
            score += 4  # Большой бонус за Москву
    
    # Слова, которые НЕ должны быть в названии пиццерии (штрафы)
    exclude_keywords = [
        'прочистка', 'канализация', 'депутат', 'совет', 'сакура', 
        'функ', 'раста', 'шоурум', 'сергей', 'сушкоф', 'мини мисс',
        'чистка', 'сервис', 'промокод', 'акция', 'скидк', 'распродаж',
        'продаж', 'магазин', 'shop', 'авто', 'auto', 'недвиж', 'ремонт'
    ]
    
    # Штраф за исключающие слова
    for exclude in exclude_keywords:
        if exclude in name_lower:
            score -= 5  # Большой штраф
    
    # Штраф за другие города (кроме Москвы)
    other_cities = ['череповец', 'воронеж', 'смоленск', 'санкт-петербург', 'спб', 
                   'екатеринбург', 'екб', 'новосибирск', 'нск', 'казань', 'нижний',
                   'краснодар', 'ростов', 'самара', 'волгоград', 'пермь', 'уфа']
    for city in other_cities:
        if city in name_lower:
            score -= 3  # Штраф за не-московские города
    
    # Проверяем частичное совпадение с оригинальным названием
    name_words = set(re.findall(r'\w+', original_lower))
    group_words = set(re.findall(r'\w+', name_lower))
    common_words = name_words.intersection(group_words)
    
    # Убираем слишком общие слова
    common_words = common_words - {'пицца', 'pizza', 'picca', 'суши', 'sushi', 'доставка', 'еда', 'food'}
    
    # Бонус за совпадение уникальных слов
    if len(common_words) > 0:
        score += len(common_words) * 2
    
    # Особый бонус за точное совпадение ключевых слов из названия
    key_original_words = [word for word in name_words if word not in ['пицца', 'pizza', 'picca', 'суши', 'sushi'] and len(word) > 2]
    for word in key_original_words:
        if word in name_lower:
            score += 3
    
    return max(0, score)  # Не даем отрицательных оценок

def find_group(name):
    token = "vk1.a.l9RotXeUzGY_ZVmJqyRWU4vHhbZv_WMQFU9V3edHCciyrtrCKMjGzIwhj81xcDunLuX_Fq0x8aYHr_zkPC9ckpXYmED4Ixii5Ysjilj63YPmQrUwKP97MrL44ugXhEfIxnADGc4UuRtMiJyGS1DDdYE-sjJZwq7nq5GuGCGE9rxeoWowzX8G_9JzlgpUHOpF"
    
    try:
        vk = vk_api.VkApi(token=token).get_api()
        
        # Очищаем название
        cleaned_name = clean_name(name)
        
        # Создаем несколько вариантов поисковых запросов с упором на Москву
        search_queries = [
            f"{cleaned_name} пицца Москва",
            f"{cleaned_name} пицца доставка Москва",
            f"{cleaned_name} пицца",
            f"{cleaned_name} pizza Moscow",
            cleaned_name  # оригинальное название
        ]
        
        print(f"Поиск: {name}")
        print(f"Очищенное: {cleaned_name}")
        
        all_groups = []
        
        # Ищем по всем вариантам запросов
        for query in search_queries:
            try:
                result = vk.groups.search(q=query, type="group", count=10)
                all_groups.extend(result['items'])
                time.sleep(0.3)  # Задержка между запросами
            except Exception as e:
                print(f"Ошибка при запросе '{query}': {e}")
                continue
        
        # Убираем дубликаты
        unique_groups = []
        seen_ids = set()
        for group in all_groups:
            if group['id'] not in seen_ids:
                seen_ids.add(group['id'])
                unique_groups.append(group)
        
        if unique_groups:
            # Сортируем по релевантности с приоритетом Москвы
            scored_groups = []
            for group in unique_groups:
                score = is_relevant_group(group['name'], name)
                
                # Дополнительные бонусы
                name_lower = name.lower()
                group_lower = group['name'].lower()
                
                # Бонус за полное совпадение начала названия
                if group_lower.startswith(name_lower):
                    score += 5
                
                # Бонус за наличие в описании слов из оригинального названия
                name_keywords = [word for word in re.findall(r'\w+', name_lower) 
                               if word not in ['пицца', 'pizza', 'picca'] and len(word) > 2]
                for keyword in name_keywords:
                    if keyword in group_lower:
                        score += 2
                
                # Супер-бонус за московские ключевые слова в названии
                moscow_keywords = ['москв', 'moscow', 'мск', 'msk']
                for moscow_word in moscow_keywords:
                    if moscow_word in group_lower:
                        score += 6  # Очень большой бонус за Москву
                        break
                
                scored_groups.append((score, group))
            
            # Сортируем по убыванию релевантности
            scored_groups.sort(key=lambda x: x[0], reverse=True)
            
            # Берем лучший результат
            best_score, best_group = scored_groups[0]
            url = f"https://vk.com/{best_group['screen_name']}"
            
            # Определяем город группы
            group_city = "не указан"
            group_lower = best_group['name'].lower()
            if any(word in group_lower for word in ['москв', 'moscow', 'мск', 'msk']):
                group_city = "Москва"
            elif any(word in group_lower for word in ['череповец']):
                group_city = "Череповец"
            elif any(word in group_lower for word in ['воронеж']):
                group_city = "Воронеж"
            elif any(word in group_lower for word in ['смоленск']):
                group_city = "Смоленск"
            
            # Улучшенная градация качества
            if best_score >= 10:
                quality = 'excellent'
            elif best_score >= 6:
                quality = 'good'
            elif best_score >= 3:
                quality = 'fair'
            else:
                quality = 'poor'
            
            print(f"Найдено [{quality}]: {best_group['name']}")
            print(f"Город: {group_city}")
            print(f"Ссылка: {url}")
            print(f"Оценка релевантности: {best_score}")
            
            return {
                'original_name': name,
                'cleaned_name': cleaned_name,
                'vk_name': best_group['name'],
                'vk_url': url,
                'match_quality': quality,
                'relevance_score': best_score,
                'city': group_city
            }
        else:
            print(f"Не найдено: {name}")
            return {
                'original_name': name,
                'cleaned_name': cleaned_name,
                'vk_name': 'Не найдено',
                'vk_url': '',
                'match_quality': 'not_found',
                'relevance_score': 0,
                'city': 'не найден'
            }
            
    except Exception as e:
        print(f"Ошибка: {e}")
        return {
            'original_name': name,
            'cleaned_name': clean_name(name),
            'vk_name': f'Ошибка: {str(e)}',
            'vk_url': '',
            'match_quality': 'error',
            'relevance_score': -1,
            'city': 'ошибка'
        }

def main():
    print("ПОИСК МОСКОВСКИХ ПИЦЦЕРИЙ ВКонтакте")
    print("=" * 60)
    
    # Чтение пиццерий из CSV файла
    pizzerias = []
    
    with open('pizzerias.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pizzerias.append(row['name'])
    
    print(f"Загружено {len(pizzerias)} пиццерий из CSV")
    print("Начинаем поиск с приоритетом московских пиццерий...")
    print("Это займет некоторое время")
    print()
    
    found = []
    
    # Обрабатываем ВСЕ пиццерии
    for i, pizza in enumerate(pizzerias, 1):
        print(f"[{i}/{len(pizzerias)}] ", end="")
        result = find_group(pizza)
        found.append(result)
        
        # Прогресс каждые 10 записей
        if i % 10 == 0:
            stats = {
                'excellent': len([f for f in found if f['match_quality'] == 'excellent']),
                'good': len([f for f in found if f['match_quality'] == 'good']),
                'fair': len([f for f in found if f['match_quality'] == 'fair']),
                'poor': len([f for f in found if f['match_quality'] == 'poor']),
                'not_found': len([f for f in found if f['match_quality'] == 'not_found']),
                'error': len([f for f in found if f['match_quality'] == 'error']),
                'moscow': len([f for f in found if f['city'] == 'Москва'])
            }
            print(f"\n=== ПРОГРЕСС: {i}/{len(pizzerias)} ===")
            print(f"Отличные: {stats['excellent']}, Хорошие: {stats['good']}")
            print(f"Удовлетворительные: {stats['fair']}, Слабые: {stats['poor']}")
            print(f"Не найдено: {stats['not_found']}, Ошибок: {stats['error']}")
            print(f"Московских пиццерий: {stats['moscow']}")
            print("=" * 40)
        
        print("-" * 50)
        
        # Задержка чтобы не блокировали
        time.sleep(1)
    
    # Сохраняем результаты
    with open('pizza_links_moscow.json', 'w', encoding='utf-8') as f:
        json.dump(found, f, ensure_ascii=False, indent=2)
    
    with open('pizza_links_moscow.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'original_name', 'cleaned_name', 'vk_name', 'vk_url', 
            'match_quality', 'relevance_score', 'city'
        ])
        writer.writeheader()
        writer.writerows(found)
    
    # Финальная статистика
    stats = {
        'excellent': len([f for f in found if f['match_quality'] == 'excellent']),
        'good': len([f for f in found if f['match_quality'] == 'good']),
        'fair': len([f for f in found if f['match_quality'] == 'fair']),
        'poor': len([f for f in found if f['match_quality'] == 'poor']),
        'not_found': len([f for f in found if f['match_quality'] == 'not_found']),
        'error': len([f for f in found if f['match_quality'] == 'error']),
        'moscow': len([f for f in found if f['city'] == 'Москва'])
    }
    
    total_found = stats['excellent'] + stats['good'] + stats['fair'] + stats['poor']
    
    print(f"\n{'='*60}")
    print("ПОИСК МОСКОВСКИХ ПИЦЦЕРИЙ ЗАВЕРШЕН!")
    print(f"{'='*60}")
    print(f"Обработано: {len(found)} из {len(pizzerias)} пиццерий")
    print(f"Найдено групп: {total_found}")
    print(f"Из них московских: {stats['moscow']}")
    print(f"\nКачество поиска:")
    print(f"  Отличные совпадения: {stats['excellent']}")
    print(f"  Хорошие совпадения: {stats['good']}")
    print(f"  Удовлетворительные: {stats['fair']}")
    print(f"  Слабые совпадения: {stats['poor']}")
    print(f"  Не найдено: {stats['not_found']}")
    print(f"  Ошибок: {stats['error']}")
    print(f"\nУспешность: {total_found/len(pizzerias)*100:.1f}%")
    print(f"Московских найдено: {stats['moscow']/len(pizzerias)*100:.1f}%")
    print(f"\nРезультаты сохранены в:")
    print("- pizza_links_moscow.json")
    print("- pizza_links_moscow.csv")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()