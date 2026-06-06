from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import google.generativeai as genai
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

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-1.5-flash")

SYSTEM_PROMPT = """Você é um assistente especialista em edição de vídeo usando FFmpeg. O usuário vai descrever em linguagem natural o que quer fazer com um vídeo. Retorne APENAS um JSON válido sem markdown:

{
  "action": "nome_da_acao",
  "description": "descrição do que será feito",
  "ffmpeg_args": ["lista", "de", "argumentos", "ffmpeg"],
  "output_extension": "mp4"
}

Use {input} para o arquivo de entrada e {output} para o de saída.
Exemplos:
- cortar 10s a 30s: ["-i", "{input}", "-ss", "10", "-to", "30", "-c", "copy", "{output}"]
- preto e branco: ["-i", "{input}", "-vf", "hue=s=0", "{output}"]
- velocidade 2x: ["-i", "{input}", "-vf", "setpts=0.5*PTS", "-af", "atempo=2.0", "{output}"]
- nitidez: ["-i", "{input}", "-vf", "unsharp=5:5:1.5:5:5:0.0", "{output}"]
- vintage: ["-i", "{input}", "-vf", "curves=vintage,hue=s=0.6", "{output}"]
- remover audio: ["-i", "{input}", "-an", "{output}"]
"""

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    ext = Path(file.filename).suffix
    file_path = UPLOAD_DIR / f"{file_id}{ext}"
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"file_id": f"{file_id}{ext}", "filename": file.filename}

@app.post("/process")
async def process_video(file_ids: str = Form(...), command: str = Form(...)):
    try:
        response = model.generate_content(SYSTEM_PROMPT + "\n\nComando: " + command)
        text = response.text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        action_data = json.loads(text.strip())
    except Exception as e:
        return JSONResponse({"error": f"Erro ao interpretar: {str(e)}"}, status_code=400)

    ids = json.loads(file_ids)
    output_id = str(uuid.uuid4())
    output_ext = action_data.get("output_extension", "mp4")
    output_path = OUTPUT_DIR / f"{output_id}.{output_ext}"

    ffmpeg_args = action_data.get("ffmpeg_args", [])
    processed_args = []
    for arg in ffmpeg_args:
        if arg == "{input}" and len(ids) > 0:
            arg = str(UPLOAD_DIR / ids[0])
        elif arg == "{output}":
            arg = str(output_path)
        processed_args.append(arg)

    cmd = ["ffmpeg", "-y"] + processed_args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            return JSONResponse({"error": f"Erro FFmpeg: {result.stderr[-300:]}"}, status_code=500)
    except FileNotFoundError:
        return JSONResponse({"error": "FFmpeg não encontrado."}, status_code=500)
    except subprocess.TimeoutExpired:
        return JSONResponse({"error": "Tempo limite excedido."}, status_code=500)

    return {
        "output_id": f"{output_id}.{output_ext}",
        "description": action_data.get("description", "Concluído"),
        "action": action_data.get("action")
    }

@app.get("/download/{output_id}")
async def download(output_id: str):
    path = OUTPUT_DIR / output_id
    if not path.exists():
        return JSONResponse({"error": "Não encontrado"}, status_code=404)
    return FileResponse(path, media_type="video/mp4", filename=output_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))