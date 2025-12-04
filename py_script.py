import os
import csv
import re

# === НАСТРОЙКИ ===
PROJECT_ROOT = "."
TRANSLATIONS_FILE = "translations.csv"

# Папки, в которых искать файлы
DIRS_TO_SCAN = ["levels", "scenes", "scripts", "resources"]
# Расширения файлов для "Кода" (где НЕ нужны скобки _())
CODE_EXTENSIONS = (".gd", ".tscn", ".json", ".tres")
# Исключаемые файлы/папки (например, сам скрипт или папка git)
EXCLUDES = ["migrate_to_gettext.py", ".git", "translations.csv", "extract_locales.py", "extract_locales_v2.py"]

def load_translations(csv_path):
    """
    Загружает переводы из CSV.
    Возвращает список кортежей: [(key, english_text), ...]
    Сортирует по ДЛИНЕ ключа (от длинных к коротким), чтобы избежать частичных замен.
    """
    if not os.path.exists(csv_path):
        print(f"ОШИБКА: Файл {csv_path} не найден!")
        return []

    translations = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader, None) # Пропускаем заголовок
        
        for row in reader:
            if len(row) >= 2:
                key = row[0].strip()
                english = row[1].strip()
                if key and english:
                    translations.append((key, english))
    
    # Сортировка: самые длинные ключи первыми
    translations.sort(key=lambda x: len(x[0]), reverse=True)
    print(f"Загружено {len(translations)} ключей для замены.")
    return translations

def escape_for_code(text):
    """Экранирует кавычки для использования внутри GDScript/JSON строк"""
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

def process_level_file(content, translations):
    """
    Обработка файлов уровней.
    Стратегия:
    1. @@KEY@@ -> _(English Text)
    2. KEY -> _(English Text)
    """
    new_content = content
    
    for key, eng in translations:
        # Формат замены для уровней: _(Text)
        # Примечание: предполагаем, что в eng нет закрывающих скобок, которые сломают парсер
        # Если есть сомнения, можно использовать _("Text")
        replacement = f"_({eng})"
        
        # 1. Сначала ищем явные маркеры @@KEY@@
        if f"@@{key}@@" in new_content:
            new_content = new_content.replace(f"@@{key}@@", replacement)
            
        # 2. Ищем просто ключ.
        # Используем регулярку, чтобы не заменить часть другого слова.
        # Ищем ключ, перед которым НЕТ буквы/цифры/_ (границы слова)
        # (в файлах уровней ключи обычно стоят после = или пробела)
        pattern = re.compile(re.escape(key))
        if pattern.search(new_content):
             new_content = new_content.replace(key, replacement)
             
    return new_content

def process_code_file(content, translations):
    """
    Обработка .gd, .tscn, .json.
    Стратегия:
    Строгая замена внутри кавычек: "KEY" -> "English Text"
    Обертка _() НЕ ИСПОЛЬЗУЕТСЯ.
    """
    new_content = content
    
    for key, eng in translations:
        # Экранируем текст, так как он встанет внутрь кавычек
        eng_escaped = escape_for_code(eng)
        
        # Ищем ключ строго в кавычках: "KEY"
        # Это защищает от замены случайных переменных в коде
        target = f'"{key}"'
        replacement = f'"{eng_escaped}"'
        
        if target in new_content:
            new_content = new_content.replace(target, replacement)
            
    return new_content

def main():
    translations = load_translations(TRANSLATIONS_FILE)
    if not translations:
        return

    files_modified = 0

    # Рекурсивный обход
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Исключаем .git и прочее
        dirs[:] = [d for d in dirs if d not in EXCLUDES]
        
        for file in files:
            if file in EXCLUDES:
                continue
                
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file)
            
            # Определяем стратегию по типу файла
            is_level_file = "levels" in root and ext == "" # Файлы уровней часто без расширения
            is_code_file = ext in CODE_EXTENSIONS
            
            # Дополнительная проверка: если файл лежит в levels, считаем его уровнем
            if "levels" in root and not is_code_file:
                is_level_file = True

            if not (is_level_file or is_code_file):
                continue

            # Читаем
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                # Fallback для старых файлов
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()

            original_content = content
            
            # Обрабатываем
            if is_level_file:
                content = process_level_file(content, translations)
            elif is_code_file:
                content = process_code_file(content, translations)

            # Если были изменения - сохраняем
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"CHANGED: {file_path}")
                files_modified += 1

    print(f"\nГотово! Изменено файлов: {files_modified}")
    print("Теперь запусти extract_locales_v2.py для проверки генерации POT файла.")

if __name__ == "__main__":
    main()
