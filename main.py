from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from google import genai
from docx import Document
from dotenv import load_dotenv
import mercadopago
import pdfplumber
import io
import json
import httpx
from bs4 import BeautifulSoup
import urllib.parse
import asyncio
import os
import re
import sqlite3
from datetime import datetime
import smtplib
import random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# ============================================================
# CONFIGURAÇÕES
# ============================================================
load_dotenv()

CHAVE_API_GOOGLE = os.getenv("GOOGLE_API_KEY")
MP_ACCESS_TOKEN  = os.getenv("MP_ACCESS_TOKEN")
GMAIL_EMAIL      = os.getenv("GMAIL_EMAIL")
GMAIL_SENHA      = os.getenv("GMAIL_SENHA")
# URL base do site — muda para a URL real quando hospedar
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:8000")

if not CHAVE_API_GOOGLE:
    raise RuntimeError("❌ GOOGLE_API_KEY não encontrada no .env!")
if not MP_ACCESS_TOKEN:
    raise RuntimeError("❌ MP_ACCESS_TOKEN não encontrada no .env!")

client_ia = genai.Client(api_key=CHAVE_API_GOOGLE)
sdk_mp    = mercadopago.SDK(MP_ACCESS_TOKEN)
print(f"✅ Configurações carregadas. BASE_URL={BASE_URL}")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(title="VagaCerta AI - API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# BANCO DE DADOS
# ============================================================
DB_PATH = os.path.join(BASE_DIR, "vagacerta.db")

def iniciar_banco():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            email              TEXT UNIQUE NOT NULL,
            email_verificado   INTEGER DEFAULT 0,
            buscas_usadas      INTEGER DEFAULT 0,
            buscas_pagas       INTEGER DEFAULT 0,
            codigo_verificacao TEXT,
            criado_em          TEXT DEFAULT CURRENT_TIMESTAMP,
            ultima_busca       TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("✅ Banco de dados iniciado.")

iniciar_banco()

def buscar_usuario(email: str):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM usuarios WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def criar_ou_atualizar_usuario(email: str, codigo: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO usuarios (email, codigo_verificacao, email_verificado, buscas_usadas, buscas_pagas)
        VALUES (?, ?, 0, 0, 0)
        ON CONFLICT(email) DO UPDATE SET codigo_verificacao = ?
    """, (email, codigo, codigo))
    conn.commit()
    conn.close()

def verificar_codigo_db(email: str, codigo: str) -> bool:
    usuario = buscar_usuario(email)
    return usuario is not None and usuario.get("codigo_verificacao") == codigo

def marcar_email_verificado(email: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET email_verificado = 1, codigo_verificacao = NULL WHERE email = ?", (email,))
    conn.commit()
    conn.close()

def registrar_busca(email: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE usuarios SET buscas_usadas = buscas_usadas + 1, ultima_busca = ? WHERE email = ?",
        (datetime.now().isoformat(), email)
    )
    conn.commit()
    conn.close()

def adicionar_busca_paga(email: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE usuarios SET buscas_pagas = buscas_pagas + 1 WHERE email = ?", (email,))
    conn.commit()
    conn.close()

def usuario_pode_buscar(email: str) -> tuple:
    usuario = buscar_usuario(email)
    if not usuario:
        return False, "email_nao_verificado"
    if not usuario.get("email_verificado"):
        return False, "email_nao_verificado"
    total_permitido = 1 + usuario.get("buscas_pagas", 0)
    if usuario.get("buscas_usadas", 0) < total_permitido:
        return True, "busca_disponivel"
    return False, "limite_atingido"

# ============================================================
# ENVIO DE EMAILS
# ============================================================
def enviar_email(destinatario: str, assunto: str, corpo_html: str) -> bool:
    if not GMAIL_EMAIL or not GMAIL_SENHA:
        print("⚠️  Gmail não configurado.")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = assunto
        msg["From"]    = f"VagaCerta AI <{GMAIL_EMAIL}>"
        msg["To"]      = destinatario
        msg.attach(MIMEText(corpo_html, "html", "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(GMAIL_EMAIL, GMAIL_SENHA)
            smtp.sendmail(GMAIL_EMAIL, destinatario, msg.as_string())
        print(f"📧 Email enviado para: {destinatario}")
        return True
    except Exception as e:
        print(f"❌ Erro ao enviar email: {e}")
        return False

def email_codigo_verificacao(destinatario: str, codigo: str) -> bool:
    assunto = "🔐 Seu código de verificação - VagaCerta AI"
    corpo = f"""
    <div style="font-family:Inter,Arial,sans-serif;max-width:500px;margin:0 auto;padding:32px;background:#F4F6FB;border-radius:16px;">
        <div style="text-align:center;margin-bottom:24px;">
            <h1 style="color:#4F46E5;font-size:1.8rem;margin:0;">🧠 VagaCerta AI</h1>
        </div>
        <div style="background:#fff;border-radius:12px;padding:32px;text-align:center;">
            <h2 style="font-size:1.3rem;color:#0F172A;margin-bottom:8px;">Confirme seu email</h2>
            <p style="color:#64748B;margin-bottom:24px;">Use o código abaixo para verificar sua conta e acessar sua busca gratuita:</p>
            <div style="background:#EEF2FF;border:2px dashed #4F46E5;border-radius:12px;padding:24px;margin-bottom:24px;">
                <span style="font-size:2.5rem;font-weight:800;color:#4F46E5;letter-spacing:8px;">{codigo}</span>
            </div>
            <p style="color:#64748B;font-size:0.85rem;">Este código expira em 10 minutos.<br>Se você não solicitou isso, ignore este email.</p>
        </div>
        <p style="text-align:center;color:#94A3B8;font-size:0.75rem;margin-top:16px;">© 2026 VagaCerta AI</p>
    </div>"""
    return enviar_email(destinatario, assunto, corpo)

def email_boas_vindas_com_vagas(destinatario: str, nome: str, cargo: str, vagas: list) -> bool:
    assunto = f"🎯 {len(vagas)} vagas encontradas para você - VagaCerta AI"
    cards = ""
    for i, v in enumerate(vagas[:5]):
        cor = "#4F46E5" if i < 3 else "#94A3B8"
        cards += f"""
        <div style="background:#fff;border:1px solid #E2E8F0;border-radius:12px;padding:20px;margin-bottom:12px;">
            <h3 style="font-size:1rem;font-weight:700;color:#0F172A;margin:0 0 4px;">{v.get('titulo','')}</h3>
            <p style="color:#64748B;font-size:0.88rem;margin:0 0 4px;">{v.get('empresa','')}</p>
            <p style="color:#94A3B8;font-size:0.8rem;margin:0 0 12px;">📍 {v.get('local','Remoto')}</p>
            <a href="{v.get('link','#')}" style="display:block;text-align:center;background:{cor};color:white;padding:10px;border-radius:8px;font-weight:600;font-size:0.9rem;text-decoration:none;">Ver Vaga →</a>
        </div>"""
    corpo = f"""
    <div style="font-family:Inter,Arial,sans-serif;max-width:600px;margin:0 auto;padding:32px;background:#F4F6FB;">
        <div style="text-align:center;margin-bottom:24px;">
            <h1 style="color:#4F46E5;font-size:1.8rem;margin:0;">🧠 VagaCerta AI</h1>
        </div>
        <div style="background:#fff;border-radius:12px;padding:32px;margin-bottom:16px;">
            <h2 style="font-size:1.3rem;color:#0F172A;margin-bottom:8px;">Olá, {nome.split()[0] if nome else 'candidato'}! 👋</h2>
            <p style="color:#64748B;margin-bottom:24px;">Encontramos <strong>{len(vagas)} vagas</strong> compatíveis com seu perfil de <strong>{cargo}</strong>:</p>
            {cards}
        </div>
        <div style="background:#EEF2FF;border-radius:12px;padding:20px;text-align:center;margin-bottom:16px;">
            <p style="color:#4F46E5;font-weight:600;margin:0 0 12px;">🔒 {max(0,len(vagas)-3)} vagas ainda bloqueadas</p>
            <a href="{BASE_URL}" style="background:#10B981;color:white;padding:12px 24px;border-radius:50px;font-weight:700;text-decoration:none;font-size:0.95rem;">Desbloquear por R$ 15,00</a>
        </div>
        <p style="text-align:center;color:#94A3B8;font-size:0.75rem;">© 2026 VagaCerta AI | Desenvolvido por Johnny Marcos</p>
    </div>"""
    return enviar_email(destinatario, assunto, corpo)

# ============================================================
# SERVE O FRONTEND
# ============================================================
@app.get("/")
def servir_frontend():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))

# ============================================================
# AUTENTICAÇÃO
# ============================================================
class EmailInput(BaseModel):
    email: str

@app.post("/api/enviar-codigo")
def enviar_codigo(body: EmailInput):
    email = body.email.strip().lower()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="Email inválido.")
    usuario = buscar_usuario(email)
    if usuario and usuario.get("email_verificado"):
        pode, motivo = usuario_pode_buscar(email)
        if motivo == "limite_atingido":
            return {"status": "limite_atingido"}
        return {"status": "ja_verificado"}
    codigo = str(random.randint(100000, 999999))
    criar_ou_atualizar_usuario(email, codigo)
    enviado = email_codigo_verificacao(email, codigo)
    if not enviado:
        raise HTTPException(status_code=500, detail="Erro ao enviar email. Verifique GMAIL_EMAIL e GMAIL_SENHA no .env")
    return {"status": "codigo_enviado"}

class CodigoInput(BaseModel):
    email: str
    codigo: str

@app.post("/api/verificar-codigo")
def verificar_codigo(body: CodigoInput):
    email  = body.email.strip().lower()
    codigo = body.codigo.strip()
    if not verificar_codigo_db(email, codigo):
        raise HTTPException(status_code=400, detail="Código inválido.")
    marcar_email_verificado(email)
    return {"status": "verificado"}

# ============================================================
# PAGAMENTO MERCADO PAGO
# ============================================================
class PagamentoInput(BaseModel):
    email: str

@app.post("/api/criar-pagamento")
def criar_pagamento(body: PagamentoInput):
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Email inválido.")

    preference_data = {
        "items": [{
            "title": "VagaCerta AI - Busca Aprofundada de Vagas",
            "quantity": 1,
            "currency_id": "BRL",
            "unit_price": 1.00,
        }],
        "payer": {"email": email},
        "back_urls": {
            "success": f"{BASE_URL}/pagamento/sucesso?email={urllib.parse.quote(email)}",
            "failure": f"{BASE_URL}/pagamento/falha?email={urllib.parse.quote(email)}",
            "pending": f"{BASE_URL}/pagamento/pendente?email={urllib.parse.quote(email)}",
        },
        "statement_descriptor": "VagaCerta AI",
        "external_reference": email,
    }

    resultado = sdk_mp.preference().create(preference_data)
    print(f"MP status: {resultado['status']}")

    if resultado["status"] == 201:
        link = resultado["response"]["init_point"]
        print(f"✅ Pagamento criado para {email}")
        return {"status": "sucesso", "link_pagamento": link}
    else:
        print(f"❌ Erro MP: {resultado}")
        raise HTTPException(status_code=500, detail=f"Erro ao criar pagamento: {resultado['response']}")

@app.get("/pagamento/sucesso")
def pagamento_sucesso(email: str = ""):
    if email:
        adicionar_busca_paga(email.strip().lower())
        print(f"✅ Busca liberada: {email}")
    return RedirectResponse(url=f"/?pagamento=sucesso&email={urllib.parse.quote(email)}")

@app.get("/pagamento/falha")
def pagamento_falha(email: str = ""):
    return RedirectResponse(url=f"/?pagamento=falha&email={urllib.parse.quote(email)}")

@app.get("/pagamento/pendente")
def pagamento_pendente(email: str = ""):
    return RedirectResponse(url=f"/?pagamento=pendente&email={urllib.parse.quote(email)}")

@app.post("/api/webhook-mp")
async def webhook_mp(request: Request):
    try:
        data = await request.json()
        if data.get("type") == "payment":
            pid = data["data"]["id"]
            pag = sdk_mp.payment().get(pid)
            if pag["status"] == 200:
                info = pag["response"]
                if info.get("status") == "approved":
                    ref = info.get("external_reference", "")
                    if ref:
                        adicionar_busca_paga(ref)
                        print(f"✅ Webhook: busca liberada para {ref}")
    except Exception as e:
        print(f"⚠️ Webhook erro: {e}")
    return {"status": "ok"}

# ============================================================
# SIMPLIFICAÇÃO DO CARGO E CIDADE
# ============================================================
def simplificar_cargo(cargo: str) -> str:
    cargo = cargo.strip()
    for nivel in ["sênior","senior","júnior","junior","pleno","trainee","estagiário","estágio"]:
        cargo = re.sub(nivel, "", cargo, flags=re.IGNORECASE).strip()
    if " e " in cargo.lower():
        partes = re.split(r"\s+e\s+", cargo, flags=re.IGNORECASE)
        cargo = partes[-1].strip()
    cargo = re.sub(r"^de\s+", "", cargo, flags=re.IGNORECASE).strip()
    return cargo

def cidade_para_busca(cidade: str) -> list:
    if not cidade: return ["Brasil"]
    cidade_lower = cidade.lower()
    cidade_principal = cidade.split(",")[0].strip()
    fallbacks = {
        "barbacena":["Belo Horizonte"],"juiz de fora":["Belo Horizonte"],
        "uberlândia":["Belo Horizonte"],"montes claros":["Belo Horizonte"],
        "sorocaba":["São Paulo"],"ribeirão preto":["São Paulo"],
        "guarulhos":["São Paulo"],"niterói":["Rio de Janeiro"],
        "contagem":["Belo Horizonte"],"betim":["Belo Horizonte"],
        "canoas":["Porto Alegre"],"caxias do sul":["Porto Alegre"],
        "caruaru":["Recife"],"feira de santana":["Salvador"],
        "caucaia":["Fortaleza"],"aparecida de goiânia":["Goiânia"],
    }
    capitais = ["são paulo","rio de janeiro","belo horizonte","brasília","porto alegre","curitiba","recife","fortaleza","salvador","manaus","belém","goiânia","florianópolis","natal","maceió","joão pessoa","teresina","campo grande","cuiabá","vitória"]
    if any(cap in cidade_lower for cap in capitais): return [cidade_principal]
    for chave, fb in fallbacks.items():
        if chave in cidade_lower: return [cidade_principal] + fb + ["Remoto"]
    estado = cidade.split(",")[-1].strip() if "," in cidade else ""
    resultado = [cidade_principal]
    if estado and estado != cidade_principal: resultado.append(estado)
    resultado.append("Remoto")
    return resultado

# ============================================================
# BUSCA DE VAGAS
# ============================================================
async def buscar_vagas_gupy(cargo, cidade):
    vagas = []
    try:
        url = f"https://portal.api.gupy.io/api/v1/jobs?jobName={urllib.parse.quote(cargo)}&city={urllib.parse.quote(cidade)}&limit=6"
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(url, headers={"User-Agent":"Mozilla/5.0"})
            if resp.status_code != 200: return []
            for job in resp.json().get("data",[])[:6]:
                vagas.append({"titulo":job.get("name","Vaga sem título"),"empresa":job.get("company",{}).get("name","Empresa não informada"),"local":f"{job.get('city','')}, {job.get('state','')}".strip(", "),"link":job.get("jobUrl","https://portal.gupy.io"),"portal":"Gupy"})
    except Exception as e: print(f"⚠️ Gupy: {e}")
    return vagas

async def buscar_vagas_gupy_remoto(cargo):
    vagas = []
    try:
        url = f"https://portal.api.gupy.io/api/v1/jobs?jobName={urllib.parse.quote(cargo)}&workplaceType=remote&limit=6"
        async with httpx.AsyncClient(timeout=15) as c:
            resp = await c.get(url, headers={"User-Agent":"Mozilla/5.0"})
            if resp.status_code != 200: return []
            for job in resp.json().get("data",[])[:6]:
                vagas.append({"titulo":job.get("name","Vaga sem título"),"empresa":job.get("company",{}).get("name","Empresa não informada"),"local":"Remoto","link":job.get("jobUrl","https://portal.gupy.io"),"portal":"Gupy"})
    except Exception as e: print(f"⚠️ Gupy remoto: {e}")
    return vagas

async def buscar_vagas_linkedin(cargo, cidade):
    vagas = []
    try:
        url = f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(cargo)}&location={urllib.parse.quote(cidade)}&f_TPR=r604800"
        headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36","Accept-Language":"pt-BR,pt;q=0.9"}
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            resp = await c.get(url, headers=headers)
            if resp.status_code != 200: return []
            soup = BeautifulSoup(resp.text,"html.parser")
            for card in soup.select("div.base-card")[:6]:
                t=card.select_one(".base-search-card__title"); e=card.select_one(".base-search-card__subtitle"); l=card.select_one(".job-search-card__location"); a=card.select_one("a.base-card__full-link")
                if t: vagas.append({"titulo":t.get_text(strip=True),"empresa":e.get_text(strip=True) if e else "Empresa não informada","local":l.get_text(strip=True) if l else cidade,"link":a["href"] if a else url,"portal":"LinkedIn"})
    except Exception as e: print(f"⚠️ LinkedIn: {e}")
    return vagas

async def buscar_vagas_infojobs(cargo, cidade):
    vagas = []
    try:
        url = f"https://www.infojobs.com.br/empregos.aspx?palabra={urllib.parse.quote(cargo)}&ciudad={urllib.parse.quote(cidade.split(',')[0].strip())}"
        headers = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36","Accept-Language":"pt-BR,pt;q=0.9"}
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as c:
            resp = await c.get(url, headers=headers)
            if resp.status_code != 200: return []
            soup = BeautifulSoup(resp.text,"html.parser")
            for card in soup.select("li.ij-OfferList-item")[:6]:
                t=card.select_one("h2 a, .ij-OfferList-item-title a"); em=card.select_one(".ij-OfferList-item-subtitle span, .company"); lo=card.select_one(".ij-OfferList-item-location, .location"); li=card.select_one("h2 a, .ij-OfferList-item-title a")
                if t:
                    href = li["href"] if li else url
                    vagas.append({"titulo":t.get_text(strip=True),"empresa":em.get_text(strip=True) if em else "Empresa não informada","local":lo.get_text(strip=True) if lo else cidade,"link":("https://www.infojobs.com.br"+href) if href.startswith("/") else href,"portal":"InfoJobs"})
    except Exception as e: print(f"⚠️ InfoJobs: {e}")
    return vagas

async def buscar_todas_vagas(cargo_original, cidade_original):
    cargo = simplificar_cargo(cargo_original)
    cidades = cidade_para_busca(cidade_original)
    print(f"   Cargo: '{cargo_original}' → '{cargo}' | Cidades: {cidades}")
    todas = []
    for cidade in cidades:
        if len(todas) >= 8: break
        resultados = await asyncio.gather(
            buscar_vagas_gupy(cargo,cidade),
            buscar_vagas_linkedin(cargo,cidade),
            buscar_vagas_infojobs(cargo,cidade),
            return_exceptions=True
        )
        for r in resultados:
            if isinstance(r, list): todas.extend(r)
    if len(todas) < 4: todas.extend(await buscar_vagas_gupy_remoto(cargo))
    vistos, unicas = set(), []
    for v in todas:
        chave = v["titulo"].lower()[:40]
        if chave not in vistos: vistos.add(chave); unicas.append(v)
    return unicas[:12]

# ============================================================
# ENDPOINT PRINCIPAL
# ============================================================
@app.post("/api/analisar-curriculo")
async def analisar_curriculo(file: UploadFile = File(...), email: str = Form(...)):
    email = email.strip().lower()
    print(f"\n📥 Arquivo: {file.filename} | Email: {email}")

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Email inválido.")

    pode, motivo = usuario_pode_buscar(email)
    if not pode:
        if motivo == "email_nao_verificado":
            return {"status": "erro", "mensagem": "Email não verificado."}
        return {"status": "limite_atingido", "mensagem": "Busca grátis já utilizada."}

    conteudo = await file.read()
    texto_extraido = ""
    try:
        if file.filename.lower().endswith(".pdf"):
            with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
                for pagina in pdf.pages:
                    t = pagina.extract_text()
                    if t: texto_extraido += t + "\n"
        elif file.filename.lower().endswith(".docx"):
            doc = Document(io.BytesIO(conteudo))
            for p in doc.paragraphs:
                if p.text.strip(): texto_extraido += p.text + "\n"
        else:
            return {"status": "erro", "mensagem": "Formato não suportado. Use PDF ou DOCX."}
        print("✅ Texto extraído.")
    except Exception as e:
        return {"status": "erro", "mensagem": "Não foi possível ler o arquivo."}

    if not texto_extraido.strip():
        return {"status": "erro", "mensagem": "O arquivo não contém texto legível."}

    try:
        prompt = f"""
Você é um recrutador sênior especialista em análise de currículos.
Responda SOMENTE com um objeto JSON válido, sem texto extra, sem markdown, sem blocos de código.
Formato exato:
{{
  "nome": "Nome completo do candidato",
  "cidade": "Cidade, Estado",
  "cargo_principal": "Cargo ou área principal (use termos simples, ex: 'Analista de Dados', 'Desenvolvedor Python')",
  "hard_skills": ["skill1", "skill2", "skill3", "skill4", "skill5"],
  "resumo": "Resumo profissional em 2 linhas"
}}
Texto do currículo:
{texto_extraido[:4000]}
"""
        resposta = client_ia.models.generate_content(model="gemini-2.5-flash", contents=prompt)
        texto_json = resposta.text.strip().replace("```json","").replace("```","").strip()
        dados = json.loads(texto_json)
        print(f"🤖 IA: {dados.get('nome')} | {dados.get('cargo_principal')}")
    except json.JSONDecodeError:
        return {"status": "erro", "mensagem": "A IA retornou formato inesperado. Tente novamente."}
    except Exception as e:
        return {"status": "erro", "mensagem": f"Erro na IA: {str(e)}"}

    registrar_busca(email)
    print(f"📧 Busca registrada: {email}")

    print(f"🔍 Buscando: {dados.get('cargo_principal')} | {dados.get('cidade')}")
    vagas = await buscar_todas_vagas(dados.get("cargo_principal",""), dados.get("cidade",""))
    print(f"✅ {len(vagas)} vagas encontradas.")

    asyncio.create_task(asyncio.to_thread(
        email_boas_vindas_com_vagas, email,
        dados.get("nome",""), dados.get("cargo_principal",""), vagas
    ))

    return {"status":"sucesso","arquivo":file.filename,"analise_ia":dados,"vagas":vagas}