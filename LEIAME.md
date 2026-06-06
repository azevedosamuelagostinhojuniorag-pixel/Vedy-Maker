# VideoAI — Guia de Instalação e Uso

## Pré-requisitos

- Python 3.10+
- FFmpeg instalado
- Chave da API Anthropic

---

## 1. Instalar FFmpeg

**Windows:**
```
winget install ffmpeg
```
ou baixe em: https://ffmpeg.org/download.html

**Mac:**
```
brew install ffmpeg
```

**Linux:**
```
sudo apt install ffmpeg
```

---

## 2. Instalar dependências Python

```bash
cd backend
pip install -r requirements.txt
```

> ⚠️ O Whisper (legendas automáticas) pode demorar para instalar pois baixa o PyTorch.
> Se quiser pular por agora: `pip install fastapi uvicorn anthropic python-multipart`

---

## 3. Configurar a chave da API

**Windows (PowerShell):**
```powershell
$env:ANTHROPIC_API_KEY = "sua_chave_aqui"
```

**Mac/Linux:**
```bash
export ANTHROPIC_API_KEY="sua_chave_aqui"
```

Pegue sua chave em: https://console.anthropic.com

---

## 4. Iniciar o backend

```bash
cd backend
python main.py
```

O servidor vai iniciar em: http://localhost:8000

---

## 5. Abrir a interface

Abra o arquivo `frontend/index.html` no navegador.

O campo "Servidor Backend" já vem preenchido com `http://localhost:8000`.
Clique em **Testar Conexão** para confirmar que está funcionando.

---

## Como usar

1. **Adicione um vídeo** — arraste ou clique na área de upload
2. **Digite o que quer fazer** — em português, naturalmente
3. **Clique em Processar** — a IA interpreta e executa

### Exemplos de comandos:
- "Corta o vídeo do segundo 10 até o minuto 2"
- "Deixa em preto e branco com efeito vintage"
- "Acelera o vídeo para o dobro da velocidade"
- "Melhora a nitidez e o contraste"
- "Remove o áudio do vídeo"
- "Adiciona o segundo arquivo como trilha sonora"
- "Rotaciona 90 graus para a direita"

---

## Hospedar no Render (opcional)

1. Crie conta em https://render.com
2. Suba o código no GitHub
3. Crie um "Web Service" apontando para a pasta `backend`
4. Adicione a variável de ambiente `ANTHROPIC_API_KEY`
5. Use a URL gerada pelo Render na interface

---

## Estrutura do projeto

```
videoai/
├── backend/
│   ├── main.py          ← API FastAPI
│   ├── requirements.txt ← Dependências
│   └── uploads/         ← Vídeos enviados (criado automaticamente)
│   └── outputs/         ← Vídeos processados (criado automaticamente)
└── frontend/
    └── index.html       ← Interface web
```
