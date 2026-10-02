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
import base64
import os 
import hmac


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
		backgroud-attachment: fixed;
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
		if hmac.compare_digest(senha, st.secrets['SENHA_APP']):
			st.session_state['autenticado'] = True
			st.rerun ()
		else:
			st.error('Senha incorreta')

	return False
if not verificar_senha():
	st.stop()


modelo_ia = OpenAI(api_key=st.secrets['GEMINI_API_KEY'],
			base_url='https://generativelanguage.googleapis.com/v1beta/openai')

st.write('# Nathan IA') #: a # dentro dos ' ' faz a mensagem aparecer na tela no maior tamnho possível e cada vez que colocar mais # o tamanho vai diminuindo
#criar historico de mensagem
if 'lista_mensagens' not in st.session_state: # session_states é a memoria do streamlit
	st.session_state ['lista_mensagens'] = []

mensagem_usuario = st.chat_input('Escreva sua mensagem aqui') # campo de mensagem para a pesssoa colocar sua mensagem

for mensagem in st.session_state ['lista_mensagens']:
	quem_enviou = mensagem['role']
	texto_mensagem = mensagem['content']
	st.chat_message(quem_enviou).write(texto_mensagem)
	
if mensagem_usuario: # ixibe a mensagem na tela
	# user - usuario
	# assistant - chatbot/robo/ia
	st.chat_message('user').write(mensagem_usuario)
	mensagem1 = {'role' : 'user', 'content': mensagem_usuario} # role é quem enviou e content e o conteudo
	st.session_state ['lista_mensagens'].append(mensagem1)

	# pegar a mensagem da ia
	resposta_modelo = modelo_ia.chat.completions.create(
		messages = st.session_state ['lista_mensagens'],
		model = 'gemini-flash-lite-latest'
	)
	resposta_ia = resposta_modelo.choices[0].message.content
  
	# enviar a mensagem na ia no chat
	st.chat_message('assistant').write(resposta_ia)	
	mensagem2 = { 'role' : 'assistant' , 'content' : resposta_ia }
	st.session_state ['lista_mensagens'].append(mensagem2)

# manter o historicio (criar memoria)

# tornar as respostas inteligentes

# lista_mensagem = []
# mensagem1 = {'role' : 'user', 'content','outra coisa'} # role é quem enviou e content e o conteudo
# mensagem2 = { 'role' : 'assistent' , 'content ' , ' '}

# lista_mensagem.append(mensagem1)
# lista_mensagem.append(mensagem2)

# print(lista_mensagem)



