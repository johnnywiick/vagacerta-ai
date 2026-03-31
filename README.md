# 🧠 VagaCerta AI — Seu Recrutador Pessoal com Inteligência Artificial

> A IA que caça a vaga perfeita para você em segundos.

![VagaCerta AI](https://img.shields.io/badge/Status-Em%20Produção-brightgreen)
![Python](https://img.shields.io/badge/Python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)
![Mercado Pago](https://img.shields.io/badge/Mercado%20Pago-Checkout%20Pro-yellow)

---

## 🚀 O que é o VagaCerta AI?

O **VagaCerta AI** é um SaaS (Software como Serviço) que usa **Inteligência Artificial** para analisar o currículo do usuário e buscar automaticamente as melhores vagas de emprego em múltiplos portais simultaneamente.

O usuário faz o upload do currículo, a IA extrai as informações do perfil e em segundos retorna as vagas mais compatíveis — com score de compatibilidade, localização e tipo de contrato.

---

## ✨ Funcionalidades

- 📄 **Leitura de currículo** em PDF ou Word (.docx)
- 🤖 **Análise com IA** (Google Gemini 2.5 Flash) — extrai nome, cargo, cidade e habilidades
- 🔍 **Busca em 4 portais simultâneos** — Gupy, LinkedIn, InfoJobs e Catho
- 📍 **Busca por localização** com fallback inteligente para capitais próximas e vagas remotas
- 🎯 **AI Match Score** — porcentagem de compatibilidade por vaga
- 🔒 **Vagas desbloqueáveis** — modelo freemium com 1ª busca grátis
- 📧 **Verificação de email** com código de 6 dígitos
- 💌 **Email automático** com as vagas encontradas após cada busca
- 💳 **Pagamento integrado** via Mercado Pago Checkout Pro (PIX, Cartão, Boleto)
- 🔐 **Autenticação segura** com banco de dados SQLite

---

## 🛠️ Tecnologias Utilizadas

| Tecnologia | Uso |
|---|---|
| **Python 3.13** | Linguagem principal |
| **FastAPI** | Framework do backend/API |
| **Google Gemini 2.5 Flash** | Análise de currículo com IA |
| **pdfplumber** | Extração de texto de PDFs |
| **python-docx** | Leitura de arquivos Word |
| **httpx + BeautifulSoup4** | Web scraping dos portais de vagas |
| **SQLite** | Banco de dados de usuários |
| **Mercado Pago SDK** | Processamento de pagamentos |
| **smtplib (Gmail)** | Envio de emails automáticos |
| **python-dotenv** | Gerenciamento seguro de variáveis |
| **Railway** | Hospedagem em produção |

---

## 💡 Como Funciona

```
1. Usuário digita o email
       ↓
2. Recebe código de verificação (6 dígitos)
       ↓
3. Confirma o código → acessa 1ª busca grátis
       ↓
4. Faz upload do currículo (PDF ou DOCX)
       ↓
5. IA analisa o perfil (cargo, cidade, habilidades)
       ↓
6. Sistema busca vagas em 4 portais simultaneamente
       ↓
7. Exibe as 3 melhores vagas + vagas bloqueadas
       ↓
8. Recebe email com as vagas encontradas
       ↓
9. Para desbloquear todas → paga R$ 9,99 via Mercado Pago
```

---

## 💰 Modelo de Negócio

| Plano | Preço | Buscas |
|---|---|---|
| **Grátis** | R$ 0,00 | 1 busca |
| **Busca Aprofundada** | R$ 9,99 | +1 busca por pagamento |

---

## 🔧 Como Rodar Localmente

### Pré-requisitos
- Python 3.13+
- Conta no [Google AI Studio](https://aistudio.google.com) (chave Gemini)
- Conta no [Mercado Pago Developers](https://www.mercadopago.com.br/developers)
- Conta Gmail com [senha de app](https://myaccount.google.com/apppasswords)

### Instalação

```bash
# Clone o repositório
git clone https://github.com/johnnywiick/vagacerta-ai.git
cd vagacerta-ai

# Instale as dependências
pip install -r requirements.txt
```

### Configuração

Crie um arquivo `.env` na raiz do projeto:

```env
GOOGLE_API_KEY=sua_chave_google_aqui
MP_ACCESS_TOKEN=seu_token_mercadopago_aqui
GMAIL_EMAIL=seu@gmail.com
GMAIL_SENHA=sua_senha_de_app_aqui
BASE_URL=http://127.0.0.1:8000
```

### Executar

```bash
uvicorn main:app --reload
```

Acesse: **http://127.0.0.1:8000**

---

## 🌐 Deploy em Produção

O projeto está hospedado no **Railway** com deploy automático via GitHub.

URL de produção: **https://vagacerta-ai.up.railway.app**

Variáveis de ambiente necessárias no Railway:
- `GOOGLE_API_KEY`
- `MP_ACCESS_TOKEN`
- `GMAIL_EMAIL`
- `GMAIL_SENHA`
- `BASE_URL`

---

## 📁 Estrutura do Projeto

```
vagacerta-ai/
├── main.py           # Backend FastAPI (API + lógica)
├── index.html        # Frontend (HTML + CSS + JS)
├── requirements.txt  # Dependências Python
├── Procfile          # Configuração Railway
├── .env              # Variáveis de ambiente (não commitado)
├── .gitignore        # Arquivos ignorados pelo Git
└── vagacerta.db      # Banco de dados SQLite (gerado automaticamente)
```

---

## 🔒 Segurança

- Chaves de API protegidas via variáveis de ambiente
- Verificação de email obrigatória antes de qualquer busca
- Banco de dados controla limite de buscas por usuário
- `.env` e `vagacerta.db` não são commitados no repositório

---

## 👨‍💻 Desenvolvedor

**Johnny Marcos**  
Desenvolvido com 💙 usando Python, FastAPI e IA.

[![GitHub](https://img.shields.io/badge/GitHub-johnnywiick-black?logo=github)](https://github.com/johnnywiick)

---

## 📄 Licença

Este projeto é proprietário. Todos os direitos reservados © 2026 VagaCerta AI.
