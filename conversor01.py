"""Conversor de arquivos do Nathan IA.

O usuário envia um arquivo, escolhe o formato e baixa o resultado (sem usar IA).

Todas as bibliotecas "pesadas" são opcionais: se alguma não carregar (por exemplo, porque o
Windows bloqueou um arquivo dela), o conversor continua funcionando e só esconde as opções
que dependem dela. CSV <-> JSON funciona sem nenhuma biblioteca extra.

  Pillow       -> conversões de imagem
  openpyxl     -> Excel (XLSX)
  pdf2docx     -> PDF para Word
  pymupdf      -> PDF para imagens (ZIP)
  python-docx  -> Word para texto
"""
import csv
import importlib
import io
import json
import os
import re
import tempfile
import zipfile

import streamlit as st
from pypdf import PdfReader

INDISPONIVEIS = []   # bibliotecas que não carregaram neste computador


def _importar(modulo, descricao):
    try:
        return importlib.import_module(modulo)
    except Exception:   # inclui "DLL load failed" e outros erros de carregamento
        INDISPONIVEIS.append(descricao)
        return None


Image = _importar('PIL.Image', 'imagens (Pillow)')
openpyxl = _importar('openpyxl', 'Excel (openpyxl)')
pdf2docx = _importar('pdf2docx', 'PDF para Word (pdf2docx)')
fitz = _importar('fitz', 'PDF para imagens (pymupdf)')
docx = _importar('docx', 'Word para texto (python-docx)')

TAMANHO_MAXIMO_MB = 25

# extensão -> nome do formato no Pillow
FORMATOS_IMAGEM = {
    'png': 'PNG', 'jpg': 'JPEG', 'webp': 'WEBP', 'bmp': 'BMP',
    'gif': 'GIF', 'tiff': 'TIFF', 'ico': 'ICO',
}
SAIDAS_IMAGEM = ['png', 'jpg', 'webp', 'bmp', 'gif', 'tiff', 'ico', 'pdf']

MIMES = {
    'png': 'image/png', 'jpg': 'image/jpeg', 'webp': 'image/webp', 'bmp': 'image/bmp',
    'gif': 'image/gif', 'tiff': 'image/tiff', 'ico': 'image/x-icon',
    'pdf': 'application/pdf', 'csv': 'text/csv', 'json': 'application/json',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'txt': 'text/plain', 'zip': 'application/zip',
}

NOMES_BONITOS = {
    'jpg': 'JPG', 'png': 'PNG', 'webp': 'WEBP', 'bmp': 'BMP', 'gif': 'GIF',
    'tiff': 'TIFF', 'ico': 'ICO (ícone)', 'pdf': 'PDF', 'csv': 'CSV',
    'xlsx': 'Excel (XLSX)', 'json': 'JSON', 'docx': 'Word (DOCX)',
    'txt': 'Texto (TXT)', 'zip': 'Imagens PNG de cada página (ZIP)',
}


def normalizar(ext):
    """jpeg vira jpg, tif vira tiff."""
    ext = ext.lower()
    return {'jpeg': 'jpg', 'tif': 'tiff'}.get(ext, ext)


def formatos_dados():
    formatos = ['csv', 'json']
    if openpyxl is not None:
        formatos.append('xlsx')
    return formatos


def opcoes_de_saida(entrada):
    """Lista de formatos para os quais o arquivo de entrada pode ser convertido."""
    if entrada in FORMATOS_IMAGEM and Image is not None:
        return [f for f in SAIDAS_IMAGEM if f != entrada]
    if entrada in formatos_dados():
        return [f for f in formatos_dados() if f != entrada]
    if entrada == 'pdf':
        saidas = ['txt']
        if pdf2docx is not None:
            saidas.append('docx')
        if fitz is not None:
            saidas.append('zip')
        return saidas
    if entrada == 'docx' and docx is not None:
        return ['txt']
    return []


def extensoes_aceitas():
    extensoes = formatos_dados() + ['pdf']
    if Image is not None:
        extensoes += list(FORMATOS_IMAGEM) + ['jpeg', 'tif']
    if docx is not None:
        extensoes.append('docx')
    return sorted(set(extensoes))


# ---------------------------------------------------------------- conversões

def converter_imagem(dados, saida):
    imagem = Image.open(io.BytesIO(dados))
    # JPG, BMP e PDF não aceitam transparência/paletas: converte para RGB
    if saida in ('jpg', 'bmp', 'pdf') and imagem.mode not in ('RGB', 'L'):
        imagem = imagem.convert('RGB')
    buffer = io.BytesIO()
    formato = 'PDF' if saida == 'pdf' else FORMATOS_IMAGEM[saida]
    imagem.save(buffer, format=formato)
    return buffer.getvalue()


def _inferir(valor):
    """Transforma '12' em 12 e '3.5' em 3.5 (sem mexer em códigos como '01234')."""
    if not isinstance(valor, str):
        return valor
    texto = valor.strip()
    if re.fullmatch(r'-?(0|[1-9]\d*)', texto):
        return int(texto)
    if re.fullmatch(r'-?(0|[1-9]\d*)\.\d+', texto):
        return float(texto)
    return valor


def ler_tabela(dados, entrada):
    """Devolve (cabecalho, linhas): o cabeçalho é uma lista de nomes e linhas é uma lista de listas."""
    if entrada == 'csv':
        try:
            texto = dados.decode('utf-8-sig')
        except UnicodeDecodeError:
            texto = dados.decode('latin-1')
        try:
            # descobre sozinho se o separador é vírgula, ponto e vírgula ou tab
            dialeto = csv.Sniffer().sniff(texto[:4096], delimiters=',;\t')
        except csv.Error:
            dialeto = csv.excel
        linhas = [[_inferir(c) for c in linha] for linha in csv.reader(io.StringIO(texto), dialeto)]
    elif entrada == 'xlsx':
        livro = openpyxl.load_workbook(io.BytesIO(dados), read_only=True, data_only=True)
        planilha = livro.worksheets[0]   # só a primeira planilha
        linhas = [['' if c is None else c for c in linha] for linha in planilha.iter_rows(values_only=True)]
        livro.close()
    else:   # json
        conteudo = json.loads(dados.decode('utf-8-sig'))
        if isinstance(conteudo, dict):
            conteudo = [conteudo]
        if not conteudo or not all(isinstance(item, dict) for item in conteudo):
            raise ValueError('O JSON precisa ser uma lista de objetos, por exemplo [{"nome": "Ana"}].')
        cabecalho = []
        for item in conteudo:
            for chave in item:
                if chave not in cabecalho:
                    cabecalho.append(chave)
        linhas = [cabecalho] + [[item.get(c, '') for c in cabecalho] for item in conteudo]

    linhas = [l for l in linhas if any(str(c).strip() for c in l)]   # tira linhas totalmente vazias
    if not linhas:
        raise ValueError('O arquivo está vazio.')
    return [str(c) for c in linhas[0]], linhas[1:]


def converter_dados(dados, entrada, saida, separador=','):
    cabecalho, linhas = ler_tabela(dados, entrada)
    if saida == 'csv':
        buffer = io.StringIO()
        escritor = csv.writer(buffer, delimiter=separador, lineterminator='\n')
        escritor.writerow(cabecalho)
        escritor.writerows(linhas)
        # utf-8-sig faz o Excel abrir os acentos certinho
        return buffer.getvalue().encode('utf-8-sig')
    if saida == 'xlsx':
        livro = openpyxl.Workbook()
        planilha = livro.active
        planilha.append(cabecalho)
        for linha in linhas:
            planilha.append(linha)
        buffer = io.BytesIO()
        livro.save(buffer)
        return buffer.getvalue()
    registros = [dict(zip(cabecalho, linha)) for linha in linhas]
    return json.dumps(registros, ensure_ascii=False, indent=2, default=str).encode('utf-8')


def pdf_para_txt(dados):
    leitor = PdfReader(io.BytesIO(dados))
    paginas = []
    for numero, pagina in enumerate(leitor.pages, start=1):
        paginas.append(f'--- Página {numero} ---\n' + (pagina.extract_text() or ''))
    return '\n\n'.join(paginas).encode('utf-8')


def pdf_para_docx(dados):
    # o pdf2docx trabalha com arquivos, então usamos uma pasta temporária
    with tempfile.TemporaryDirectory() as pasta:
        caminho_pdf = os.path.join(pasta, 'entrada.pdf')
        caminho_docx = os.path.join(pasta, 'saida.docx')
        with open(caminho_pdf, 'wb') as f:
            f.write(dados)
        conversor = pdf2docx.Converter(caminho_pdf)
        try:
            conversor.convert(caminho_docx)
        finally:
            conversor.close()
        with open(caminho_docx, 'rb') as f:
            return f.read()


def pdf_para_imagens(dados):
    documento = fitz.open(stream=dados, filetype='pdf')
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as pacote:
        for numero, pagina in enumerate(documento, start=1):
            pacote.writestr(f'pagina_{numero}.png', pagina.get_pixmap(dpi=150).tobytes('png'))
    return buffer.getvalue()


def docx_para_txt(dados):
    documento = docx.Document(io.BytesIO(dados))
    return '\n'.join(p.text for p in documento.paragraphs).encode('utf-8')


def converter(dados, entrada, saida, separador=','):
    """Recebe os bytes do arquivo e devolve os bytes convertidos."""
    entrada = normalizar(entrada)
    if saida not in opcoes_de_saida(entrada):
        raise ValueError('Essa conversão não está disponível.')
    if entrada in FORMATOS_IMAGEM:
        return converter_imagem(dados, saida)
    if entrada in ('csv', 'xlsx', 'json'):
        return converter_dados(dados, entrada, saida, separador)
    if entrada == 'pdf':
        if saida == 'txt':
            return pdf_para_txt(dados)
        if saida == 'docx':
            return pdf_para_docx(dados)
        if saida == 'zip':
            return pdf_para_imagens(dados)
    if entrada == 'docx' and saida == 'txt':
        return docx_para_txt(dados)
    raise ValueError('Essa conversão ainda não é suportada.')


# ---------------------------------------------------------------- tela

def mostrar_conversor():
    st.subheader('🔄 Conversor de arquivos')
    st.caption('Envie um arquivo, escolha o formato e baixe o resultado. '
               'O arquivo é convertido na hora e não fica guardado.')

    if INDISPONIVEIS:
        with st.expander('Algumas conversões não estão disponíveis neste computador'):
            st.write('Estas bibliotecas não carregaram (o Windows pode ter bloqueado): '
                     + ', '.join(INDISPONIVEIS) + '.')

    arquivo = st.file_uploader('Envie o arquivo', type=extensoes_aceitas())
    if not arquivo:
        return

    if arquivo.size > TAMANHO_MAXIMO_MB * 1024 * 1024:
        st.error(f'O arquivo passa de {TAMANHO_MAXIMO_MB} MB. Envie um arquivo menor.')
        return

    nome_base, _, extensao = arquivo.name.rpartition('.')
    entrada = normalizar(extensao)
    saidas = opcoes_de_saida(entrada)
    if not saidas:
        st.warning('Não tenho conversões disponíveis para esse tipo de arquivo.')
        return

    saida = st.selectbox('Converter para', saidas,
                         format_func=lambda f: NOMES_BONITOS.get(f, f.upper()))

    separador = ','
    if saida == 'csv':
        separador = st.radio('Separador do CSV', [',', ';'], horizontal=True,
                             help='O Excel em português costuma abrir melhor com ponto e vírgula (;).')

    if st.button('Converter', type='primary'):
        try:
            with st.spinner('Convertendo ...'):
                resultado = converter(arquivo.getvalue(), entrada, saida, separador)
        except Exception as erro:
            st.error(f'Não consegui converter esse arquivo: {erro}')
            return
        st.success('Pronto! Baixe o arquivo abaixo.')
        st.download_button(
            label=f'⬇️ Baixar {nome_base}.{saida}',
            data=resultado,
            file_name=f'{nome_base}.{saida}',
            mime=MIMES.get(saida, 'application/octet-stream'),
        )
