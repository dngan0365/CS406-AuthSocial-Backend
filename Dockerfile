FROM python:3.12

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV TORCH_HOME=/app/.torch
ENV HF_HOME=/app/.hf

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
