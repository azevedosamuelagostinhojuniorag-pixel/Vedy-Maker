from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import anthropic
import subprocess
import os
import uuid
import json
import shutil
from pathlib import Path

app = FastAPI(title="VideoAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM_PROMPT = """Você é um assistente especialista em edição de vídeo usando FFmpeg.
O usuário vai descrever em linguagem natural o que quer fazer com um vídeo.
Você deve retornar APENAS um JSON válido (sem markdown, sem explicações) com esta estrutura:

{
  "action": "nome_da_acao",
  "description": "descrição do que será feito",
  "ffmpeg_args": ["lista", "de", "argumentos", "ffmpeg"],
  "output_extension": "mp4"
}

Ações disponíveis:
- cut: cortar trecho (usa -ss e -to)
- join: juntar vídeos (usa concat)
- add_audio: adicionar música/áudio
- remove_bg_color: remover fundo colorido (chroma key)
- enhance: melhorar qualidade (upscale, nitidez)
- add_effect: adicionar efeito (preto e branco, vintage, brilho, contraste)
- add_subtitles: adicionar legendas
- speed: alterar velocidade
- volume: ajustar volume
- crop: recortar vídeo
- rotate: rotacionar vídeo
- mute: remover áudio

Para os ffmpeg_args, use {input} como placeholder para o arquivo de entrada e {output} para o de saída.
Para join, use {input0}, {input1}, etc.

Exemplos de ffmpeg_args:
- cut de 10s a 30s: ["-i", "{input}", "-ss", "10", "-to", "30", "-c", "copy", "{output}"]
- preto e branco: ["-i", "{input}", "-vf", "hue=s=0", "{output}"]
- velocidade 2x: ["-i", "{input}", "-vf", "setpts=0.5*PTS", "-af", "atempo=2.0", "{output}"]
- nitidez: ["-i", "{input}", "-vf", "unsharp=5:5:1.5:5:5:0.0", "{output}"]
- brilho e contraste: ["-i", "{input}", "-vf", "eq=brightness=0.1:contrast=1.3", "{output}"]
- vintage: ["-i", "{input}", "-vf", "curves=vintage,hue=s=0.6", "{output}"]
"""

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/interpret")
async def interpret_command(command: str = Form(...)):
    """Interpreta um comando em linguagem natural e retorna a ação FFmpeg."""
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": command}]
    )
    
    try:
        result = json.loads(message.content[0].text)
        return JSONResponse(result)
    except:
        return JSONResponse({"error": "Não consegui interpretar o comando. Tente ser mais específico."}, status_code=400)

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """Faz upload de um vídeo."""
    file_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix
    file_path = UPLOAD_DIR / f"{file_id}{ext}"
    
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    return {"file_id": f"{file_id}{ext}", "filename": file.filename}

@app.post("/process")
async def process_video(
    file_ids: str = Form(...),
    command: str = Form(...)
):
    """Processa um vídeo com base no comando em linguagem natural."""
    
    # Interpreta o comando
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": command}]
    )
    
    try:
        action_data = json.loads(message.content[0].text)
    except:
        return JSONResponse({"error": "Não consegui interpretar o comando."}, status_code=400)
    
    ids = json.loads(file_ids)
    output_id = str(uuid.uuid4())
    output_ext = action_data.get("output_extension", "mp4")
    output_path = OUTPUT_DIR / f"{output_id}.{output_ext}"
    
    # Substitui placeholders nos args
    ffmpeg_args = action_data.get("ffmpeg_args", [])
    processed_args = []
    for arg in ffmpeg_args:
        if arg == "{input}" and len(ids) > 0:
            arg = str(UPLOAD_DIR / ids[0])
        elif arg == "{output}":
            arg = str(output_path)
        else:
            for i, fid in enumerate(ids):
                arg = arg.replace(f"{{input{i}}}", str(UPLOAD_DIR / fid))
        processed_args.append(arg)
    
    # Executa FFmpeg
    cmd = ["ffmpeg", "-y"] + processed_args
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            return JSONResponse({
                "error": f"Erro no processamento: {result.stderr[-500:]}"
            }, status_code=500)
    except subprocess.TimeoutExpired:
        return JSONResponse({"error": "Tempo limite excedido."}, status_code=500)
    except FileNotFoundError:
        return JSONResponse({"error": "FFmpeg não encontrado. Instale com: sudo apt install ffmpeg"}, status_code=500)
    
    return {
        "output_id": f"{output_id}.{output_ext}",
        "description": action_data.get("description", "Processamento concluído"),
        "action": action_data.get("action")
    }

@app.get("/download/{output_id}")
async def download(output_id: str):
    """Baixa o vídeo processado."""
    path = OUTPUT_DIR / output_id
    if not path.exists():
        return JSONResponse({"error": "Arquivo não encontrado"}, status_code=404)
    return FileResponse(path, media_type="video/mp4", filename=output_id)

@app.post("/transcribe")
async def transcribe(file_id: str = Form(...)):
    """Gera legendas usando Whisper."""
    try:
        import whisper
        model = whisper.load_model("base")
        file_path = UPLOAD_DIR / file_id
        result = model.transcribe(str(file_path), language="pt")
        
        # Gera arquivo SRT
        srt_id = str(uuid.uuid4())
        srt_path = OUTPUT_DIR / f"{srt_id}.srt"
        
        with open(srt_path, "w", encoding="utf-8") as f:
            for i, segment in enumerate(result["segments"]):
                start = format_time(segment["start"])
                end = format_time(segment["end"])
                f.write(f"{i+1}\n{start} --> {end}\n{segment['text'].strip()}\n\n")
        
        return {"srt_id": f"{srt_id}.srt", "text": result["text"]}
    except ImportError:
        return JSONResponse({"error": "Whisper não instalado. Execute: pip install openai-whisper"}, status_code=500)

def format_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
