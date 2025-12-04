import os
import csv
import re

# === НАСТРОЙКИ ===
PROJECT_ROOT = "."
TRANSLATIONS_FILE = "translations.csv"

DIRS_TO_SCAN = ["levels", "scenes", "scripts", "resources"]
CODE_EXTENSIONS = (".gd", ".tscn", ".json", ".tres")
EXCLUDES = ["migrate_to_gettext.py", "migrate_to_gettext_v2.py", "migrate_to_gettext_v3.py", ".git", "translations.csv", "extract_locales.py"]

def load_translations(csv_path):
    if not os.path.exists(csv_path):
        print(f"ОШИБКА: Файл {csv_path} не найден!")
        return []

    translations = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        for row in reader:
            if len(row) >= 2:
                key = row[0].strip()
                english = row[1].strip()
                if key and english:
                    translations.append((key, english))
    
    # Сортируем по длине ключа (от длинных к коротким), чтобы избежать наложения
    translations.sort(key=lambda x: len(x[0]), reverse=True)
    return translations

def escape_for_code(text):
    """Экранирование для вставки внутрь строкового литерала кода (GDScript/JSON)"""
    return text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

def process_level_file(content, translations):
    new_content = content
    
    for key, eng in translations:
        # Подготовка текста замены
        # Если в английском тексте есть кавычки, их надо экранировать, 
        # так как в echo мы будем оборачивать текст в кавычки.
        eng_safe = eng.replace('"', '\\"')
        
        replacement_normal = f"_({eng})"       # Обычная замена: _(Text)
        replacement_quoted = f'"_({eng_safe})"' # Замена в кавычках: "_(Text)"
        
        # Экранируем ключ для использования в regex
        key_esc = re.escape(key)

        # 1. СИТУАЦИЯ: echo @@KEY@@ (без кавычек) -> echo "_(Text)"
        # Мы добавляем кавычки, чтобы shell не падал.
        # Ищем echo, пробелы, @@KEY@@ (и проверяем, что кавычек нет)
        pattern_echo_bare = re.compile(rf'(echo\s+)@@{key_esc}@@')
        # Используем lambda, чтобы избежать ошибки bad escape \o
        new_content = pattern_echo_bare.sub(lambda m: f'{m.group(1)}{replacement_quoted}', new_content)

        # 2. СИТУАЦИЯ: "@@KEY@@" (уже в кавычках) -> "_(Text)"
        # Мы просто меняем внутренность, кавычки остаются от файла.
        # replace безопаснее regex и работает быстрее
        new_content = new_content.replace(f'"@@{key}@@"', replacement_quoted)

        # 3. СИТУАЦИЯ: @@KEY@@ (остальные случаи, например title = @@KEY@@) -> _(Text)
        new_content = new_content.replace(f"@@{key}@@", replacement_normal)

        # 4. СИТУАЦИЯ: Голый ключ KEY -> _(Text)
        # Ищем границы слова \b, чтобы не заменить подстроку
        pattern_bare = re.compile(rf'\b{key_esc}\b')
        new_content = pattern_bare.sub(lambda m: replacement_normal, new_content)
             
    return new_content

def process_code_file(content, translations):
    """Обработка кода (.gd, .tscn, .json). Здесь _() НЕ НУЖНЫ."""
    new_content = content
    for key, eng in translations:
        eng_escaped = escape_for_code(eng)
        
        # Строгая замена ключа в кавычках: "KEY" -> "English Text"
        target = f'"{key}"'
        replacement = f'"{eng_escaped}"'
        
        if target in new_content:
            new_content = new_content.replace(target, replacement)
    return new_content

def main():
    print("Загрузка переводов...")
    translations = load_translations(TRANSLATIONS_FILE)
    if not translations: return

    files_modified = 0

    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in EXCLUDES]
        
        for file in files:
            if file in EXCLUDES: continue
            
            file_path = os.path.join(root, file)
            _, ext = os.path.splitext(file)
            
            # Определение типа файла
            is_level_file = "levels" in root and ext == ""
            is_code_file = ext in CODE_EXTENSIONS
            # Если файл в levels имеет расширение .txt или без расширения - считаем уровнем
            if "levels" in root and not is_code_file: 
                is_level_file = True

            if not (is_level_file or is_code_file): continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f: content = f.read()
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='latin-1') as f: content = f.read()

            original = content
            
            if is_level_file:
                content = process_level_file(content, translations)
            elif is_code_file:
                content = process_code_file(content, translations)

            if content != original:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"CHANGED: {file_path}")
                files_modified += 1

    print(f"\nГотово! Изменено файлов: {files_modified}")

if __name__ == "__main__":
    main()
