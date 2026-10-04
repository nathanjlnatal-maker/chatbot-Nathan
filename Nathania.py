#titulo
# campo de mensagem (input)
# quando o usuario mandar uma mensagem
	# mostrar a mensagem na conversa
	# mandar a mensagem pra ia responder
	# mostra a resposta da ia
	
# pip install streamlit openai
# pro código rodar não se clica em play, tem que ir no terminal e digitar ( streamlit run 'nome da sua pasta')

import streamlit as st
from openai import OpenAI
from google import genai # bibioteca do gemini para criar imagens
import base64
import os 
import hmac
from pypdf import PdfReader
from datetime import date
from conversor01 import mostrar_conversor

PASTA = os.path.dirname(os.path.abspath(__file__))

PROMPT_SISTEMA = (
        'Você é o Nathan IA, um assistente pessoal criado para ajudar principalmente com estudos e programação. '
    'Seu foco principal é auxiliar em Python, lógica de programação, SQL, HTML/CSS, JavaScript, '
    'carreira em tecnologia e técnicas de estudo. '
    'Explique os assuntos de forma clara e passo a passo, usando exemplos curtos e práticos. '
    'Sempre que for adequado, incentive o aluno a tentar resolver o problema antes de entregar a resposta completa. '
    'Apesar de seu foco principal ser estudos e programação, você também pode realizar outras tarefas quando o usuário solicitar, '
    'como escrever, revisar ou resumir textos, fazer cálculos, organizar informações, explicar assuntos gerais, '
    'criar ideias, auxiliar em tarefas do dia a dia e outras funções que estejam ao seu alcance. '
    'Quando a solicitação não estiver relacionada a estudos, apenas responda normalmente, sem dizer que só pode ajudar com estudos. '
    'Mantenha sempre respostas úteis, claras e objetivas, adaptando a explicação ao nível de conhecimento do usuário.'
	)

# configurações das IAs (se um nome de modelo mudar, é só trocar aqui)

MODELO_GEMINI = 'gemini-flash-lite-latest'
MODELO_CLAUDE = 'claude-haiku-4-5-20251001'
MODELO_IMAGEM = 'gemini-3.1-flash-image'
MODELO_DEEPSEEK = 'deepseek-v4-flash'
MODELO_GROQ = 'openai/gpt-oss-120b'
LIMITES = {
     'Gemini' : 500_000,
     'Claude' : 300_000,
     'DeepSeek' : 300_000,
     'GPT-OSS (Groq)' : 300_000,
     'Nano Banana 2' : 30,
}  
LIMITE_HISTORICO = 20 # quantas mensagens recentes vão para a IA (economiza cota/crédito)

if st.session_state.get('dia_uso') != date.today():
     st.session_state['uso'] = {nome: 0 for nome in LIMITES}
     st.session_state['dia_uso'] = date.today()

def registrar_uso(nome, quantidade):
     st.session_state['uso'][nome] += quantidade

LIMITE_CARACTERES_ARQUIVO = 15000

def ler_arquivo(arquivo):
     nome=arquivo.name
     try:
        if nome.lower().endswith('.pdf'):
            leitor = PdfReader(arquivo)
            texto = '\n'.join((pagina.extract_text() or '') for pagina in leitor.pages)
        else:
            texto = arquivo.getvalue().decode('utf-8', errors='ignore')
     except Exception:
        return nome, '[não consegui ler este arquivo]', False
     if not texto.strip():
        texto = '[não encontrei texto neste arquivo (PDF escaneado?)]'
     cortado = len(texto) > LIMITE_CARACTERES_ARQUIVO
     return nome, texto[:LIMITE_CARACTERES_ARQUIVO], cortado

def colocar_fundo (fundo):
	pasta = os.path.dirname(__file__)
	caminho = os.path.join(pasta, fundo)
	with open(caminho, 'rb') as arquivo:
		imagem_base64 = base64.b64encode(arquivo.read()).decode()
	st.markdown(f'''
	<style>
	.stApp {{
		background-image: url('data:image/jpg;base64,{imagem_base64}');
		background-size: cover;
		background-position: center;
		background-attachment: fixed;
	}}
	[data-testid='stHeader'] {{
		background: transparent;
	}}
	[data-testid='stBottom'] > div {{
		background: transparent;
	}}
	.stChatMessage {{
		background-color: rgba(0,0,0,0.55);
		border-radius: 12px;
	}}
	</style>
	''', unsafe_allow_html=True)
colocar_fundo('fundo.jpg')

def verificar_senha():
	if st.session_state.get('autenticado'):
		return True

	senha=st.text_input('Digite a senha para acessar', type='password')
	if senha:
		# .encode() evita erro se a senha tiver acento ou ç
		if hmac.compare_digest(senha, st.secrets['SENHA_APP']):
			st.session_state['autenticado'] = True
			st.rerun ()
		else:
			st.error('Senha incorreta')

	return False
if not verificar_senha():
	st.stop()

# Gemini texto (usa a biblioteca openai apontando para o Google)
cliente_gemini_texto = OpenAI(
	api_key=st.secrets['GEMINI_API_KEY'],
	base_url='https://generativelanguage.googleapis.com/v1beta/openai')

# Gemini imagem (usa a biblioteca própria do Google, com a mesma chave)
cliente_gemini_imagem = genai.Client(
    api_key=st.secrets.get('GEMINI_IMAGE_API_KEY', st.secrets['GEMINI_API_KEY'])
)

# Claude só aparece no menu se a chave ANTHROPIC_API_KEY estiver nos Secrets

if 'ANTHROPIC_API_KEY' in st.secrets:
	cliente_claude = OpenAI(
		api_key=st.secrets['ANTHROPIC_API_KEY'],
		base_url='https://api.anthropic.com/v1/'
	)
if 'DEEPSEEK_API_KEY' in st.secrets:
     cliente_deepseek = OpenAI(
     	 api_key=st.secrets['DEEPSEEK_API_KEY'],
		 base_url='https://api.deepseek.com'
    )
if 'GROQ_API_KEY' in st.secrets:
     cliente_groq = OpenAI(
          api_key=st.secrets['GROQ_API_KEY'],
          base_url='https://api.groq.com/openai/v1'
	 )
if 'ia_escolhida' not in st.session_state:
    st.session_state['ia_escolhida'] = 'Gemini'

if 'modo' not in st.session_state:
    st.session_state['modo'] = 'chat'

# menu na lateral
def botao_ia(nome, chave):
    if st.sidebar.button(nome, key=chave, use_container_width=True):
        st.session_state['ia_escolhida'] = nome
        st.session_state['modo'] = 'chat'

def botao_conversor():
    if st.sidebar.button('Conversor de arquivos', key='btn_conversor', use_container_width=True):
        st.session_state['modo'] = 'conversor'

st.sidebar.markdown('## 🛠️ Ferramentas')
botao_conversor()

st.sidebar.markdown('---')
st.sidebar.markdown('## 🤖 Escolha a IA')

botao_ia('Gemini', 'btn_gemini')

if 'ANTHROPIC_API_KEY' in st.secrets:
    botao_ia('Claude', 'btn_claude')

if 'DEEPSEEK_API_KEY' in st.secrets:
    botao_ia('DeepSeek', 'btn_deepseek')

if 'GROQ_API_KEY' in st.secrets:
    botao_ia('GPT-OSS (Groq)', 'btn_groq')

if 'GEMINI_IMAGE_API_KEY' in st.secrets:
    botao_ia('Nano Banana 2', 'btn_nano_banana')

# IA atualmente escolhida
ia_escolhida = st.session_state['ia_escolhida']

st.sidebar.markdown('---')
if st.session_state['modo'] == 'conversor':
    st.sidebar.write('**Ferramenta:** Conversor de arquivos')
else:
    st.sidebar.write(f'**IA escolhida:** {ia_escolhida}')

st.write('# Nathan IA')

if st.session_state['modo'] == 'conversor':
    mostrar_conversor()
    st.stop()
 
# criar histórico de mensagens (session_state é a memória do Streamlit)
if 'lista_mensagens' not in st.session_state:
    st.session_state['lista_mensagens'] = []
 
entrada = st.chat_input(
     'Escreva sua mensagem aqui',
     accept_file = 'multiple',
     file_type=['pdf', 'txt', 'py', 'csv', 'md', 'json']
) 
for mensagem in st.session_state['lista_mensagens']:
    with st.chat_message(mensagem['role']):
        st.write(mensagem['content'])
        if 'imagem' in mensagem:
            st.image(mensagem['imagem'])
 
if entrada and (entrada.text or entrada.files):
    texto_usuario = entrada.text or 'Analise o(s) arquivo(s) enviado(s).'
    texto_para_ia = texto_usuario
    aviso_arquivos = ''
    for arquivo in entrada.files:
        nome, conteudo, cortado = ler_arquivo(arquivo)
        texto_para_ia += f'\n\n[Arquivo: {nome}]\n{conteudo}'
        aviso_arquivos += f'\n\n📎 {nome}' + (' (cortado: arquivo muito grande)' if cortado else '')

    st.chat_message('user').write(texto_usuario + aviso_arquivos)
    mensagem1 = {
        'role': 'user',
        'content': texto_usuario + aviso_arquivos,   # o que aparece no chat
        'conteudo_ia': texto_para_ia,                # o que a IA recebe (com o texto do arquivo)
    }
    st.session_state['lista_mensagens'].append(mensagem1)
 
    try:
        if ia_escolhida == 'Nano Banana 2':
            with st.spinner('Criando imagem ...'):
                resposta_img = cliente_gemini_imagem.models.generate_content(
                    model=MODELO_IMAGEM,
                    ccontents=texto_usuario,
                )
 
            imagem_gerada = None
            for parte in resposta_img.candidates[0].content.parts:
                if parte.inline_data is not None:
                    imagem_gerada = parte.inline_data.data  # a imagem vem como bytes
 
            if imagem_gerada is None:
                raise Exception('A IA não devolveu nenhuma imagem')
            
            registrar_uso('Nano Banana 2',1)

            mensagem2 = {
                'role': 'assistant',
                'content': 'Imagem criada pelo Nano Banana 2.',
                'imagem': imagem_gerada
            }
 
        else:
            if ia_escolhida == 'Claude':
                cliente, modelo = cliente_claude, MODELO_CLAUDE
            elif ia_escolhida == 'DeepSeek':
                cliente, modelo = cliente_deepseek, MODELO_DEEPSEEK
            elif ia_escolhida == 'GPT-OSS (Groq)':
                cliente, modelo = cliente_groq, MODELO_GROQ
            else:
                cliente, modelo = cliente_gemini_texto, MODELO_GEMINI
 
            # manda só role e content (sem a imagem) e só as mensagens mais recentes
            historico = [
                {'role': m['role'], 'content': m.get('conteudo_ia', m['content'])}
                for m in st.session_state['lista_mensagens'][-LIMITE_HISTORICO:]
            ]
            # o Claude exige que a conversa comece pelo usuário
            while historico and historico[0]['role'] == 'assistant':
                historico.pop(0)
 
            mensagem_para_ia = [{'role': 'system', 'content': PROMPT_SISTEMA}] + historico
 
            with st.spinner('Pensando ...'):
                resposta_modelo = cliente.chat.completions.create(
                    messages=mensagem_para_ia,
                    model=modelo
                )
 
            resposta_ia = resposta_modelo.choices[0].message.content

            if resposta_modelo.usage:
                 registrar_uso(ia_escolhida, resposta_modelo.usage.total_tokens)

            mensagem2 = {'role': 'assistant', 'content': resposta_ia}
        # mostrar a resposta no chat e guardar no histórico
        with st.chat_message('assistant'):
            st.write(mensagem2['content'])
            if 'imagem' in mensagem2:
                st.image(mensagem2['imagem'])
        st.session_state['lista_mensagens'].append(mensagem2)
 
    except Exception as erro:
            if st.session_state['lista_mensagens']:
                st.session_state['lista_mensagens'].pop()  # tira a pergunta que ficou sem resposta
            st.error(f'Não consegui gerar a resposta agora: {erro}')

CHAVES = {
     'Claude' : 'ANTHROPIC_API_KEY',
     'DeepSeek' : 'DEEPSEEK_API_KEY',
     'GPT-OSS (Groq)' : 'GROQ_API_KEY',
     'Nano Banana 2' : 'GEMINI_IMAGE_API_KEY',
}

st.sidebar.markdown('---')
st.sidebar.markdown('## 📊 Limite restante ')
for nome, limite in LIMITES.items():
     if nome in CHAVES and CHAVES [nome] not in st.secrets:
          continue
     restante = max(1 - st.session_state['uso'][nome] / limite,0)
     st.sidebar.progress(restante, text=f'{nome}: {restante:.0%} restante')


# Para fazer o código rodar no terminal 
#  cd -LiteralPath "[Aula 3] Chatbot com Ia em tempo real"
#streamlit run Nathania_multi_ia.py








	#resposta_modelo = modelo_ia.chat.completions.create(
		#messages = mensagem_para_ia,
		#model = 'gemini-flash-lite-latest'

	#resposta_ia = resposta_modelo.choices[0].message.content
  
	# enviar a mensagem na ia no chat
	#st.chat_message('assistant').write(resposta_ia)	
	#mensagem2 = { 'role' : 'assistant' , 'content' : resposta_ia }
	#st.session_state ['lista_mensagens'].append(mensagem2)'''

# manter o historicio (criar memoria)

# tornar as respostas inteligentes

# lista_mensagem = []
# mensagem1 = {'role' : 'user', 'content','outra coisa'} # role é quem enviou e content e o conteudo
# mensagem2 = { 'role' : 'assistent' , 'content ' , ' '}

# lista_mensagem.append(mensagem1)
# lista_mensagem.append(mensagem2)

# print(lista_mensagem)



