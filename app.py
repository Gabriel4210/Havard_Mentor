import streamlit as st
from google import genai
from google.genai import types
from pypdf import PdfReader
import os
import gdown

# Configuração da Página
st.set_page_config(
    page_title="Harvard Mentor AI",
    page_icon="🎓",
    layout="wide"
)

# --- 1. CONFIGURAÇÃO DE SEGREDOS ---
api_key = st.secrets.get("GOOGLE_API_KEY")
file_id = st.secrets.get("GDRIVE_FILE_ID")

# --- 2. FUNÇÕES DE INFRAESTRUTURA ---

def download_pdf_if_needed(filename):
    """
    Verifica se o PDF existe localmente. 
    Se não existir (cenário do Streamlit Cloud), baixa do Google Drive.
    """
    if os.path.exists(filename):
        return True
    
    if not file_id:
        st.error("Erro: ID do arquivo não configurado nos Secrets.")
        return False

    with st.spinner("Baixando material de estudo seguro (Isso acontece apenas uma vez)..."):
        try:
            
            url = f'https://drive.google.com/uc?id={file_id}'
            gdown.download(url, filename, quiet=False)
            return True
        except Exception as e:
            st.error(f"Falha ao baixar o arquivo: {e}")
            return False

@st.cache_resource
def load_pdf_text(pdf_path):
    """Lê o PDF e extrai o texto. Usa cache para performance."""
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

def get_gemini_response(history, mode, context_text):
    # Definição das Personas (System Prompts)
    prompts = {
        "Consultor": f"""
            Você é um Consultor Sênior da Harvard Business School.
            CONTEXTO: O usuário tem um desafio de negócios.
            BASE DE CONHECIMENTO: Use EXCLUSIVAMENTE o seguinte material: {context_text}
            
            SUA MISSÃO:
            1. Analise o problema do usuário.
            2. Encontre os frameworks/conceitos no material que se aplicam.
            3. Dê uma resposta estruturada (Diagnóstico -> Conceito -> Plano de Ação).
            4. Cite o módulo de onde tirou a informação.
            """,
        
        "Quiz": f"""
            Você é um Professor avaliador.
            BASE DE CONHECIMENTO: {context_text}
            
            SUA MISSÃO:
            1. Gere UMA pergunta de múltipla escolha ou discursiva baseada no texto.
            2. Aguarde a resposta do usuário.
            3. Se ele acertar, parabenize e explique o conceito. Se errar, corrija gentilmente citando o texto.
            4. Mantenha o tom educativo e desafiador.
            """,
        
        "Roleplay": f"""
            ATENÇÃO: Ignore que você é uma IA. Você é agora um PERSONAGEM.
            CENÁRIO: Simulação de Negociação/Liderança baseada em: {context_text}
            
            SUA MISSÃO:
            1. Aja como uma contraparte difícil (ex: cliente irritado, chefe exigente).
            2. Reaja às falas do usuário. Se ele usar boas técnicas do texto, ceda um pouco. Se ele for ruim, seja duro.
            3. NUNCA saia do personagem, a menos que o usuário diga "FIM DA SIMULAÇÃO".
            """
    }

    system_instruction = prompts.get(mode, "Você é um assistente útil.")

    # 2. Inicializa o Cliente (Nova Sintaxe)
    client = genai.Client(api_key=api_key)

    # 3. Converte histórico do Streamlit para o formato da Google
    # Streamlit usa: {"role": "user/assistant", "content": "texto"}
    # Google GenAI usa: types.Content(role="user/model", parts=[...])
    
    contents = []
    for msg in chat_history_streamlit:
        role = "user" if msg["role"] == "user" else "model"
        contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=msg["content"])]
            )
        )

    # 4. Configuração da Geração
    generate_content_config = types.GenerateContentConfig(
        temperature=0.7,
        top_p=0.95,
        max_output_tokens=2000,
        system_instruction=system_instruction,
    )

    # 5. Chamada ao Modelo
    try:
        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=contents,
            config=generate_content_config
        )
        return response.text
    except Exception as e:
        return f"Erro na API Google: {str(e)}"

# --- 3. INTERFACE (FRONTEND) ---

st.sidebar.title("Harvard Impact AI")
page = st.sidebar.radio("Menu", ["Introdução", "Mentor Virtual"])

if page == "Introdução":
    st.title("Domine os Fundamentos de Negócios 🚀")
    st.markdown("""
    Bem-vindo ao seu Mentor de Negócios baseado no currículo de Harvard.
    Utilizando a tecnologia **Google Gemini 1.5 Flash**.
    
    Escolha seu modo no menu lateral:
    1.  **Consultor:** Resolução de problemas.
    2.  **Quiz:** Estudo ativo.
    3.  **Roleplay:** Simulação prática.
    """)

elif page == "Mentor Virtual":
    if not api_key:
        st.warning("⚠️ API Key não detectada nos Secrets.")
        st.stop()
    
    pdf_filename = "Harvard Manager Mentor.pdf"
    pdf_text = load_pdf_text(pdf_filename)
    
    if not pdf_text:
        st.stop()

    col1, col2 = st.columns([3, 1])
    with col1:
        mode = st.radio("Modo:", ["Consultor", "Quiz", "Roleplay"], horizontal=True)
    with col2:
        if st.button("Limpar Chat 🗑️"):
            st.session_state.messages = []
            st.rerun()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        avatar = "🤖" if message["role"] == "assistant" else "👤"
        with st.chat_message(message["role"], avatar=avatar):
            st.markdown(message["content"])

    if prompt := st.chat_input("Digite sua mensagem..."):
        # Adiciona mensagem do usuário ao histórico visual
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="👤"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Analisando..."):
                # Passa o histórico completo + nova mensagem (já inclusa no state)
                response_text = get_gemini_response(st.session_state.messages, mode, pdf_text)
                
                st.markdown(response_text)
                st.session_state.messages.append({"role": "assistant", "content": response_text})
