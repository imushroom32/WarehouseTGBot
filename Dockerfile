# Базовый образ с Python 3.11
FROM python:3.11-slim

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем pipenv
RUN pip install pipenv

# Копируем только Pipfile (и lock при наличии) и устанавливаем зависимости
WORKDIR /app
COPY Pipfile Pipfile.lock* ./
RUN pipenv install --system --deploy

# Копируем остальной проект
COPY . .

# Указываем рабочую директорию
WORKDIR /app

# Точка входа
CMD ["python", "-m", "bot.main"]

