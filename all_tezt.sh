### Скрипт `Делаем файл для ChatGPT`

#!/bin/bash
# Скрипт объединяет файлы из list.txt в один файл all_text.md
# Форматирует содержимое с разделителями и подсветкой синтаксиса

# Очистим файл результата
> all_text.md

# Функция для определения языка по расширению
get_lang() {
  case "$1" in
    *.html) echo "html" ;;
    *.htm)  echo "html" ;;
    *.css)  echo "css" ;;
    *.js)   echo "javascript" ;;
    *.ts)   echo "typescript" ;;
    *.py)   echo "python" ;;
    *.sh)   echo "bash" ;;
    *.json) echo "json" ;;
    *.yml|*.yaml) echo "yaml" ;;
    *.xml)  echo "xml" ;;
    *.php)  echo "php" ;;
    *.java) echo "java" ;;
    *.c)    echo "c" ;;
    *.cpp|*.cc|*.cxx) echo "cpp" ;;
    *.md)   echo "markdown" ;;
    *)      echo "txt" ;; # по умолчанию
  esac
}

while read file; do
  lang=$(get_lang "$file")

  echo -e "=== FILE START: $file ===" >> all_text.md
  echo -e "\`\`\`$lang" >> all_text.md
  cat "$file" >> all_text.md
  echo -e "\`\`\`" >> all_text.md
  echo -e "=== FILE END: $file ===\n" >> all_text.md
done < list.txt
