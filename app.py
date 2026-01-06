import streamlit as st
import google.generativeai as genai
from pypdf import PdfReader
import os

# Configuração da Página
st.set_page_config(page_title="Harvard Mentor AI", layout="wide")

# --- 1. CONFIGURAÇÃO E SEGURANÇA ---
api_key = st.secrets.get("GOOGLE_API_KEY")

# Se não tiver chave configurada, pede na tela
if not api_key:
    api_key = st.sidebar.text_input("Insira sua Google API Key", type="password")

# --- 2. FUNÇÕES DE BACKEND ---

@st.cache_resource
def load_pdf_text(pdf_path):
    """Lê o PDF e extrai o texto. Usa cache para não reler a cada clique."""
    if not os.path.exists(pdf_path):
        return None
    
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def get_gemini_response(history, mode, context_text):
    """Envia o histórico e o contexto para o Gemini."""
    
    
    if mode == "Consultor":
        system_instruction = f"""
        Você é um Consultor Sênior formado com o material do 'Harvard Manager Mentor'.
        SEU OBJETIVO: Ajudar o usuário a resolver problemas práticos de negócios usando APENAS os conceitos do material fornecido.
        MATERIAL DE BASE: {context_text}
        DIRETRIZES:
        - Seja direto e profissional.
        - Cite o conceito específico (ex: 'Segundo o módulo de Negociação...').
        - Dê planos de ação (Passo 1, Passo 2).
        """
    elif mode == "Quiz":
        system_instruction = f"""
        Você é um Examinador Rigoroso da Harvard.
        SEU OBJETIVO: Testar o conhecimento do usuário sobre o material.
        MATERIAL DE BASE: {context_text}
        DIRETRIZES:
        - Faça UMA pergunta por vez baseada no texto.
        - Espere a resposta.
        - Avalie se está certo ou errado e explique o porquê baseando-se no texto.
        - Depois, proponha outra pergunta.
        """
    elif mode == "Roleplay":
        system_instruction = f"""
        Você é um ator em uma simulação de negócios.
        SEU OBJETIVO: Agir como uma contraparte difícil (um cliente bravo, um funcionário desmotivado ou um fornecedor rígido).
        MATERIAL DE BASE: {context_text}
        DIRETRIZES:
        - Não saia do personagem.
        - O usuário deve tentar aplicar as técnicas do curso para lidar com você.
        - No final, se o usuário pedir 'Feedback', saia do personagem e avalie a performance dele baseada no curso.
        """
    else:
        system_instruction = "Você é um assistente útil."

    # Configura o modelo
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=system_instruction
    )
    
    # Inicia o chat com o histórico
    chat = model.start_chat(history=history)
    response = chat.send_message(st.session_state.messages[-1]["content"])
    
    return response.text

# --- 3. INTERFACE DO USUÁRIO ---

# Sidebar de Navegação e Modos
st.sidebar.title(" Harvard Mentor AI")
page = st.sidebar.radio("Navegação", ["Introdução", "Chat com Mentor"])

if page == "Introdução":
    st.title("Bem-vindo ao Harvard Mentor AI ")
    st.markdown("""
    Este projeto aplica conhecimentos de **Marketing, Finanças, Negociação e Liderança** baseados no currículo *Harvard Business Impact*.
    
    ### O que este app faz?
    Ele transforma o conteúdo estático das aulas em um mentor interativo utilizando **Inteligência Artificial (Google Gemini 1.5)**.
    
    ### Como usar?
    Vá para a aba **Chat com Mentor** e escolha um modo:
    1.   **Consultor:** Traga um problema real e receba conselhos baseados na teoria.
    2.   **Quiz:** Teste seus conhecimentos. O Mentor fará perguntas sobre o material.
    3.   **Roleplay:** Simule situações difíceis (negociações, conflitos) e treine sua resposta.
    
    ---
    *Disclaimer: Este é um projeto educacional de portfólio. O conteúdo base pertence à Harvard Business School Publishing.*
    """)

elif page == "Chat com Mentor":
    # Carregar o PDF (apenas uma vez)
    # IMPORTANTE: O nome do arquivo deve ser exato
    pdf_text = load_pdf_text("Harvard Manager Mentor.pdf")
    
    if not pdf_text:
        st.error("Erro: Arquivo PDF não encontrado. Verifique se o arquivo 'Harvard Manager Mentor.pdf' está na raiz do projeto.")
        st.stop()

    if not api_key:
        st.warning("Por favor, insira a API Key na barra lateral para começar.")
        st.stop()

    # Seletor de Modo
    mode = st.radio("Escolha o Modo de Interação:", ["Consultor", "Quiz", "Roleplay"], horizontal=True)
    
    # Botão para limpar conversa se trocar de modo
    if st.button("Reiniciar Conversa"):
        st.session_state.messages = []
        st.rerun()

    # Inicializa o histórico visual
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Exibe as mensagens anteriores na tela
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Input do Usuário
    if prompt := st.chat_input("Digite sua mensagem..."):
        
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Gera resposta
        with st.chat_message("assistant"):
            with st.spinner("O Mentor está analisando o material..."):
                try:
                    # Converte histórico do Streamlit para o formato do Google (opcional, mas o .start_chat lida bem)
                    # Aqui simplificamos enviando o contexto no system prompt a cada chamada ou mantendo sessão
                    # O Gemini 1.5 é stateless via API REST, mas a lib python mantém estado se usarmos chat.history.
                    # Para simplificar o código no Streamlit (que recarrega tudo), recriamos a chamada.
                    
                    history_gemini = [
                        {"role": "user" if m["role"] == "user" else "model", "parts": [m["content"]]}
                        for m in st.session_state.messages[:-1] 
                    ]
                    
                    response_text = get_gemini_response(history_gemini, mode, pdf_text)
                    st.markdown(response_text)
                    
                    # 3. Adiciona resposta ao histórico visual
                    st.session_state.messages.append({"role": "assistant", "content": response_text})
                    
                except Exception as e:
                    st.error(f"Ocorreu um erro na API: {e}")
