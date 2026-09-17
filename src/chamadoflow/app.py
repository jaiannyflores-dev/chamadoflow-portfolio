import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
import subprocess
import json
import time
from .parser_xml import ler_xml
from .rules import analisar_chamado_operacional, converter_data
from .templates import (
    MODELOS_ATUALIZACAO_JIRA,
    gerar_atualizacao_jira,
    gerar_mensagens,
    gerar_mensagem_strike_manual,
    sugerir_objetivo,
)
from .contatos import atualizar_base, localizar_contato_por_nome, salvar_base
from .excel_export import exportar_filas_para_excel
from .paths import caminho_app
from .versao import nome_completo_app

class HelpDeskAgent(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(nome_completo_app())
        self.geometry("1450x1000")
        self.state("zoomed")
        self.minsize(1100, 650)
        self.chamados = []
        self.resultados = []
        self.arquivo_xml = None
        self.arquivos_xml = []
        self.chamados_por_chave = {}
        self.registros_por_iid = {}
        self.filtro_ativo = "todos"
        self.caminho_base_contatos = caminho_app("data", "contatos_chat.json")
        self.base_contatos = {"contatos": {}}
        self.contato_chat_atual = None
        self.email_chat_atual = ""
        self.chamado_selecionado = None
        self.resultado_selecionado = None
        self.mensagens_geradas = None
        self.nome_chat_atual = ""
        self.coluna_ordenacao = None
        self.ordem_decrescente = False
        self.criar_interface()
    # ==================================================
    # INTERFACE
    # ==================================================
    def criar_interface(self):
        topo = ttk.Frame(
            self,
            padding=10
        )
        topo.pack(
            fill="x"
        )
        self.label_arquivo = ttk.Label(
            topo,
            text="Nenhum XML selecionado"
        )
        self.label_arquivo.pack(
            side="left",
            padx=(0, 15)
        )
        ttk.Button(
            topo,
            text="Selecionar XMLs",
            command=self.selecionar_xml
        ).pack(
            side="left",
            padx=5
        )
        self.botao_analisar = ttk.Button(
            topo,
            text="Reanalisar",
            command=self.analisar_xml,
            state="disabled"
        )
        self.botao_analisar.pack(
            side="left",
            padx=5
        )
        self.botao_resumo_responsaveis = ttk.Button(
            topo,
            text="Resumo por responsável",
            command=self.mostrar_resumo_responsaveis,
            state="disabled"
        )
        self.botao_resumo_responsaveis.pack(
            side="right",
            padx=(10, 0)
        )
        self.botao_exportar_excel = ttk.Button(
            topo,
            text="Exportar Excel",
            command=self.exportar_excel_filas,
            state="disabled",
        )
        self.botao_exportar_excel.pack(
            side="right",
            padx=(10, 0),
        )
        self.label_total = ttk.Label(
            topo,
            text=""
        )
        self.label_total.pack(
            side="right"
        )
        self.frame_contadores = ttk.Frame(self, padding=(10, 0, 10, 5))
        self.frame_contadores.pack(fill="x")
        self.botoes_filtro = {}
        for codigo, texto in (
            ("todos", "Todos"),
            ("vip", "VIP"),
            ("alta", "Prioridade alta"),
            ("manual", "Validação manual"),
            ("sla", "SLA estourado"),
        ):
            botao = ttk.Button(
                self.frame_contadores,
                text=f"{texto} (0)",
                command=lambda c=codigo: self.aplicar_filtro(c),
                state="disabled",
            )
            botao.pack(side="left", padx=2)
            self.botoes_filtro[codigo] = botao
        # ----------------------------------------------
        # TABELA
        # ----------------------------------------------
        frame_tabela = ttk.Frame(
            self,
            padding=(10, 0, 10, 10)
        )
        frame_tabela.pack(
            fill="x",
            expand=False
        )
        colunas = (
            "prioridade",
            "fila",
            "chave",
            "status",
            "sem_atualizacao",
            "situacao",
            "quem",
            "acao",
            "strike",
            "confianca",
        )
        self.tabela = ttk.Treeview(
            frame_tabela,
            columns=colunas,
            show="headings",
            selectmode="browse",
            height=10
        )
        self.tabela.heading(
            "prioridade",
            text="Prioridade",
            command=lambda c="prioridade": self.ordenar_tabela(c)
        )
        self.tabela.heading(
            "fila",
            text="Fila",
            command=lambda c="fila": self.ordenar_tabela(c)
        )
        self.tabela.heading(
            "chave",
            text="Chamado",
            command=lambda c="chave": self.ordenar_tabela(c)
        )
        self.tabela.heading(
            "status",
            text="Status Jira",
            command=lambda c="status": self.ordenar_tabela(c)
        )
        self.tabela.heading(
            "sem_atualizacao",
            text="Sem atualização",
            command=lambda c="sem_atualizacao": self.ordenar_tabela(c)
        )
        self.tabela.heading(
            "situacao",
            text="Situação",
            command=lambda c="situacao": self.ordenar_tabela(c)
        )
        self.tabela.heading(
            "quem",
            text="Quem precisa agir",
            command=lambda c="quem": self.ordenar_tabela(c)
        )
        self.tabela.heading(
            "acao",
            text="O que fazer agora",
            command=lambda c="acao": self.ordenar_tabela(c)
        )
        self.tabela.heading(
            "strike",
            text="Strike",
            command=lambda c="strike": self.ordenar_tabela(c)
        )
        self.tabela.heading(
            "confianca",
            text="Confiança",
            command=lambda c="confianca": self.ordenar_tabela(c)
        )
        self.tabela.column(
            "prioridade",
            width=110,
            anchor="center"
        )
        self.tabela.column("fila", width=140)
        self.tabela.column(
            "chave",
            width=110
        )
        self.tabela.column(
            "status",
            width=140
        )
        self.tabela.column("sem_atualizacao", width=125, anchor="center")
        self.tabela.column(
            "situacao",
            width=210
        )
        self.tabela.column(
            "quem",
            width=190
        )
        self.tabela.column(
            "acao",
            width=430
        )
        self.tabela.column(
            "strike",
            width=80,
            anchor="center"
        )
        self.tabela.column(
            "confianca",
            width=85,
            anchor="center"
        )
        scroll_y = ttk.Scrollbar(
            frame_tabela,
            orient="vertical",
            command=self.tabela.yview
        )
        scroll_x = ttk.Scrollbar(
            frame_tabela,
            orient="horizontal",
            command=self.tabela.xview
        )
        self.tabela.configure(
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set
        )
        self.tabela.tag_configure("atualizacao_alerta", foreground="#9A6700")
        self.tabela.tag_configure("atualizacao_critica", foreground="#B42318")
        self.tabela.grid(
            row=0,
            column=0,
            sticky="nsew"
        )
        scroll_y.grid(
            row=0,
            column=1,
            sticky="ns"
        )
        scroll_x.grid(
            row=1,
            column=0,
            sticky="ew"
        )
        frame_tabela.rowconfigure(
            0,
            weight=1
        )
        frame_tabela.columnconfigure(
            0,
            weight=1
        )
        # ----------------------------------------------
        # DETALHES DO CHAMADO
        # ----------------------------------------------
        # Área inferior rolável. A tabela permanece fixa no topo e
        # somente os detalhes rolam, evitando que os controles inferiores
        # desapareçam em telas menores.
        frame_scroll_detalhes = ttk.Frame(self)
        frame_scroll_detalhes.pack(
            fill="both", expand=True, padx=10, pady=(0, 5)
        )
        self.canvas_detalhes = tk.Canvas(
            frame_scroll_detalhes, highlightthickness=0
        )
        scroll_detalhes = ttk.Scrollbar(
            frame_scroll_detalhes,
            orient="vertical",
            command=self.canvas_detalhes.yview
        )
        self.canvas_detalhes.configure(
            yscrollcommand=scroll_detalhes.set
        )
        self.canvas_detalhes.pack(
            side="left", fill="both", expand=True
        )
        scroll_detalhes.pack(side="right", fill="y")
        frame_detalhes = ttk.LabelFrame(
            self.canvas_detalhes,
            text="Detalhes do chamado",
            padding=10
        )
        self._janela_detalhes = self.canvas_detalhes.create_window(
            (0, 0), window=frame_detalhes, anchor="nw"
        )
        frame_detalhes.bind(
            "<Configure>", self._atualizar_scroll_detalhes
        )
        self.canvas_detalhes.bind(
            "<Configure>", self._ajustar_largura_detalhes
        )
        self.canvas_detalhes.bind_all(
            "<MouseWheel>", self._rolar_detalhes
        )
        # Cabeçalho
        self.label_detalhe_chave = ttk.Label(
            frame_detalhes,
            text="Selecione um chamado",
            font=("Segoe UI", 11, "bold")
        )
        self.label_detalhe_chave.pack(
            anchor="w"
        )
        self.label_detalhe_resumo = ttk.Label(
            frame_detalhes,
            text="",
            wraplength=1250
        )
        self.label_detalhe_resumo.pack(
            anchor="w",
            pady=(2, 10)
        )
        # Informações principais
        frame_info = ttk.Frame(
            frame_detalhes
        )
        frame_info.pack(
            fill="x"
        )
        self.label_detalhe_situacao = ttk.Label(
            frame_info,
            text="Situação: -"
        )
        self.label_detalhe_situacao.grid(
            row=0,
            column=0,
            sticky="w",
            padx=(0, 30),
            pady=2
        )
        self.label_detalhe_responsavel = ttk.Label(
            frame_info,
            text="Responsável: -"
        )
        self.label_detalhe_responsavel.grid(
            row=0,
            column=1,
            sticky="w",
            padx=(0, 30),
            pady=2
        )
        self.label_detalhe_quem = ttk.Label(
            frame_info,
            text="Quem precisa agir: -"
        )
        self.label_detalhe_quem.grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 30),
            pady=2
        )
        self.label_detalhe_strike = ttk.Label(
            frame_info,
            text="Strike: -"
        )
        self.label_detalhe_strike.grid(
            row=1,
            column=1,
            sticky="w",
            padx=(0, 30),
            pady=2
        )
        self.label_detalhe_confianca = ttk.Label(
            frame_info,
            text="Confiança: -"
        )
        self.label_detalhe_confianca.grid(
            row=1,
            column=2,
            sticky="w",
            pady=2
        )
        # Pessoas para contato
        frame_pessoas = ttk.LabelFrame(
            frame_detalhes,
            text="Pessoas para contato",
            padding=8
        )
        frame_pessoas.pack(
            fill="x",
            pady=(10, 0)
        )
        frame_pessoas.columnconfigure(1, weight=1)
        ttk.Label(frame_pessoas, text="Solicitante:").grid(
            row=0, column=0, sticky="w", padx=(0, 8), pady=2
        )
        self.label_solicitante_nome = ttk.Label(frame_pessoas, text="-")
        self.label_solicitante_nome.grid(
            row=0, column=1, sticky="w", pady=2
        )
        self.botao_copiar_solicitante = ttk.Button(
            frame_pessoas,
            text="Copiar nome",
            command=self.copiar_solicitante,
            state="disabled"
        )
        self.botao_copiar_solicitante.grid(
            row=0, column=2, sticky="e", padx=(8, 0), pady=2
        )
        ttk.Label(frame_pessoas, text="Aprovador:").grid(
            row=1, column=0, sticky="w", padx=(0, 8), pady=2
        )
        self.label_aprovador_nome = ttk.Label(frame_pessoas, text="-")
        self.label_aprovador_nome.grid(
            row=1, column=1, sticky="w", pady=2
        )
        self.botao_copiar_aprovador = ttk.Button(
            frame_pessoas,
            text="Copiar nome",
            command=self.copiar_aprovador,
            state="disabled"
        )
        self.botao_copiar_aprovador.grid(
            row=1, column=2, sticky="e", padx=(8, 0), pady=2
        )
        ttk.Label(
            frame_pessoas,
            text="Quem procurar no Chat:",
            font=("Segoe UI", 9, "bold")
        ).grid(
            row=2, column=0, sticky="w", padx=(0, 8), pady=(6, 2)
        )
        self.label_nome_chat = ttk.Label(
            frame_pessoas,
            text="-",
            font=("Segoe UI", 9, "bold")
        )
        self.label_nome_chat.grid(
            row=2, column=1, sticky="w", pady=(6, 2)
        )
        self.botao_copiar_chat = ttk.Button(
            frame_pessoas,
            text="Copiar nome",
            command=self.copiar_nome_chat,
            state="disabled"
        )
        self.botao_copiar_chat.grid(
            row=2, column=2, sticky="e", padx=(8, 0), pady=(6, 2)
        )
        self.botao_abrir_chat = ttk.Button(
            frame_pessoas,
            text="Abrir no Google Chat",
            command=self.abrir_chat,
            state="disabled"
        )
        self.botao_abrir_chat.grid(
            row=2, column=3, sticky="e", padx=(8, 0), pady=(6, 2)
        )
        self.botao_salvar_link_chat = ttk.Button(
            frame_pessoas,
            text="Salvar link do Chat",
            command=self.salvar_link_chat,
            state="disabled"
        )
        self.botao_salvar_link_chat.grid(
            row=2, column=4, sticky="e", padx=(8, 0), pady=(6, 2)
        )
        ttk.Label(frame_pessoas, text="E-mail para busca:").grid(
            row=3, column=0, sticky="w", padx=(0, 8), pady=(2, 0)
        )
        self.label_email_chat = ttk.Label(frame_pessoas, text="-")
        self.label_email_chat.grid(
            row=3, column=1, sticky="w", pady=(2, 0)
        )
        # Ação
        ttk.Label(
            frame_detalhes,
            text="O que fazer agora:",
            font=("Segoe UI", 9, "bold")
        ).pack(
            anchor="w",
            pady=(10, 2)
        )
        self.label_detalhe_acao = ttk.Label(
            frame_detalhes,
            text="-",
            wraplength=1250
        )
        self.label_detalhe_acao.pack(
            anchor="w"
        )
        # Último comentário
        ttk.Label(
            frame_detalhes,
            text="Último comentário:",
            font=("Segoe UI", 9, "bold")
        ).pack(
            anchor="w",
            pady=(10, 2)
        )
        self.texto_comentario = tk.Text(
            frame_detalhes,
            height=3,
            wrap="word",
            state="disabled"
        )
        self.texto_comentario.pack(
            fill="x"
        )
        # Destinatário da mensagem. O agente sugere automaticamente,
        # mas a escolha final fica com a usuária.
        frame_destino = ttk.LabelFrame(
            frame_detalhes,
            text="Enviar mensagem para",
            padding=8
        )
        frame_destino.pack(fill="x", pady=(10, 0))
        self.var_destino = tk.StringVar(value="")
        self.radio_demandante = ttk.Radiobutton(
            frame_destino,
            text="Demandante",
            value="Demandante",
            variable=self.var_destino,
            command=self._destino_alterado
        )
        self.radio_demandante.pack(side="left", padx=(0, 18))
        self.radio_aprovador = ttk.Radiobutton(
            frame_destino,
            text="Aprovador",
            value="Aprovador",
            variable=self.var_destino,
            command=self._destino_alterado
        )
        self.radio_aprovador.pack(side="left", padx=(0, 18))
        self.radio_responsavel = ttk.Radiobutton(
            frame_destino,
            text="Responsável",
            value="Responsável",
            variable=self.var_destino,
            command=self._destino_alterado
        )
        self.radio_responsavel.pack(side="left")
        self.label_destinatario_escolhido = ttk.Label(
            frame_destino, text=""
        )
        self.label_destinatario_escolhido.pack(
            side="left", padx=(25, 0)
        )
        # Objetivo sugerido
        ttk.Label(
            frame_detalhes,
            text="Objetivo sugerido:",
            font=("Segoe UI", 9, "bold")
        ).pack(
            anchor="w",
            pady=(10, 2)
        )
        self.var_objetivo = tk.StringVar()
        self.combo_objetivo = ttk.Combobox(
            frame_detalhes,
            textvariable=self.var_objetivo,
            values=[],
            state="disabled"
        )
        self.combo_objetivo.pack(
            fill="x"
        )
        # Botões principais
        frame_botoes = ttk.Frame(
            frame_detalhes
        )
        frame_botoes.pack(
            fill="x",
            pady=(10, 0)
        )
        self.botao_abrir_jira = ttk.Button(
            frame_botoes,
            text="Abrir no Jira",
            command=self.abrir_jira,
            state="disabled"
        )
        self.botao_abrir_jira.pack(
            side="left"
        )
        self.botao_gerar_mensagens = ttk.Button(
            frame_botoes,
            text="Gerar mensagens",
            command=self.gerar_mensagens_selecionado,
            state="disabled"
        )
        self.botao_gerar_mensagens.pack(
            side="left",
            padx=(8, 0)
        )
        # Mensagem para contato
        ttk.Label(
            frame_detalhes,
            text="Mensagem para contato:",
            font=("Segoe UI", 9, "bold")
        ).pack(
            anchor="w",
            pady=(10, 2)
        )
        self.texto_mensagem_contato = tk.Text(
            frame_detalhes,
            height=5,
            wrap="word",
            state="disabled"
        )
        self.texto_mensagem_contato.pack(
            fill="x"
        )
        self.botao_copiar_contato = ttk.Button(
            frame_detalhes,
            text="Copiar mensagem",
            command=self.copiar_mensagem_contato,
            state="disabled"
        )
        self.botao_copiar_contato.pack(
            anchor="w",
            pady=(4, 0)
        )
        frame_atualizacao_jira = ttk.LabelFrame(
            frame_detalhes,
            text="Atualização para o Jira",
            padding=8,
        )
        frame_atualizacao_jira.pack(fill="x", pady=(10, 0))
        ttk.Label(
            frame_atualizacao_jira,
            text="Resultado do contato:",
        ).pack(anchor="w")
        self.var_atualizacao_jira = tk.StringVar(value="")
        self.combo_atualizacao_jira = ttk.Combobox(
            frame_atualizacao_jira,
            textvariable=self.var_atualizacao_jira,
            values=list(MODELOS_ATUALIZACAO_JIRA),
            state="readonly",
        )
        self.combo_atualizacao_jira.pack(fill="x", pady=(2, 6))
        self.combo_atualizacao_jira.bind(
            "<<ComboboxSelected>>",
            self._atualizacao_jira_alterada,
        )
        self.texto_atualizacao_jira = tk.Text(
            frame_atualizacao_jira,
            height=4,
            wrap="word",
        )
        self.texto_atualizacao_jira.pack(fill="x")
        self.botao_copiar_atualizacao_jira = ttk.Button(
            frame_atualizacao_jira,
            text="Copiar atualização",
            command=self.copiar_atualizacao_jira,
            state="disabled",
        )
        self.botao_copiar_atualizacao_jira.pack(anchor="w", pady=(4, 0))
        # Nota Jira / Strike
        ttk.Label(
            frame_detalhes,
            text="Nota Jira / Strike:",
            font=("Segoe UI", 9, "bold")
        ).pack(
            anchor="w",
            pady=(10, 2)
        )
        self.texto_mensagem_strike = tk.Text(
            frame_detalhes,
            height=5,
            wrap="word",
            state="disabled"
        )
        self.texto_mensagem_strike.pack(
            fill="x"
        )
        self.botao_copiar_strike = ttk.Button(
            frame_detalhes,
            text="Copiar nota Jira",
            command=self.copiar_mensagem_strike,
            state="disabled"
        )
        self.botao_copiar_strike.pack(
            anchor="w",
            pady=(4, 0)
        )
        frame_strike_manual = ttk.LabelFrame(
            frame_detalhes,
            text="Geração manual de Strike",
            padding=8,
        )
        frame_strike_manual.pack(fill="x", pady=(10, 0))
        self.label_strike_manual = ttk.Label(
            frame_strike_manual,
            text=(
                "Use quando a tentativa sem resposta já ocorreu, mas "
                "ainda não apareceu no XML."
            ),
            wraplength=420,
        )
        self.label_strike_manual.pack(anchor="w")
        self.botao_gerar_strike_manual = ttk.Button(
            frame_strike_manual,
            text="Gerar Strike manual",
            command=self.gerar_strike_manual_selecionado,
            state="disabled",
        )
        self.botao_gerar_strike_manual.pack(anchor="w", pady=(6, 0))
        self.tabela.bind(
            "<<TreeviewSelect>>",
            self.mostrar_detalhes
        )
        # ----------------------------------------------
        # ----------------------------------------------
        # RODAPÉ
        # ----------------------------------------------
        rodape = ttk.Frame(
            self,
            padding=10
        )
        rodape.pack(
            fill="x"
        )
        self.label_status = ttk.Label(
            rodape,
            text="Pronto."
        )
        self.label_status.pack(
            side="left"
        )
        self.label_versao = ttk.Label(
            rodape,
            text=nome_completo_app(),
        )
        self.label_versao.pack(side="right")
    def _atualizar_scroll_detalhes(self, event=None):
        self.canvas_detalhes.configure(
            scrollregion=self.canvas_detalhes.bbox("all")
        )
    def _ajustar_largura_detalhes(self, event):
        self.canvas_detalhes.itemconfigure(
            self._janela_detalhes, width=event.width
        )
    def _rolar_detalhes(self, event):
        # Só rola quando o ponteiro estiver sobre a metade inferior.
        try:
            x, y = self.winfo_pointerxy()
            widget = self.winfo_containing(x, y)
            if widget and self._eh_descendente(widget, self.canvas_detalhes):
                self.canvas_detalhes.yview_scroll(
                    int(-1 * (event.delta / 120)), "units"
                )
        except Exception:
            pass
    def _eh_descendente(self, widget, ancestral):
        atual = widget
        while atual is not None:
            if atual == ancestral:
                return True
            try:
                nome_pai = atual.winfo_parent()
                if not nome_pai:
                    break
                atual = atual._nametowidget(nome_pai)
            except Exception:
                break
        return False
    # ==================================================
    # SELEÇÃO DO XML
    # ==================================================
    def selecionar_xml(self):
        arquivos = filedialog.askopenfilenames(
            title="Selecionar exportações XML do Jira",
            initialdir=str(
                caminho_app("xml")
            ),
            filetypes=[
                (
                    "Arquivos XML",
                    "*.xml"
                ),
                (
                    "Todos os arquivos",
                    "*.*"
                ),
            ]
        )
        if not arquivos:
            return
        self.arquivos_xml = list(arquivos)
        self.arquivo_xml = self.arquivos_xml[0]
        self.label_arquivo.config(
            text=(
                Path(self.arquivos_xml[0]).name
                if len(self.arquivos_xml) == 1
                else f"{len(self.arquivos_xml)} XMLs selecionados"
            )
        )
        self.botao_analisar.config(state="normal")
        self.analisar_xml()
    # ==================================================
    # ANÁLISE
    # ==================================================
    def analisar_xml(self):
        arquivos = self.arquivos_xml or (
            [self.arquivo_xml] if self.arquivo_xml else []
        )
        if not arquivos:
            messagebox.showwarning(
                "HelpDeskAgent",
                "Selecione primeiro o XML exportado do Jira."
            )
            return
        try:
            self.label_status.config(
                text="Analisando chamados..."
            )
            self.update_idletasks()
            chamados = self._ler_e_consolidar_chamados(arquivos)
            self.base_contatos = atualizar_base(
                self.caminho_base_contatos,
                caminho_app("contacts.csv"),
                chamados,
            )
            resultados = []
            for chamado in chamados:
                resultado = analisar_chamado_operacional(
                    chamado
                )
                resultados.append(
                    resultado
                )
            resultados.sort(
                key=lambda item: (
                    {
                        "SLA estourado": 0,
                        "Alta": 1,
                        "Normal": 2,
                    }.get(item.get("prioridade"), 3),
                    -(
                        item.get("horas_sem_atualizacao")
                        if item.get("horas_sem_atualizacao") is not None
                        else -1
                    ),
                    item.get("chave") or ""
                )
            )
            self.chamados = chamados
            self.chamados_por_chave = {
                chamado.get("chave"): chamado
                for chamado in chamados
                if chamado.get("chave")
            }
            self.resultados = resultados
            self.filtro_ativo = "todos"
            self.preencher_tabela()
            self.botao_resumo_responsaveis.config(
                state="normal"
            )
            self.botao_exportar_excel.config(state="normal")
            self.atualizar_contadores()
            self.label_status.config(
                text=(
                    f"Análise concluída: {len(resultados)} chamados "
                    f"em {len(arquivos)} XML(s)."
                )
            )
        except Exception as erro:
            messagebox.showerror(
                "Erro ao analisar XML",
                str(erro)
            )
            self.label_status.config(
                text="Erro durante a análise."
            )

    def _ler_e_consolidar_chamados(self, arquivos):
        chamados_por_chave = {}

        for arquivo in arquivos:
            fila_arquivo = Path(arquivo).stem

            for chamado in ler_xml(arquivo):
                chamado = dict(chamado)
                fila = str(chamado.get("time_solucionador") or "").strip()
                fila = fila or fila_arquivo
                chamado["fila_origem"] = fila
                chamado["filas_origem"] = [fila]
                chave = chamado.get("chave")

                if not chave:
                    continue

                existente = chamados_por_chave.get(chave)

                if existente is None:
                    chamados_por_chave[chave] = chamado
                    continue

                filas = sorted(
                    set(existente["filas_origem"] + chamado["filas_origem"])
                )
                data_existente = converter_data(existente.get("atualizado"))
                data_nova = converter_data(chamado.get("atualizado"))

                if data_nova is not None and (
                    data_existente is None or data_nova > data_existente
                ):
                    chamado["filas_origem"] = filas
                    chamados_por_chave[chave] = chamado
                else:
                    existente["filas_origem"] = filas

        chamados = list(chamados_por_chave.values())

        for chamado in chamados:
            chamado["fila_origem"] = ", ".join(
                chamado["filas_origem"]
            )

        return chamados

    def exportar_excel_filas(self):
        if not self.resultados:
            messagebox.showwarning(
                "Exportar Excel",
                "Analise pelo menos um XML antes de exportar.",
            )
            return

        nome_arquivo = time.strftime("filas_%Y-%m-%d_%H%M.xlsx")
        caminho = filedialog.asksaveasfilename(
            title="Salvar filas em Excel",
            initialdir=str(caminho_app("exports")),
            initialfile=nome_arquivo,
            defaultextension=".xlsx",
            filetypes=[("Planilha Excel", "*.xlsx")],
        )
        if not caminho:
            return

        filas_por_chave = {}
        for chamado in self.chamados:
            chave = chamado.get("chave")
            if not chave:
                continue
            filas = chamado.get("filas_origem") or [
                chamado.get("fila_origem")
            ]
            if isinstance(filas, str):
                filas = [filas]
            for fila in filas:
                fila = str(fila or "").strip()
                if fila:
                    filas_por_chave.setdefault(fila, []).append(chave)

        try:
            exportar_filas_para_excel(
                caminho,
                self.resultados,
                self.chamados_por_chave,
                filas_por_chave,
            )
        except OSError as erro:
            messagebox.showerror("Erro ao exportar Excel", str(erro))
            return

        self.label_status.config(
            text=(
                "Excel exportado: uma aba consolidada e "
                f"{len(filas_por_chave)} aba(s) por fila."
            )
        )

    def atualizar_contadores(self):
        contagens = {
            "todos": len(self.resultados),
            "vip": sum(item.get("vip", False) for item in self.resultados),
            "alta": sum(
                item.get("prioridade") == "Alta"
                for item in self.resultados
            ),
            "manual": sum(
                item.get("requer_validacao_manual", False)
                for item in self.resultados
            ),
            "sla": sum(
                item.get("prioridade") == "SLA estourado"
                for item in self.resultados
            ),
        }
        rotulos = {
            "todos": "Todos",
            "vip": "VIP",
            "alta": "Prioridade alta",
            "manual": "Validação manual",
            "sla": "SLA estourado",
        }

        for codigo, botao in self.botoes_filtro.items():
            marcador = "• " if codigo == self.filtro_ativo else ""
            botao.config(
                text=f"{marcador}{rotulos[codigo]} ({contagens[codigo]})",
                state="normal",
            )

        self.label_total.config(
            text=f"{len(self.resultados)} chamados consolidados"
        )

    def aplicar_filtro(self, filtro):
        self.filtro_ativo = filtro
        self.preencher_tabela()
        self.atualizar_contadores()
        self.label_status.config(
            text=f"Filtro aplicado: {self.botoes_filtro[filtro].cget('text')}"
        )

    def _resultados_visiveis(self):
        if self.filtro_ativo == "vip":
            return [item for item in self.resultados if item.get("vip")]
        if self.filtro_ativo == "alta":
            return [
                item for item in self.resultados
                if item.get("prioridade") == "Alta"
            ]
        if self.filtro_ativo == "manual":
            return [
                item for item in self.resultados
                if item.get("requer_validacao_manual")
            ]
        if self.filtro_ativo == "sla":
            return [
                item for item in self.resultados
                if item.get("prioridade") == "SLA estourado"
            ]

        return self.resultados

    def _formatar_horas_sem_atualizacao(self, horas):
        if horas is None:
            return "Não identificado"

        minutos_totais = max(0, round(horas * 60))
        horas_inteiras, minutos = divmod(minutos_totais, 60)

        return f"{horas_inteiras}h {minutos:02}min"
    # ==================================================
    # TABELA
    # ==================================================
    def preencher_tabela(self):
        for item in self.tabela.get_children():
            self.tabela.delete(
                item
            )
        self.registros_por_iid = {}
        self.chamado_selecionado = None
        self.resultado_selecionado = None

        for indice, resultado in enumerate(self._resultados_visiveis()):
            strike_atual = resultado.get(
                "strike_atual",
                0
            )
            horas_sem_atualizacao = resultado.get("horas_sem_atualizacao")
            tempo_sem_atualizacao = self._formatar_horas_sem_atualizacao(
                horas_sem_atualizacao
            )
            tags = ()

            if horas_sem_atualizacao is not None:
                if horas_sem_atualizacao > 10:
                    tags = ("atualizacao_critica",)
                elif horas_sem_atualizacao >= 2:
                    tags = ("atualizacao_alerta",)

            if strike_atual:
                strike_texto = (
                    f"Strike {strike_atual}"
                )
            else:
                strike_texto = "-"
            iid = f"resultado_{indice}"
            chamado = self.chamados_por_chave.get(resultado.get("chave"))
            self.registros_por_iid[iid] = (chamado, resultado)
            self.tabela.insert(
                "",
                "end",
                iid=iid,
                tags=tags,
                values=(
                    resultado.get(
                        "prioridade",
                        ""
                    ),
                    resultado.get(
                        "fila_origem",
                        ""
                    ),
                    resultado.get(
                        "chave",
                        ""
                    ),
                    resultado.get(
                        "status_jira",
                        ""
                    ),
                    tempo_sem_atualizacao,
                    resultado.get(
                        "situacao",
                        ""
                    ),
                    resultado.get(
                        "quem_precisa_agir",
                        ""
                    ),
                    resultado.get(
                        "acao_final",
                        ""
                    ),
                    strike_texto,
                    resultado.get(
                        "confianca",
                        ""
                    ),
                )
            )
    def ordenar_tabela(self, coluna):
        if self.coluna_ordenacao == coluna:
            self.ordem_decrescente = not self.ordem_decrescente
        else:
            self.coluna_ordenacao = coluna
            self.ordem_decrescente = False
        itens = list(self.tabela.get_children(""))
        indice_coluna = {
            "prioridade": 0,
            "fila": 1,
            "chave": 2,
            "status": 3,
            "sem_atualizacao": 4,
            "situacao": 5,
            "quem": 6,
            "acao": 7,
            "strike": 8,
            "confianca": 9,
        }[coluna]
        def chave_ordenacao(iid):
            valores = self.tabela.item(iid, "values")
            valor = str(valores[indice_coluna] if len(valores) > indice_coluna else "")
            if coluna == "sem_atualizacao":
                _, resultado = self.registros_por_iid.get(iid, (None, {}))
                horas = resultado.get("horas_sem_atualizacao")
                return horas if horas is not None else -1
            if coluna == "strike":
                match = __import__("re").search(r"(\d+)", valor)
                return int(match.group(1)) if match else 0
            if coluna == "chave":
                match = __import__("re").match(r"(.+?)-(\d+)$", valor)
                if match:
                    return (match.group(1).lower(), int(match.group(2)))
            return valor.casefold()
        itens.sort(
            key=chave_ordenacao,
            reverse=self.ordem_decrescente
        )
        for posicao, iid in enumerate(itens):
            self.tabela.move(iid, "", posicao)
        nomes = {
            "prioridade": "Prioridade",
            "fila": "Fila",
            "chave": "Chamado",
            "status": "Status Jira",
            "sem_atualizacao": "Sem atualização",
            "situacao": "Situação",
            "quem": "Quem precisa agir",
            "acao": "O que fazer agora",
            "strike": "Strike",
            "confianca": "Confiança",
        }
        for codigo, nome in nomes.items():
            indicador = ""
            if codigo == coluna:
                indicador = " ▼" if self.ordem_decrescente else " ▲"
            self.tabela.heading(
                codigo,
                text=nome + indicador,
                command=lambda c=codigo: self.ordenar_tabela(c)
            )
    def mostrar_resumo_responsaveis(self):
        if not self.chamados:
            return
        contagem = {}
        for chamado in self.chamados:
            responsavel = str(
                chamado.get("responsavel") or "Sem responsável"
            ).strip() or "Sem responsável"
            contagem[responsavel] = contagem.get(responsavel, 0) + 1
        janela = tk.Toplevel(self)
        janela.title("Resumo por responsável")
        janela.geometry("620x520")
        janela.minsize(480, 350)
        janela.transient(self)
        frame = ttk.Frame(janela, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame,
            text=f"Responsáveis — {len(self.chamados)} chamados",
            font=("TkDefaultFont", 10, "bold")
        ).pack(anchor="w", pady=(0, 10))
        tabela = ttk.Treeview(
            frame,
            columns=("responsavel", "quantidade"),
            show="headings"
        )
        tabela.column("responsavel", width=430)
        tabela.column("quantidade", width=100, anchor="center")
        ordem = {"coluna": "quantidade", "desc": True}
        def ordenar_resumo(coluna):
            if ordem["coluna"] == coluna:
                ordem["desc"] = not ordem["desc"]
            else:
                ordem["coluna"] = coluna
                ordem["desc"] = coluna == "quantidade"
            itens = list(tabela.get_children(""))
            indice = 0 if coluna == "responsavel" else 1
            def chave(iid):
                valor = tabela.item(iid, "values")[indice]
                return int(valor) if coluna == "quantidade" else str(valor).casefold()
            itens.sort(key=chave, reverse=ordem["desc"])
            for posicao, iid in enumerate(itens):
                tabela.move(iid, "", posicao)
            tabela.heading(
                "responsavel",
                text="Responsável" + (" ▼" if coluna == "responsavel" and ordem["desc"] else " ▲" if coluna == "responsavel" else ""),
                command=lambda: ordenar_resumo("responsavel")
            )
            tabela.heading(
                "quantidade",
                text="Quantidade" + (" ▼" if coluna == "quantidade" and ordem["desc"] else " ▲" if coluna == "quantidade" else ""),
                command=lambda: ordenar_resumo("quantidade")
            )
        tabela.heading(
            "responsavel",
            text="Responsável",
            command=lambda: ordenar_resumo("responsavel")
        )
        tabela.heading(
            "quantidade",
            text="Quantidade ▼",
            command=lambda: ordenar_resumo("quantidade")
        )
        barra = ttk.Scrollbar(frame, orient="vertical", command=tabela.yview)
        tabela.configure(yscrollcommand=barra.set)
        tabela.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        for responsavel, quantidade in sorted(
            contagem.items(),
            key=lambda item: (-item[1], item[0].casefold())
        ):
            tabela.insert("", "end", values=(responsavel, quantidade))
    # ==================================================
    # DETALHES
    # ==================================================
    def mostrar_detalhes(self, event=None):
        selecionado = self.tabela.selection()
        if not selecionado:
            return
        chamado, resultado = self.registros_por_iid.get(
            selecionado[0],
            (None, None),
        )
        if not resultado or not chamado:
            return
        # Guarda seleção atual para os botões.
        self.chamado_selecionado = chamado
        self.resultado_selecionado = resultado
        responsavel = (
            resultado.get("responsavel")
            or "Não identificado"
        )
        strike_atual = resultado.get(
            "strike_atual",
            0
        )
        solicitante_nome = (
            chamado.get("solicitante_nome")
            or chamado.get("solicitante")
            or ""
        ).strip()
        aprovador_nome = (
            chamado.get("aprovador_nome")
            or ""
        ).strip()
        destino_sugerido = self._determinar_destino_sugerido(
            chamado, resultado
        )
        self.var_destino.set(destino_sugerido)
        self._atualizar_estados_destino(chamado, resultado)
        nome_chat = self._nome_por_destino(
            chamado, resultado, destino_sugerido
        )
        self.nome_chat_atual = nome_chat
        self._atualizar_contato_chat(nome_chat)
        self.label_solicitante_nome.config(
            text=solicitante_nome or "Não identificado"
        )
        self.label_aprovador_nome.config(
            text=aprovador_nome or "Não identificado"
        )
        self.label_nome_chat.config(
            text=nome_chat or "Não identificado"
        )
        self.botao_copiar_solicitante.config(
            state="normal" if solicitante_nome else "disabled"
        )
        self.botao_copiar_aprovador.config(
            state="normal" if aprovador_nome else "disabled"
        )
        self.botao_copiar_chat.config(
            state="normal" if nome_chat else "disabled"
        )
        self.botao_abrir_chat.config(
            state="normal" if nome_chat else "disabled"
        )
        if strike_atual:
            strike_texto = f"Strike {strike_atual}"
        else:
            strike_texto = "Nenhum"
        self.label_detalhe_chave.config(
            text=resultado.get(
                "chave",
                ""
            )
        )
        self.label_detalhe_resumo.config(
            text=resultado.get(
                "resumo",
                ""
            )
        )
        self.label_detalhe_situacao.config(
            text=(
                "Situação: "
                f"{resultado.get('situacao', '')}"
            )
        )
        self.label_detalhe_responsavel.config(
            text=(
                "Responsável: "
                f"{responsavel}"
            )
        )
        self.label_detalhe_quem.config(
            text=(
                "Quem precisa agir: "
                f"{resultado.get('quem_precisa_agir', '')}"
            )
        )
        self.label_detalhe_strike.config(
            text=(
                "Strike: "
                f"{strike_texto}"
            )
        )
        self.label_detalhe_confianca.config(
            text=(
                "Confiança: "
                f"{resultado.get('confianca', '')}"
            )
        )
        self.label_detalhe_acao.config(
            text=resultado.get(
                "acao_final",
                ""
            )
        )
        ultimo = chamado.get(
            "ultimo_comentario"
        ) or {}
        comentario = str(
            ultimo.get(
                "texto",
                ""
            )
        ).strip()
        if not comentario:
            comentario = (
                "Nenhum comentário identificado."
            )
        self.texto_comentario.config(
            state="normal"
        )
        self.texto_comentario.delete(
            "1.0",
            "end"
        )
        self.texto_comentario.insert(
            "1.0",
            comentario
        )
        self.texto_comentario.config(
            state="disabled"
        )
        self.botao_abrir_jira.config(
            state="normal"
        )
        try:
            objetivo = self._objetivo_por_destino(
                chamado, resultado, destino_sugerido
            ) or sugerir_objetivo(chamado, resultado)
        except Exception:
            objetivo = ""
        self.var_objetivo.set(
            objetivo
        )
        opcoes_objetivo = self._opcoes_objetivo(
            chamado,
            resultado,
            objetivo
        )
        self.combo_objetivo.config(
            values=opcoes_objetivo,
            state="normal"
        )
        self.label_destinatario_escolhido.config(
            text=f"→ {nome_chat}" if nome_chat else "→ Nome não identificado"
        )
        self.botao_gerar_mensagens.config(
            state="normal"
        )
        self.mensagens_geradas = None
        self._definir_texto(
            self.texto_mensagem_contato,
            "Clique em Gerar mensagens."
        )
        self._definir_texto(
            self.texto_mensagem_strike,
            "Nenhuma mensagem de Strike gerada."
        )
        self.botao_copiar_contato.config(
            state="disabled"
        )
        self.botao_copiar_strike.config(
            state="disabled"
        )
        proximo_strike = resultado.get("proximo_strike")
        if proximo_strike in {1, 2, 3}:
            if strike_atual:
                contexto_strike = f"O XML indica Strike {strike_atual}."
            else:
                contexto_strike = "O XML ainda não indica Strike."
            self.label_strike_manual.config(
                text=(
                    f"{contexto_strike} "
                    f"Você pode gerar manualmente a nota do Strike "
                    f"{proximo_strike} após validar a nova tentativa "
                    f"sem resposta no Jira."
                )
            )
            self.botao_gerar_strike_manual.config(state="normal")
        else:
            self.label_strike_manual.config(
                text=(
                    "Não há próximo Strike disponível: o XML já "
                    "indica Strike 3."
                )
            )
            self.botao_gerar_strike_manual.config(state="disabled")
        self._limpar_atualizacao_jira()
     # ==================================================
    # JIRA
    # ==================================================
    # MENSAGENS
    # ==================================================
    def _determinar_destino_sugerido(self, chamado, resultado):
        alvo = str(
            resultado.get("alvo_contato")
            or resultado.get("quem_precisa_agir")
            or ""
        ).strip().lower()
        if alvo == "aprovador":
            return "Aprovador"
        if alvo in {"demandante", "solicitante", "usuário", "usuario"}:
            return "Demandante"
        return "Responsável"
    def _nome_por_destino(self, chamado, resultado, destino):
        if destino == "Aprovador":
            return (chamado.get("aprovador_nome") or "").strip()
        if destino == "Demandante":
            return (
                chamado.get("solicitante_nome")
                or chamado.get("solicitante")
                or ""
            ).strip()
        if destino == "Responsável":
            return (
                resultado.get("responsavel")
                or chamado.get("responsavel")
                or ""
            ).strip()
        return ""
    def _atualizar_estados_destino(self, chamado, resultado):
        self.radio_demandante.config(
            state="normal" if self._nome_por_destino(
                chamado, resultado, "Demandante"
            ) else "disabled"
        )
        self.radio_aprovador.config(
            state="normal" if self._nome_por_destino(
                chamado, resultado, "Aprovador"
            ) else "disabled"
        )
        self.radio_responsavel.config(
            state="normal" if self._nome_por_destino(
                chamado, resultado, "Responsável"
            ) else "disabled"
        )
    def _destino_alterado(self):
        chamado = self.chamado_selecionado or {}
        resultado = self.resultado_selecionado or {}
        destino = self.var_destino.get()
        nome = self._nome_por_destino(chamado, resultado, destino)
        self.nome_chat_atual = nome
        self._atualizar_contato_chat(nome)
        self.label_nome_chat.config(text=nome or "Não identificado")
        self.botao_copiar_chat.config(
            state="normal" if nome else "disabled"
        )
        self.botao_abrir_chat.config(
            state="normal" if nome else "disabled"
        )
        self.label_destinatario_escolhido.config(
            text=f"→ {nome}" if nome else "→ Nome não identificado"
        )
        objetivo = self._objetivo_por_destino(
            chamado, resultado, destino
        )
        self.var_objetivo.set(objetivo)
        self.combo_objetivo.config(
            values=self._opcoes_objetivo(
                chamado, resultado, objetivo
            )
        )
        self.mensagens_geradas = None
        self._definir_texto(
            self.texto_mensagem_contato,
            "Clique em Gerar mensagens."
        )
        self.botao_copiar_contato.config(state="disabled")
    def _objetivo_por_destino(self, chamado, resultado, destino):
        resumo = str(resultado.get("resumo") or chamado.get("resumo") or "").lower()
        if destino == "Aprovador":
            return "Solicitar aprovação para continuidade do atendimento."
        if destino == "Responsável":
            return "Solicitar atualização sobre o andamento do atendimento."
        termos_problema = (
            "falha", "erro", "não funciona", "nao funciona",
            "não consegue", "nao consegue", "problema",
            "instabilidade", "autenticação", "autenticacao",
            "senha", "acesso"
        )
        if any(termo in resumo for termo in termos_problema):
            return "Verificar se o problema informado no chamado ainda persiste."
        return "Verificar com o demandante se a solicitação ainda necessita de atendimento."
    def _determinar_nome_chat(self, chamado, resultado):
        alvo = str(
            resultado.get("alvo_contato")
            or resultado.get("quem_precisa_agir")
            or ""
        ).strip()
        if alvo.lower() == "aprovador":
            return (chamado.get("aprovador_nome") or "").strip()
        if alvo.lower() in {"demandante", "solicitante", "usuário", "usuario"}:
            return (
                chamado.get("solicitante_nome")
                or chamado.get("solicitante")
                or ""
            ).strip()
        # Quando a regra já devolve o nome de uma pessoa específica,
        # usamos esse nome diretamente.
        genericos = {
            "", "helpdesk", "técnico", "tecnico", "analista",
            "responsável", "responsavel", "aprovador", "demandante"
        }
        if alvo.lower() not in genericos:
            return alvo
        return ""
    def _opcoes_objetivo(self, chamado, resultado, sugerido):
        situacao = str(resultado.get("situacao") or "").lower()
        destino = getattr(self, "var_destino", tk.StringVar(value="")).get()
        alvo = destino.lower() or str(resultado.get("alvo_contato") or "").lower()
        opcoes = []
        if sugerido:
            opcoes.append(sugerido)
        if alvo == "aprovador":
            opcoes.extend([
                "Solicitar aprovação para continuidade do atendimento.",
                "Verificar se a solicitação pode ser atendida.",
                "Solicitar o de acordo para continuidade do chamado."
            ])
        elif alvo == "demandante":
            opcoes.extend([
                "Verificar se o problema informado no chamado ainda persiste.",
                "Verificar com o demandante se a solicitação ainda necessita de atendimento.",
                "Solicitar o melhor horário para continuidade do atendimento."
            ])
        elif alvo in {"responsável", "responsavel"}:
            opcoes.extend([
                "Solicitar atualização sobre o andamento do atendimento.",
                "Verificar se ainda é necessária alguma informação complementar.",
                "Solicitar continuidade do atendimento."
            ])
        # Remove duplicatas preservando a ordem. O Combobox continua
        # editável, então Jai pode escrever qualquer objetivo manualmente.
        return list(dict.fromkeys(opcoes))
    def copiar_solicitante(self):
        chamado = self.chamado_selecionado or {}
        nome = (
            chamado.get("solicitante_nome")
            or chamado.get("solicitante")
            or ""
        ).strip()
        self.copiar_para_area_transferencia(nome, "Nome do solicitante")
    def copiar_aprovador(self):
        chamado = self.chamado_selecionado or {}
        nome = (chamado.get("aprovador_nome") or "").strip()
        self.copiar_para_area_transferencia(nome, "Nome do aprovador")
    def copiar_nome_chat(self):
        self.copiar_para_area_transferencia(
            self.nome_chat_atual,
            "Nome para procurar no Chat"
        )

    def _atualizar_contato_chat(self, nome):
        self.contato_chat_atual = localizar_contato_por_nome(
            self.base_contatos,
            nome,
        )
        self.email_chat_atual = (
            self.contato_chat_atual.get("email", "")
            if self.contato_chat_atual
            else ""
        )
        self.label_email_chat.config(
            text=self.email_chat_atual or "Não identificado"
        )
        self.botao_salvar_link_chat.config(
            state="normal" if self.email_chat_atual else "disabled"
        )

    def salvar_link_chat(self):
        if not self.email_chat_atual:
            messagebox.showwarning(
                "HelpDeskAgent",
                "Não foi possível identificar o e-mail deste contato."
            )
            return

        url = simpledialog.askstring(
            "Salvar link do Google Chat",
            (
                "Abra a conversa correta no Google Chat, copie a URL "
                "do navegador e cole-a abaixo:"
            ),
            parent=self,
        )

        if not url:
            return

        url = url.strip()

        if not url.startswith("https://chat.google.com/"):
            messagebox.showwarning(
                "Link inválido",
                "Informe um link iniciado por https://chat.google.com/"
            )
            return

        registro = self.base_contatos["contatos"].setdefault(
            self.email_chat_atual,
            {"nome": self.nome_chat_atual, "url_chat": ""},
        )
        registro["url_chat"] = url
        salvar_base(self.caminho_base_contatos, self.base_contatos)
        self._atualizar_contato_chat(self.nome_chat_atual)
        self.label_status.config(
            text=f"Link do Google Chat salvo para {self.nome_chat_atual}."
        )

    def abrir_chat(self):
        nome = self.nome_chat_atual.strip()

        if not nome:
            messagebox.showwarning(
                "HelpDeskAgent",
                "Selecione um destinatário com nome disponível."
            )
            return

        url_chat = "https://chat.google.com/"
        url_direta = (
            self.contato_chat_atual.get("url_chat", "")
            if self.contato_chat_atual
            else ""
        )
        texto_busca = self.email_chat_atual or nome
        caminhos_chrome = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]

        try:
            with caminho_app("config.json").open(
                "r", encoding="utf-8-sig"
            ) as arquivo:
                config = json.load(arquivo)
            url_chat = config.get("chat", {}).get("base_url", url_chat)
            caminhos_config = config.get("chrome", {}).get("caminhos", [])
            if caminhos_config:
                caminhos_chrome = caminhos_config
        except Exception:
            pass

        chrome = next(
            (caminho for caminho in caminhos_chrome if Path(caminho).exists()),
            None,
        )

        if not chrome:
            messagebox.showerror(
                "Google Chrome não encontrado",
                "Verifique os caminhos do Google Chrome no config.json."
            )
            return

        try:
            if url_direta:
                subprocess.Popen([chrome, "--new-tab", url_direta])
                self.label_status.config(
                    text=f"Conversa de {nome} aberta no Google Chat."
                )
            else:
                self.copiar_para_area_transferencia(
                    texto_busca,
                    "E-mail para procurar no Chat"
                    if self.email_chat_atual
                    else "Nome para procurar no Chat",
                )
                subprocess.Popen([chrome, "--new-tab", url_chat])
                self.label_status.config(
                    text=(
                        "Google Chat aberto. O e-mail/nome foi copiado; "
                        "cole-o na busca e pressione Enter."
                    )
                )
        except Exception as erro:
            messagebox.showerror("Erro ao abrir Google Chat", str(erro))
    def _definir_texto(self, widget, texto):
        widget.config(
            state="normal"
        )
        widget.delete(
            "1.0",
            "end"
        )
        widget.insert(
            "1.0",
            texto or ""
        )
        widget.config(
            state="disabled"
        )

    def _limpar_atualizacao_jira(self):
        self.var_atualizacao_jira.set("")
        self.texto_atualizacao_jira.delete("1.0", "end")
        self.botao_copiar_atualizacao_jira.config(state="disabled")

    def _atualizacao_jira_alterada(self, event=None):
        texto = gerar_atualizacao_jira(self.var_atualizacao_jira.get())
        self.texto_atualizacao_jira.delete("1.0", "end")
        self.texto_atualizacao_jira.insert("1.0", texto)
        self.botao_copiar_atualizacao_jira.config(
            state="normal" if texto else "disabled"
        )
    def _gerar_mensagem_para_destino(self, chamado, resultado, destino, objetivo):
        """
        Gera a mensagem usando exclusivamente os modelos de templates.py.
        A escolha manual Demandante / Aprovador / Responsável altera apenas
        quem_precisa_agir para a geração da mensagem, sem modificar a análise
        operacional original do chamado.
        """
        from .templates import gerar_mensagem_contato
        analise_mensagem = dict(resultado)
        if destino == "Aprovador":
            analise_mensagem["quem_precisa_agir"] = "Aprovador"
        elif destino == "Demandante":
            analise_mensagem["quem_precisa_agir"] = "Demandante"
        elif destino == "Responsável":
            nome_responsavel = self._nome_por_destino(
                chamado,
                resultado,
                "Responsável"
            )
            analise_mensagem["quem_precisa_agir"] = (
                nome_responsavel
                or "Responsável"
            )
        return gerar_mensagem_contato(
            chamado,
            analise_mensagem,
            objetivo=objetivo or None
        )
    def gerar_mensagens_selecionado(self):
        chamado = getattr(
            self,
            "chamado_selecionado",
            None
        )
        resultado = getattr(
            self,
            "resultado_selecionado",
            None
        )
        if not chamado or not resultado:
            messagebox.showwarning(
                "HelpDeskAgent",
                "Selecione um chamado primeiro."
            )
            return
        objetivo = self.var_objetivo.get().strip()
        try:
            mensagens = gerar_mensagens(
                chamado,
                resultado,
                resultado,
                objetivo=objetivo or None
            )
        except Exception as erro:
            messagebox.showerror(
                "Erro ao gerar mensagens",
                str(erro)
            )
            return
        self.mensagens_geradas = mensagens
        destino = self.var_destino.get() or self._determinar_destino_sugerido(
            chamado, resultado
        )
        mensagem_contato = self._gerar_mensagem_para_destino(
            chamado, resultado, destino, objetivo
        )
        mensagens["mensagem_contato"] = mensagem_contato
        # Mantém a personalização antiga como proteção adicional.
        # Se o template de aprovação ainda vier com saudação genérica,
        # personaliza com o nome estruturado extraído do XML.
        aprovador_nome = (chamado.get("aprovador_nome") or "").strip()
        alvo = str(resultado.get("alvo_contato") or "").strip().lower()
        if (
            mensagem_contato
            and aprovador_nome
            and alvo == "aprovador"
            and mensagem_contato.startswith("Olá. Tudo bem?")
        ):
            mensagem_contato = mensagem_contato.replace(
                "Olá. Tudo bem?",
                f"Olá, {aprovador_nome}. Tudo bem?",
                1
            )
            mensagens["mensagem_contato"] = mensagem_contato
        mensagem_strike = mensagens.get(
            "mensagem_strike"
        )
        self._definir_texto(
            self.texto_mensagem_contato,
            mensagem_contato
        )
        self.botao_copiar_contato.config(
            state=(
                "normal"
                if mensagem_contato
                else "disabled"
            )
        )
        if mensagem_strike:
            self._definir_texto(
                self.texto_mensagem_strike,
                mensagem_strike
            )
            self.botao_copiar_strike.config(
                state="normal"
            )
        else:
            self._definir_texto(
                self.texto_mensagem_strike,
                "Nenhuma mensagem de Strike necessária."
            )
            self.botao_copiar_strike.config(
                state="disabled"
            )
        self.label_status.config(
            text=(
                f"Mensagens de "
                f"{resultado.get('chave', '')} geradas."
            )
        )

    def gerar_strike_manual_selecionado(self):
        chamado = getattr(self, "chamado_selecionado", None)
        resultado = getattr(self, "resultado_selecionado", None)
        if not chamado or not resultado:
            messagebox.showwarning(
                "HelpDeskAgent",
                "Selecione um chamado primeiro.",
            )
            return

        proximo_strike = resultado.get("proximo_strike")
        if proximo_strike not in {1, 2, 3}:
            messagebox.showwarning(
                "Geração manual de Strike",
                "Não existe um próximo Strike disponível para este chamado.",
            )
            return

        chave = resultado.get("chave", "este chamado")
        confirmou = messagebox.askyesno(
            "Confirmar Strike manual",
            (
                f"Gerar a nota do Strike {proximo_strike} para {chave}?\n\n"
                "Use esta opção apenas se você confirmou no Jira uma "
                "nova tentativa sem resposta que ainda não consta no XML. "
                "A ação apenas gera a nota; nada será enviado ao Jira."
            ),
        )
        if not confirmou:
            return

        objetivo = self.var_objetivo.get().strip()
        mensagem_strike = gerar_mensagem_strike_manual(
            chamado,
            resultado,
            proximo_strike,
            objetivo=objetivo or None,
        )
        if not mensagem_strike:
            messagebox.showerror(
                "Geração manual de Strike",
                "Não foi possível gerar a nota de Strike.",
            )
            return

        mensagens = self.mensagens_geradas or {}
        mensagens["mensagem_strike"] = mensagem_strike
        self.mensagens_geradas = mensagens
        self._definir_texto(self.texto_mensagem_strike, mensagem_strike)
        self.botao_copiar_strike.config(state="normal")
        self.label_status.config(
            text=(
                f"Nota manual do Strike {proximo_strike} de "
                f"{chave} gerada."
            )
        )
    def copiar_para_area_transferencia(
        self,
        texto,
        descricao
    ):
        if not texto:
            return
        self.clipboard_clear()
        self.clipboard_append(
            texto
        )
        self.update()
        self.label_status.config(
            text=f"{descricao} copiada."
        )
    def copiar_mensagem_contato(self):
        mensagens = getattr(
            self,
            "mensagens_geradas",
            None
        )
        if not mensagens:
            return
        self.copiar_para_area_transferencia(
            mensagens.get(
                "mensagem_contato",
                ""
            ),
            "Mensagem para contato"
        )
    def copiar_mensagem_strike(self):
        mensagens = getattr(
            self,
            "mensagens_geradas",
            None
        )
        if not mensagens:
            return
        self.copiar_para_area_transferencia(
            mensagens.get(
                "mensagem_strike",
                ""
            ),
            "Nota Jira / Strike"
        )

    def copiar_atualizacao_jira(self):
        texto = self.texto_atualizacao_jira.get("1.0", "end-1c").strip()
        self.copiar_para_area_transferencia(texto, "Atualização para o Jira")
    # ==================================================
    def abrir_jira(self):
        resultado = getattr(
            self,
            "resultado_selecionado",
            None
        )
        if not resultado:
            messagebox.showwarning(
                "HelpDeskAgent",
                "Selecione um chamado primeiro."
            )
            return
        chave = resultado.get("chave")
        if not chave:
            return
        base_url = ""
        caminhos_chrome = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        # Carrega config.json, se disponível.
        try:
            with caminho_app("config.json").open(
                "r",
                encoding="utf-8-sig"
            ) as arquivo:
                config = json.load(arquivo)
            base_url = (
                config
                .get("jira", {})
                .get(
                    "base_url",
                    base_url
                )
            )
            caminhos_config = (
                config
                .get("chrome", {})
                .get(
                    "caminhos",
                    []
                )
            )
            if caminhos_config:
                caminhos_chrome = caminhos_config
        except Exception:
            pass
        base_url = str(base_url or "").strip()
        if not base_url or "example.com" in base_url.casefold():
            messagebox.showerror(
                "URL do Jira não configurada",
                (
                    "Defina jira.base_url no arquivo config.json "
                    "antes de abrir o chamado no Jira."
                ),
            )
            return
        url = f"{base_url}{chave}"
        # Procura especificamente o Google Chrome.
        chrome = None
        for caminho in caminhos_chrome:
            if Path(caminho).exists():
                chrome = caminho
                break
        if not chrome:
            messagebox.showerror(
                "Google Chrome não encontrado",
                (
                    "O HelpDeskAgent não encontrou "
                    "o Google Chrome neste computador.\n\n"
                    "Verifique os caminhos configurados "
                    "no config.json."
                )
            )
            return
        try:
            subprocess.Popen(
                [
                    chrome,
                    "--new-tab",
                    url
                ]
            )
            self.label_status.config(
                text=(
                    f"{chave} aberto no Google Chrome."
                )
            )
        except Exception as erro:
            messagebox.showerror(
                "Erro ao abrir Jira",
                str(erro)
            )
def main():
    app = HelpDeskAgent()
    app.mainloop()


if __name__ == "__main__":
    main()
