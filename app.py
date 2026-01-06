import streamlit as st
from google import genai
from google.genai import types
from pypdf import PdfReader
import os
import gdown

# --- 1. CONFIGURAÇÃO DA PÁGINA E CSS ---
st.set_page_config(
    page_title="Harvard Mentor AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS Customizado para dar um ar profissional (Harvard Style)
st.markdown("""
<style>
    /* Cor de fundo da sidebar */
    [data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }
    /* Estilo dos botões de ação rápida */
    .stButton button {
        width: 100%;
        border-radius: 8px;
        height: 3em;
        background-color: white;
        border: 1px solid #A51C30; /* Harvard Crimson */
        color: #A51C30;
        font-weight: 600;
    }
    .stButton button:hover {
        background-color: #A51C30;
        color: white;
        border: 1px solid #A51C30;
    }
    /* Título principal */
    h1 {
        color: #1e1e1e;
        font-family: 'Helvetica Neue', sans-serif;
    }
    /* Chat bubbles */
    .stChatMessage {
        background-color: transparent;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. CONFIGURAÇÃO DE SEGREDOS ---
api_key = st.secrets.get("GOOGLE_API_KEY")
file_id = st.secrets.get("GDRIVE_FILE_ID")

# --- 3. FUNÇÕES DE INFRAESTRUTURA ---

def download_pdf_if_needed(filename):
    if os.path.exists(filename):
        return True
    if not file_id:
        st.error("Erro: ID do arquivo não configurado nos Secrets.")
        return False
    with st.spinner("Baixando biblioteca de Harvard..."):
        try:
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, filename, quiet=False)
            return True
        except Exception as e:
            st.error(f"Falha ao baixar o arquivo: {e}")
            return False

@st.cache_resource
def load_pdf_text(pdf_path):
    if not download_pdf_if_needed(pdf_path):
        return None
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        st.error(f"Erro ao ler PDF: {e}")
        return None

def get_gemini_response(chat_history_streamlit, mode, context_text):
    prompts = {
        "Consultor": f"""
            Você é um Consultor Sênior da Harvard Business School.
            CONTEXTO: O usuário tem um desafio de negócios.
            BASE DE CONHECIMENTO: Use EXCLUSIVAMENTE o seguinte material: {context_text}
            DIRETRIZES: 
            - Seja extremamente prático e direto.
            - Estruture a resposta em tópicos.
            - Cite o conceito específico do texto.
            """,
        "Quiz": f"""
            Você é um Professor da Harvard.
            BASE DE CONHECIMENTO: {context_text}
            DIRETRIZES: 
            - Se o usuário pedir um quiz, faça UMA pergunta de múltipla escolha difícil.
            - Se ele responder, avalie e explique a lógica.
            """,
        "Roleplay": f"""
            ATENÇÃO: Ignore que é uma IA. Você é um PERSONAGEM.
            CENÁRIO: Baseado em: {context_text}
            DIRETRIZES: Aja como uma contraparte difícil (cliente, chefe, fornecedor).
            """
    }
    
    system_instruction = prompts.get(mode, "Você é um assistente útil.")
    client = genai.Client(api_key=api_key)
    
    contents = []
    for msg in chat_history_streamlit:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg["content"])]
            )
        )

    generate_content_config = types.GenerateContentConfig(
        temperature=0.5,
        top_p=0.95,
        max_output_tokens=2048,
        system_instruction=system_instruction,
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=generate_content_config
        )
        return response.text
    except Exception as e:
        return f"Erro na API Google: {str(e)}"

# --- 4. INTERFACE (FRONTEND) ---

# Sidebar: Controles e Branding
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/2/25/Harvard_University_shield.png/1200px-Harvard_University_shield.png", width=80)
    st.title("Mentor AI")
    st.markdown("---")
    
    st.subheader("⚙️ Configuração")
    mode = st.radio(
        "Modo de Interação:", 
        ["Consultor", "Quiz", "Roleplay"], 
        captions=["Resolva problemas", "Teste seu conhecimento", "Simule cenários"]
    )
    
    st.markdown("---")
    if st.button("🔄 Reiniciar Conversa"):
        st.session_state.messages = []
        st.rerun()
    
    st.markdown("---")
    st.caption("Powered by Google Gemini 2.5 Flash \nBased on Harvard Business Impact")

# Lógica Principal
if not api_key:
    st.warning("⚠️ API Key não detectada.")
    st.stop()

pdf_text = load_pdf_text("Harvard Manager Mentor.pdf")
if not pdf_text:
    st.stop()

# Inicializa Session State
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- TELA DE BOAS-VINDAS (Se o chat estiver vazio) ---
if len(st.session_state.messages) == 0:
    st.title("Bem-vindo ao Harvard Mentor AI 🎓")
    st.markdown(f"#### Seu assistente de elite para *Marketing, Finanças, Negociação e Liderança*.")
    st.markdown("Não sabe por onde começar? Escolha uma opção abaixo baseada no modo **" + mode + "**:")
    
    col1, col2, col3 = st.columns(3)
    
    # Lógica de Sugestões Inteligentes
    suggestion = None
    if mode == "Consultor":
        if col1.button("📉 Estratégia de Preço"):
            suggestion = "Como definir o preço de um novo produto premium em um mercado saturado segundo o material?"
        if col2.button("🤝 Negociação Difícil"):
            suggestion = "Quais são as melhores táticas para negociar com um fornecedor que tem monopólio?"
        if col3.button("📊 Análise Financeira"):
            suggestion = "Explique a diferença entre Fluxo de Caixa e Lucro como se eu fosse um CEO iniciante."
            
    elif mode == "Quiz":
        if col1.button("🎲 Quiz Aleatório"):
            suggestion = "Faça uma pergunta difícil de múltipla escolha sobre Liderança."
        if col2.button("💰 Quiz de Finanças"):
            suggestion = "Teste meu conhecimento sobre ROI e Payback."
        if col3.button("📢 Quiz de Marketing"):
            suggestion = "Me faça uma pergunta sobre os 4 Ps do Marketing."

    elif mode == "Roleplay":
        st.info("No modo Roleplay, o Mentor vai atuar como um personagem. Escolha o cenário:")
        if col1.button("😡 Cliente Irritado"):
            suggestion = "Inicie uma simulação onde você é um cliente furioso porque a entrega atrasou. Eu sou o gerente."
        if col2.button("💼 Chefe Exigente"):
            suggestion = "Atue como meu chefe pedindo cortes de orçamento impossíveis. Eu preciso defender meu time."
        if col3.button("🤑 Investidor Cético"):
            suggestion = "Você é um investidor Shark Tank. Eu estou tentando vender minha ideia. Comece me questionando."

    # Se clicou em algum botão, já envia a mensagem
    if suggestion:
        st.session_state.messages.append({"role": "user", "content": suggestion})
        st.rerun()

# --- EXIBIÇÃO DO CHAT ---
else:
    # Mostra título menor quando já tem chat
    st.subheader(f"Conversando com: Mentor ({mode})")

for message in st.session_state.messages:
    avatar = "🤖" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# Input do Usuário
if prompt := st.chat_input("Digite sua dúvida ou resposta..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Consultando material de Harvard..."):
            response_text = get_gemini_response(st.session_state.messages, mode, pdf_text)
            st.markdown(response_text)
            st.session_state.messages.append({"role": "assistant", "content": response_text})
