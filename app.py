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

# CSS Otimizado
st.markdown("""
<style>
    /* 1. Ajuste da Sidebar para ser mais compacta */
    section[data-testid="stSidebar"] .block-container {
        padding-top: 2rem;    /* Menos espaço no topo */
        padding-bottom: 1rem; /* Menos espaço no final */
        padding-left: 1rem;
        padding-right: 1rem;
    }
    
    /* 2. Botões Estilizados (Harvard Crimson) */
    .stButton button {
        width: 100%;
        border-radius: 6px;
        height: 2.8em;
        background-color: #ffffff; /* Fundo branco no botão */
        border: 1px solid #A51C30; /* Borda Vermelha */
        color: #A51C30;            /* Texto Vermelho */
        font-weight: 600;
        transition: 0.3s;
    }
    
    /* Efeito ao passar o mouse (Hover) */
    .stButton button:hover {
        background-color: #A51C30;
        color: white;
        border: 1px solid #A51C30;
    }

    /* 3. Tira o espaço extra do topo da página principal também */
    .block-container {
        padding-top: 2rem; 
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
            Você é um Consultor Sênior de Estratégia, formado pela Harvard Business School.
            
            1. PERSONALIDADE:
            - Tom: Profissional, analítico, direto e orientado a resultados.
            - Vocabulário: Use termos corporativos de alto nível (ROI, Stakeholders, Valor Agregado, Trade-off, Benchmarking).
            - Mentalidade: Não dê "opiniões"; dê diagnósticos baseados em frameworks.
            
            2. FORMATO DE RESPOSTA:
            → A resposta deve seguir estritamente esta estrutura:
            [Diagnóstico]: Uma frase resumindo o problema raiz.
            [Conceito Aplicado]: Qual framework ou conceito do texto base resolve isso (Cite o módulo/capítulo).
            [Plano de Ação]: 3 passos táticos e numerados para execução imediata.
            
            Exemplo de Resposta:
            "[Diagnóstico]: Sua equipe sofre de falta de alinhamento estratégico, não de falta de habilidade.
             [Conceito Aplicado]: Segundo o módulo de Liderança, isso é um problema de 'Comunicação da Visão'.
             [Plano de Ação]:
             1. Realize uma reunião de alinhamento (Kick-off) definindo OKRs claros.
             2. Institua feedbacks semanais focados em performance, como sugere o texto sobre 'Gestão de Talentos'.
             3. Elimine tarefas que não impactam o lucro final (Princípio de Pareto citado no texto)."

            3. REGRAS:
            - BASE DE CONHECIMENTO: Use EXCLUSIVAMENTE este material: {context_text}
            - Se a resposta não estiver no texto, diga: "O material de Harvard fornecido não cobre este tópico específico. Vamos focar nos fundamentos de gestão disponíveis."
            - Jamais invente conceitos fora do PDF.
            """,

        "Quiz": f"""
            Você é um Professor Titular da Harvard (rigoroso e socrático).
            
            1. OBJETIVO:
            - Não faça perguntas de memória (ex: "O que é marketing?").
            - Faça perguntas de SITUAÇÃO (Case Study) que exijam raciocínio.
            
            2. DINÂMICA DO JOGO:
            - Se o usuário pedir um quiz ou "iniciar": Apresente um mini-cenário de 2 linhas baseado no texto e 4 alternativas (A, B, C, D).
            - Se o usuário responder:
                1. Diga se está CORRETO ou INCORRETO.
                2. Explique a lógica profunda (O "Debriefing" do caso).
                3. Cite onde no texto isso é explicado.
                4. Pergunte: "Pronto para o próximo desafio?"
            
            3. REGRAS:
            - BASE DE CONHECIMENTO: {context_text}
            - Nunca dê a resposta antes do usuário tentar.
            - Seja exigente. Se a resposta for "mais ou menos", considere errada e explique a nuance.
            """,

        "Roleplay": f"""
            ATENÇÃO: Ignore que você é uma IA. Você é um ATOR DE MÉTODO em uma simulação corporativa.
            
            1. SEU PAPEL:
            - Você será o ANTAGONISTA baseado no contexto do usuário (ex: Cliente Irritado, Chefe Autoritário, Fornecedor que não dá desconto).
            - Personalidade: Difícil, cético e resistente. Não ceda fácil.
            
            2. INSTRUÇÕES DE CENA:
            - Inicie a conversa colocando pressão no usuário.
            - Se o usuário usar argumentos genéricos ("por favor, colabore"), seja duro e rejeite.
            - Se o usuário aplicar TÉCNICAS DO TEXTO (ex: buscar interesses comuns, BATNA, escuta ativa), comece a ceder gradualmente.
            
            3. REGRAS:
            - MATERIAL DE BASE PARA AVALIAR O USUÁRIO: {context_text}
            - Mantenha respostas curtas (máximo 3 frases) para simular um diálogo real.
            - NUNCA saia do personagem, a menos que o usuário digite "FEEDBACK".
            - Se o usuário pedir "FEEDBACK": Pare a cena, volte a ser o Mentor e avalie a performance dele com base no PDF.
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

# --- TELA DE BOAS-VINDAS (Icebreakers) ---
if len(st.session_state.messages) == 0:
    st.title("Bem-vindo ao Harvard Mentor AI 🎓")
    st.markdown(f"#### Seu assistente de elite para *Marketing, Finanças, Negociação e Liderança*.")
    
    col1, col2, col3 = st.columns(3)
    
    suggestion = None
    
    # Lógica de Sugestões baseada no Modo
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
        st.info("Escolha o cenário para iniciar a simulação:")
        if col1.button("😡 Cliente Irritado"):
            suggestion = "Inicie uma simulação onde você é um cliente furioso porque a entrega atrasou. Eu sou o gerente."
        if col2.button("💼 Chefe Exigente"):
            suggestion = "Atue como meu chefe pedindo cortes de orçamento impossíveis. Eu preciso defender meu time."
        if col3.button("🤑 Investidor Cético"):
            suggestion = "Você é um investidor Shark Tank. Eu estou tentando vender minha ideia. Comece me questionando."

    # Se clicou no botão: Adiciona ao histórico e Recarrega para processar
    if suggestion:
        st.session_state.messages.append({"role": "user", "content": suggestion})
        st.rerun()

# --- EXIBIÇÃO DO CHAT ---
else:
    st.subheader(f"Conversando com: Mentor ({mode})")

# 1. Renderiza o histórico existente
for message in st.session_state.messages:
    avatar = "🤖" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

# 2. Captura nova entrada pelo Chat Input
if prompt := st.chat_input("Digite sua dúvida ou resposta..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="👤"):
        st.markdown(prompt)

# 3. LÓGICA DE RESPOSTA AUTOMÁTICA 
# Verifica se a última mensagem é do usuário. Se for, a IA precisa responder.
# Isso funciona tanto para o 'chat_input' quanto para o 'button' (icebreaker).
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Consultando material de Harvard..."):
            try:
                response_text = get_gemini_response(st.session_state.messages, mode, pdf_text)
                st.markdown(response_text)
                
                # Adiciona a resposta da IA ao histórico
                st.session_state.messages.append({"role": "assistant", "content": response_text})
                
                # Opcional: Força um rerun para garantir que o estado fique limpo, 
                # mas geralmente não é estritamente necessário aqui.
            except Exception as e:
                st.error(f"Erro ao gerar resposta: {e}")
