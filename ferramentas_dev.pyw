"""Ferramentas Dev — canivete suíço do programador, 100% offline.
Formatadores (JSON/XML/SQL/CSV), testador de regex, diff de textos, conversores e geradores.
"""
import os
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from PyQt6.QtCore import Qt, QTimer  # noqa: E402
from PyQt6.QtGui import (QColor, QFont, QIcon, QPainter, QPixmap, QTextCharFormat,  # noqa: E402
                         QTextCursor)
from PyQt6.QtWidgets import (QApplication, QCheckBox, QColorDialog, QComboBox, QHBoxLayout,  # noqa: E402
                             QLabel, QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit,
                             QPushButton, QSpinBox, QSplitter, QStackedWidget, QTabWidget,
                             QTextEdit, QVBoxLayout, QWidget)

import fd_core as core  # noqa: E402
from fd_core import FdError  # noqa: E402

ACCENT = "#7c5cff"
QSS = """
QWidget { background:#11131a; color:#e7e9f0; font:10pt 'Segoe UI'; }
#title { font:700 18pt 'Segoe UI'; }
#ptitle { font:700 15pt 'Segoe UI'; }
#info { color:#8a93a8; }
#cat { color:#8a93a8; font-weight:600; }
#ok { color:#79e0a8; }
#err { color:#ff7a7a; font-family:'Consolas'; }
QLineEdit, QComboBox, QSpinBox { background:#1b202b; border:1px solid #2d3550;
    border-radius:8px; padding:6px; }
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus { border:1px solid #7c5cff; }
#code { font:10pt 'Consolas'; }
QPlainTextEdit, QTextEdit { background:#0c0e14; border:1px solid #2d3550; border-radius:10px;
    color:#e7e9f0; font:10pt 'Consolas'; selection-background-color:#7c5cff; }
#out { color:#79e0a8; }
QPushButton { background:#222a38; border:0; border-radius:10px; padding:9px 14px; }
QPushButton:hover { background:#2d3550; }
#go { background:#7c5cff; color:#fff; font-weight:600; padding:12px 16px; font-size:12pt; }
#go:hover { background:#8f74ff; }
QListWidget { background:#161a23; border:1px solid #2d3550; border-radius:10px; padding:4px;
    outline:0; }
QListWidget::item { padding:7px 8px; border-radius:7px; }
QListWidget::item:selected { background:#7c5cff; color:#fff; }
QListWidget::item:hover:!selected { background:#222a38; }
QCheckBox { spacing:6px; }
QTabWidget::pane { border:0; }
QTabBar::tab { background:#1b202b; padding:7px 14px; border-radius:8px; margin-right:4px; }
QTabBar::tab:selected { background:#7c5cff; color:#fff; }
QSplitter::handle { background:#11131a; }
"""


def app_icon():
    pm = QPixmap(64, 64)
    pm.fill(QColor("transparent"))
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(ACCENT))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(6, 10, 52, 44, 10, 10)
    p.setPen(QColor("#ffffff"))
    f = QFont("Consolas", 20)
    f.setBold(True)
    p.setFont(f)
    p.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, "</>")
    p.end()
    return QIcon(pm)


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s.lower())
                   if unicodedata.category(c) != "Mn")


# ====================================================================== base
class Page(QWidget):
    NAME = ""
    ICON = ""
    DESC = ""
    KEYWORDS = ""

    def __init__(self):
        super().__init__()
        self.lay = QVBoxLayout(self)
        self.lay.setContentsMargins(4, 0, 0, 0)
        self.lay.setSpacing(8)
        t = QLabel(f"{self.ICON}  {self.NAME}")
        t.setObjectName("ptitle")
        self.lay.addWidget(t)
        d = QLabel(self.DESC)
        d.setObjectName("info")
        d.setWordWrap(True)
        self.lay.addWidget(d)
        self.msg = QLabel("")
        self.msg.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(200)
        self._timer.timeout.connect(self.safe_run)
        self.build()

    # ---- helpers
    def editor(self, placeholder="", readonly=False):
        e = QPlainTextEdit()
        e.setPlaceholderText(placeholder)
        e.setReadOnly(readonly)
        e.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        e.setTabStopDistance(32)
        if readonly:
            e.setObjectName("out")
        return e

    def line(self, placeholder="", text=""):
        e = QLineEdit(text)
        e.setPlaceholderText(placeholder)
        e.setObjectName("code")
        return e

    def combo(self, items):
        c = QComboBox()
        c.addItems(list(items))
        return c

    def button(self, text, slot, primary=False):
        b = QPushButton(text)
        if primary:
            b.setObjectName("go")
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        b.clicked.connect(lambda: self.safe_run(slot))
        return b

    def row(self, *widgets, stretch=True):
        h = QHBoxLayout()
        h.setSpacing(8)
        for w in widgets:
            if isinstance(w, str):
                h.addWidget(QLabel(w))
            else:
                h.addWidget(w)
        if stretch:
            h.addStretch(1)
        return h

    def output(self, label="Resultado", copy_source=None):
        """Cria a caixa de saída + botão Copiar; devolve o QPlainTextEdit."""
        out = self.editor("O resultado aparece aqui…", readonly=True)
        lbl = QLabel(label)
        lbl.setObjectName("cat")
        cp = QPushButton("📋 Copiar")
        cp.setCursor(Qt.CursorShape.PointingHandCursor)
        cp.clicked.connect(lambda: self.copy((copy_source or out.toPlainText)()))
        head = QHBoxLayout()
        head.addWidget(lbl)
        head.addStretch(1)
        head.addWidget(self.msg)
        head.addWidget(cp)
        box = QVBoxLayout()
        box.setSpacing(4)
        box.addLayout(head)
        box.addWidget(out)
        return out, box

    def copy(self, text):
        QApplication.clipboard().setText(text)
        if text:
            self.set_msg("Copiado! ✔")

    def set_msg(self, text, ok=True):
        self.msg.setObjectName("ok" if ok else "err")
        self.msg.setStyleSheet("")
        self.msg.style().unpolish(self.msg)
        self.msg.style().polish(self.msg)
        self.msg.setText(text)

    def live(self, *signals):
        for s in signals:
            s.connect(self._timer.start)

    def safe_run(self, fn=None):
        fn = fn or self.run
        try:
            self.set_msg("")
            fn()
        except FdError as e:
            self.show_error(str(e))
        except Exception as e:  # nunca derrubar a janela
            self.show_error(f"Erro inesperado: {type(e).__name__}: {e}")

    def show_error(self, text):
        if hasattr(self, "out"):
            self.out.setPlainText("⚠ " + text)
        self.set_msg("⚠ Erro", ok=False)

    def build(self):
        raise NotImplementedError

    def run(self):
        raise NotImplementedError


# ====================================================================== formatadores
class JsonPage(Page):
    NAME, ICON, KEYWORDS = "JSON", "🧾", "formatar minificar validar ordenar"
    DESC = "Formate, minifique ou valide JSON. Se tiver erro, mostra a linha e a coluna exatas."

    def build(self):
        self.inp = self.editor('Cole o JSON aqui, ex.: {"nome": "Caio", "tags": [1, 2]}')
        self.indent = self.combo(["2 espaços", "4 espaços", "Tab"])
        self.sort = QCheckBox("Ordenar chaves")
        self.lay.addWidget(self.inp, 1)
        self.lay.addLayout(self.row(
            self.button("✨ Formatar", self.run, True), self.button("Minificar", self.minify),
            self.button("Validar", self.validate), "Recuo:", self.indent, self.sort))
        self.out, box = self.output()
        self.lay.addLayout(box, 1)

    def _indent(self):
        return {0: 2, 1: 4, 2: "\t"}[self.indent.currentIndex()]

    def run(self):
        self.out.setPlainText(core.json_format(self.inp.toPlainText(), self._indent(),
                                               self.sort.isChecked()))
        self.set_msg("✅ JSON válido")

    def minify(self):
        r = core.json_minify(self.inp.toPlainText(), self.sort.isChecked())
        self.out.setPlainText(r)
        self.set_msg(f"✅ {len(r)} caracteres")

    def validate(self):
        self.out.setPlainText(core.json_validate(self.inp.toPlainText()))


class XmlPage(Page):
    NAME, ICON, KEYWORDS = "XML", "📰", "formatar validar minificar html"
    DESC = "Formate (indente), minifique ou valide XML. Erros mostram linha e coluna."

    def build(self):
        self.inp = self.editor("Cole o XML aqui, ex.: <pessoa><nome>Caio</nome></pessoa>")
        self.indent = QSpinBox()
        self.indent.setRange(1, 8)
        self.indent.setValue(2)
        self.lay.addWidget(self.inp, 1)
        self.lay.addLayout(self.row(
            self.button("✨ Formatar", self.run, True), self.button("Minificar", self.minify),
            self.button("Validar", self.validate), "Recuo:", self.indent))
        self.out, box = self.output()
        self.lay.addLayout(box, 1)

    def run(self):
        self.out.setPlainText(core.xml_format(self.inp.toPlainText(), self.indent.value()))
        self.set_msg("✅ XML bem-formado")

    def minify(self):
        self.out.setPlainText(core.xml_minify(self.inp.toPlainText()))

    def validate(self):
        self.out.setPlainText(core.xml_validate(self.inp.toPlainText()))


class SqlPage(Page):
    NAME, ICON, KEYWORDS = "SQL", "🗃️", "formatar query consulta select banco"
    DESC = "Deixa a consulta legível: palavras-chave em MAIÚSCULAS e quebra de linha antes de " \
           "SELECT, FROM, WHERE, JOIN, AND, ORDER BY…"

    def build(self):
        self.inp = self.editor("select id, nome from clientes c join pedidos p on p.cliente_id = c.id "
                               "where c.ativo = 1 and p.total > 100 order by nome")
        self.upper = QCheckBox("Palavras-chave em MAIÚSCULAS")
        self.upper.setChecked(True)
        self.lay.addWidget(self.inp, 1)
        self.lay.addLayout(self.row(self.button("✨ Formatar", self.run, True), self.upper))
        self.out, box = self.output()
        self.lay.addLayout(box, 1)
        self.live(self.inp.textChanged, self.upper.toggled)

    def run(self):
        if not self.inp.toPlainText().strip():
            self.out.clear()
            return
        self.out.setPlainText(core.sql_format(self.inp.toPlainText(), self.upper.isChecked()))


class CsvJsonPage(Page):
    NAME, ICON, KEYWORDS = "CSV → JSON", "📊", "planilha excel tabela converter"
    DESC = "A primeira linha do CSV vira as chaves. O separador pode ser detectado sozinho."

    def build(self):
        self.inp = self.editor("nome;idade;cidade\nCaio;30;São Paulo\nAna;28;Santos")
        self.delim = self.combo(core.DELIMS)
        self.conv = QCheckBox("Converter números e true/false")
        self.conv.setChecked(True)
        self.lay.addWidget(self.inp, 1)
        self.lay.addLayout(self.row(self.button("➡ Converter", self.run, True),
                                    "Separador:", self.delim, self.conv))
        self.out, box = self.output()
        self.lay.addLayout(box, 1)
        self.live(self.inp.textChanged, self.delim.currentIndexChanged, self.conv.toggled)

    def run(self):
        if not self.inp.toPlainText().strip():
            self.out.clear()
            return
        r = core.csv_to_json(self.inp.toPlainText(), core.DELIMS[self.delim.currentText()],
                             self.conv.isChecked())
        self.out.setPlainText(r)


class JsonCsvPage(Page):
    NAME, ICON, KEYWORDS = "JSON → CSV", "📑", "planilha excel tabela converter"
    DESC = "Converte uma lista de objetos JSON em CSV (as colunas são a união de todas as chaves)."

    def build(self):
        self.inp = self.editor('[{"nome": "Caio", "idade": 30}, {"nome": "Ana", "cidade": "Santos"}]')
        names = [k for k in core.DELIMS if core.DELIMS[k]]
        self.delim = self.combo(names)
        self.lay.addWidget(self.inp, 1)
        self.lay.addLayout(self.row(self.button("➡ Converter", self.run, True), "Separador:", self.delim))
        self.out, box = self.output()
        self.lay.addLayout(box, 1)
        self.live(self.inp.textChanged, self.delim.currentIndexChanged)

    def run(self):
        if not self.inp.toPlainText().strip():
            self.out.clear()
            return
        self.out.setPlainText(core.json_to_csv(self.inp.toPlainText(),
                                               core.DELIMS[self.delim.currentText()]))


# ====================================================================== texto
HL_COLORS = ["#5b4bb5", "#2f7d5b", "#8a5a1c", "#7a2f5e"]


class RegexPage(Page):
    NAME, ICON, KEYWORDS = "Testador de Regex", "🔍", "expressao regular regex replace substituir"
    DESC = "Teste ao vivo: as correspondências ficam destacadas no texto. Use \\1 ou \\g<nome> " \
           "na substituição."

    def build(self):
        self.pat = self.line(r"Padrão, ex.: (\d{2})/(\d{2})/(\d{4})")
        self.ic = QCheckBox("IGNORECASE (i)")
        self.ml = QCheckBox("MULTILINE (m)")
        self.da = QCheckBox("DOTALL (s)")
        self.lay.addWidget(self.pat)
        self.lay.addLayout(self.row(self.ic, self.ml, self.da, self.button("🔍 Testar", self.run, True)))
        self.text = QTextEdit()
        self.text.setAcceptRichText(False)
        self.text.setPlaceholderText("Texto de teste, ex.: Hoje é 05/11/2026 e amanhã 06/11/2026.")
        self.lay.addWidget(self.text, 1)
        self.repl = self.line(r"Substituir por (opcional), ex.: \3-\2-\1")
        self.lay.addWidget(self.repl)
        tabs = QTabWidget()
        self.out = self.editor(readonly=True)
        self.sub_out = self.editor(readonly=True)
        tabs.addTab(self.out, "Correspondências")
        tabs.addTab(self.sub_out, "Prévia da substituição")
        self.tabs = tabs
        out_lbl = QLabel("Resultado")
        out_lbl.setObjectName("cat")
        cp = QPushButton("📋 Copiar")
        cp.clicked.connect(lambda: self.copy(tabs.currentWidget().toPlainText()))
        head = QHBoxLayout()
        head.addWidget(out_lbl)
        head.addStretch(1)
        head.addWidget(self.msg)
        head.addWidget(cp)
        self.lay.addLayout(head)
        self.lay.addWidget(tabs, 1)
        self.live(self.pat.textChanged, self.text.textChanged, self.repl.textChanged,
                  self.ic.toggled, self.ml.toggled, self.da.toggled)

    def show_error(self, text):
        self.out.setPlainText("⚠ " + text)
        self.sub_out.clear()
        self.text.setExtraSelections([])
        self.set_msg("⚠ Regex inválida", ok=False)

    def run(self):
        pattern = self.pat.text()
        text = self.text.toPlainText()
        if not pattern:
            self.text.setExtraSelections([])
            self.out.setPlainText("Digite um padrão.")
            self.sub_out.clear()
            return
        rx = core.regex_compile(pattern, self.ic.isChecked(), self.ml.isChecked(), self.da.isChecked())
        matches = core.regex_matches(rx, text)
        sels = []
        for i, m in enumerate(matches):
            if m["start"] == m["end"]:
                continue
            sel = QTextEdit.ExtraSelection()
            fmt = QTextCharFormat()
            fmt.setBackground(QColor(HL_COLORS[i % len(HL_COLORS)]))
            fmt.setForeground(QColor("#ffffff"))
            sel.format = fmt
            cur = QTextCursor(self.text.document())
            cur.setPosition(m["start"])
            cur.setPosition(m["end"], QTextCursor.MoveMode.KeepAnchor)
            sel.cursor = cur
            sels.append(sel)
        self.text.setExtraSelections(sels)
        self.out.setPlainText(core.regex_report(matches))
        self.set_msg(f"{len(matches)} correspondência(s)" if matches else "nenhuma correspondência",
                     ok=bool(matches))
        if self.repl.text():
            new, n = core.regex_replace(rx, self.repl.text(), text)
            self.sub_out.setPlainText(new)
        else:
            self.sub_out.setPlainText("(digite algo em “Substituir por” pra ver a prévia)")


class DiffPage(Page):
    NAME, ICON, KEYWORDS = "Comparar textos (diff)", "🆚", "diff diferenca comparar"
    DESC = "Cole as duas versões. Linhas removidas em vermelho, adicionadas em verde. " \
           "O botão Copiar copia o diff unificado."

    def build(self):
        self.a = self.editor("Texto original")
        self.b = self.editor("Texto modificado")
        sp = QSplitter(Qt.Orientation.Horizontal)
        for title, ed in (("Original", self.a), ("Modificado", self.b)):
            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            lb = QLabel(title)
            lb.setObjectName("cat")
            v.addWidget(lb)
            v.addWidget(ed)
            sp.addWidget(w)
        self.lay.addWidget(sp, 1)
        self.ws = QCheckBox("Ignorar espaços")
        self.case = QCheckBox("Ignorar maiúsculas/minúsculas")
        self.lay.addLayout(self.row(self.button("🆚 Comparar", self.run, True), self.ws, self.case))
        self.visual = QTextEdit()
        self.visual.setReadOnly(True)
        self.uni = self.editor(readonly=True)
        tabs = QTabWidget()
        tabs.addTab(self.visual, "Visual")
        tabs.addTab(self.uni, "Unificado")
        self.out = self.uni
        lbl = QLabel("Resultado")
        lbl.setObjectName("cat")
        cp = QPushButton("📋 Copiar")
        cp.clicked.connect(lambda: self.copy(self.uni.toPlainText()))
        head = QHBoxLayout()
        head.addWidget(lbl)
        head.addStretch(1)
        head.addWidget(self.msg)
        head.addWidget(cp)
        self.lay.addLayout(head)
        self.lay.addWidget(tabs, 1)
        self.live(self.ws.toggled, self.case.toggled)

    def run(self):
        import html as _html
        rows, uni, add, rem = core.diff_texts(self.a.toPlainText(), self.b.toPlainText(),
                                              self.ws.isChecked(), self.case.isChecked())
        colors = {"+": ("#123d26", "#79e0a8"), "-": ("#4a1a1f", "#ff8f8f"), " ": ("transparent", "#c9cede")}
        parts = []
        for tag, text in rows:
            bg, fg = colors[tag]
            parts.append(f'<div style="background:{bg};color:{fg};white-space:pre">'
                         f'{tag} {_html.escape(text) or "&nbsp;"}</div>')
        self.visual.setHtml('<div style="font-family:Consolas;font-size:10pt">' + "".join(parts) + "</div>")
        self.uni.setPlainText(uni or "(os textos são iguais)")
        if add or rem:
            self.set_msg(f"+{add} adicionada(s)  −{rem} removida(s)")
        else:
            self.set_msg("✅ Textos iguais")


class EscapePage(Page):
    NAME, ICON, KEYWORDS = "Escape de string", "🧷", "escape unescape aspas barra json python c html"
    DESC = "Escapa (ou desfaz) aspas, barras, quebras de linha etc. para colar dentro de código."

    def build(self):
        self.inp = self.editor('Texto, ex.: Ele disse "oi"\ne foi embora\\')
        self.lang = self.combo(core.ESCAPE_LANGS)
        self.lay.addWidget(self.inp, 1)
        self.lay.addLayout(self.row(self.button("🧷 Escapar", self.run, True),
                                    self.button("Desescapar", self.unescape), "Linguagem:", self.lang))
        self.out, box = self.output()
        self.lay.addLayout(box, 1)

    def run(self):
        self.out.setPlainText(core.escape_text(self.inp.toPlainText(), self.lang.currentText()))

    def unescape(self):
        self.out.setPlainText(core.unescape_text(self.inp.toPlainText(), self.lang.currentText()))


class Base64Page(Page):
    NAME, ICON, KEYWORDS = "Base64 / URL", "🔣", "base64 url encode decode codificar percent"
    DESC = "Codifica e decodifica Base64 (normal ou URL-safe) e URL (percent-encoding). Usa UTF-8."

    def build(self):
        self.inp = self.editor("Texto ou código para converter")
        self.kind = self.combo(core.ENCODINGS)
        self.lay.addWidget(self.inp, 1)
        self.lay.addLayout(self.row(self.button("🔒 Codificar", self.run, True),
                                    self.button("🔓 Decodificar", self.decode), "Tipo:", self.kind))
        self.out, box = self.output()
        self.lay.addLayout(box, 1)

    def run(self):
        self.out.setPlainText(core.encode_text(self.inp.toPlainText(), self.kind.currentText()))

    def decode(self):
        self.out.setPlainText(core.decode_text(self.inp.toPlainText(), self.kind.currentText()))


class HashPage(Page):
    NAME, ICON, KEYWORDS = "Hash (MD5/SHA)", "#️⃣", "hash md5 sha1 sha256 checksum crc"
    DESC = "Calcula MD5, SHA-1, SHA-256, SHA-512, SHA3, BLAKE2 e CRC32 do texto (UTF-8), ao vivo."

    def build(self):
        self.inp = self.editor("Texto para calcular o hash")
        self.upper = QCheckBox("Maiúsculas")
        self.lay.addWidget(self.inp, 1)
        self.lay.addLayout(self.row(self.button("#️⃣ Calcular", self.run, True), self.upper))
        self.out, box = self.output()
        self.lay.addLayout(box, 1)
        self.live(self.inp.textChanged, self.upper.toggled)

    def run(self):
        self.out.setPlainText(core.hash_report(self.inp.toPlainText(), self.upper.isChecked()))


# ====================================================================== conversores
class BasesPage(Page):
    NAME, ICON, KEYWORDS = "Bases numéricas", "🔢", "binario hexadecimal octal decimal hex bin"
    DESC = "Converte entre binário, octal, decimal e hexadecimal. Aceita prefixos 0x, 0b, 0o e _."

    def build(self):
        self.inp = self.line("Número, ex.: 255, 0xFF, 0b1010")
        self.base = self.combo(core.BASES)
        self.lay.addLayout(self.row(self.inp, "Base de entrada:", self.base, stretch=False))
        self.lay.addLayout(self.row(self.button("🔢 Converter", self.run, True)))
        self.out, box = self.output()
        self.lay.addLayout(box, 1)
        self.live(self.inp.textChanged, self.base.currentIndexChanged)

    def run(self):
        if not self.inp.text().strip():
            self.out.clear()
            return
        self.out.setPlainText(core.convert_base_report(self.inp.text(), core.BASES[self.base.currentText()]))


class ColorPage(Page):
    NAME, ICON, KEYWORDS = "Cores HEX ↔ RGB ↔ HSL", "🎨", "cor color hex rgb hsl"
    DESC = "Digite uma cor em qualquer formato (#7c5cff, rgb(124, 92, 255), hsl(252, 100%, 68%)) " \
           "ou escolha na paleta."

    def build(self):
        self.inp = self.line("#7c5cff", "#7c5cff")
        pick = QPushButton("🎨 Escolher…")
        pick.clicked.connect(self.pick)
        self.lay.addLayout(self.row(self.inp, pick, self.button("Converter", self.run, True), stretch=False))
        self.swatch = QLabel("Aa  Amostra")
        self.swatch.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.swatch.setMinimumHeight(90)
        self.lay.addWidget(self.swatch)
        self.out, box = self.output()
        self.lay.addLayout(box, 1)
        self.live(self.inp.textChanged)
        self.safe_run()

    def pick(self):
        try:
            start = QColor(core.color_info(self.inp.text())["hex"])
        except FdError:
            start = QColor(ACCENT)
        c = QColorDialog.getColor(start, self, "Escolher cor")
        if c.isValid():
            self.inp.setText(c.name())

    def run(self):
        info = core.color_info(self.inp.text())
        self.swatch.setStyleSheet(f"background:{info['hex']}; color:{info['text_color']};"
                                  "border-radius:12px; font:700 16pt 'Segoe UI';")
        self.out.setPlainText(core.color_report(self.inp.text()))


class TimestampPage(Page):
    NAME, ICON, KEYWORDS = "Timestamp ↔ data", "🕒", "unix epoch timestamp data hora"
    DESC = "Converte timestamp Unix (segundos ou milissegundos) em data, ou data em timestamp. " \
           "Aceita 05/11/2026 14:30 e 2026-11-05T14:30:00Z."

    def build(self):
        self.inp = self.line("1730000000  ou  05/11/2026 14:30")
        now = QPushButton("⏱ Agora")
        now.clicked.connect(lambda: self.inp.setText(str(int(__import__("time").time()))))
        self.lay.addLayout(self.row(self.inp, now, self.button("Converter", self.run, True), stretch=False))
        self.out, box = self.output()
        self.lay.addLayout(box, 1)
        self.live(self.inp.textChanged)
        self.safe_run()

    def run(self):
        self.out.setPlainText(core.timestamp_report(self.inp.text()))


# ====================================================================== geradores/outros
class UuidPage(Page):
    NAME, ICON, KEYWORDS = "Gerador de UUID", "🆔", "uuid guid gerar id"
    DESC = "Gera UUIDs v4 (aleatórios) ou v1 (baseados no tempo), um por linha."

    def build(self):
        self.n = QSpinBox()
        self.n.setRange(1, 10000)
        self.n.setValue(5)
        self.ver = self.combo(["v4 (aleatório)", "v1 (tempo)"])
        self.upper = QCheckBox("Maiúsculas")
        self.hyph = QCheckBox("Com hífens")
        self.hyph.setChecked(True)
        self.lay.addLayout(self.row("Quantidade:", self.n, "Versão:", self.ver, self.upper, self.hyph))
        self.lay.addLayout(self.row(self.button("🆔 Gerar", self.run, True)))
        self.out, box = self.output()
        self.lay.addLayout(box, 1)
        self.safe_run()

    def run(self):
        ids = core.make_uuids(self.n.value(), 4 if self.ver.currentIndex() == 0 else 1,
                              self.upper.isChecked(), self.hyph.isChecked())
        self.out.setPlainText("\n".join(ids))


class CronPage(Page):
    NAME, ICON, KEYWORDS = "Cron explicado", "⏰", "cron crontab agendamento agendar"
    DESC = "Digite uma expressão cron de 5 campos (minuto hora dia mês dia-da-semana) e veja em " \
           "português, com as próximas execuções."
    EXAMPLES = ["*/5 * * * *", "0 9 * * 1-5", "30 2 1 * *", "0 0 * * 0", "*/15 9-17 * * mon-fri",
                "0 8,12,18 * * *", "0 0 1 1 *", "@hourly", "@daily"]

    def build(self):
        self.inp = self.line("*/5 * * * *", "*/5 * * * *")
        self.ex = self.combo(["Exemplos…"] + self.EXAMPLES)
        self.ex.activated.connect(lambda i: i and self.inp.setText(self.EXAMPLES[i - 1]))
        self.lay.addLayout(self.row(self.inp, self.ex, self.button("⏰ Explicar", self.run, True), stretch=False))
        hint = QLabel("┌ minuto (0–59)  ┌ hora (0–23)  ┌ dia (1–31)  ┌ mês (1–12)  ┌ dia da semana (0–6, dom=0)\n"
                      "Use * (todos), */n (a cada n), a-b (intervalo), a,b (lista).")
        hint.setObjectName("info")
        self.lay.addWidget(hint)
        self.out, box = self.output()
        self.lay.addLayout(box, 1)
        self.live(self.inp.textChanged)
        self.safe_run()

    def run(self):
        self.out.setPlainText(core.cron_report(self.inp.text()))


class CounterPage(Page):
    NAME, ICON, KEYWORDS = "Contador de linhas", "📏", "contar linhas palavras caracteres codigo loc"
    DESC = "Conta linhas (código, comentário, em branco), palavras e caracteres, ao vivo."

    def build(self):
        self.inp = self.editor("Cole o código ou texto aqui")
        self.lay.addWidget(self.inp, 2)
        self.lay.addLayout(self.row(self.button("📏 Contar", self.run, True)))
        self.out, box = self.output()
        self.lay.addLayout(box, 1)
        self.live(self.inp.textChanged)
        self.safe_run()

    def run(self):
        self.out.setPlainText(core.code_stats_report(self.inp.toPlainText()))


CATEGORIES = [
    ("Formatadores", [JsonPage, XmlPage, SqlPage, CsvJsonPage, JsonCsvPage]),
    ("Texto e Regex", [RegexPage, DiffPage, EscapePage, Base64Page, HashPage]),
    ("Conversores", [BasesPage, ColorPage, TimestampPage]),
    ("Geradores e outros", [UuidPage, CronPage, CounterPage]),
]


# ====================================================================== janela
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("💻 Ferramentas Dev")
        self.setWindowIcon(app_icon())
        self.resize(1100, 750)
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(14)

        side = QWidget()
        side.setFixedWidth(270)
        left = QVBoxLayout(side)
        left.setContentsMargins(0, 0, 0, 0)
        title = QLabel("💻 Ferramentas Dev")
        title.setObjectName("title")
        left.addWidget(title)
        sub = QLabel("Tudo offline, nada sai do PC.")
        sub.setObjectName("info")
        left.addWidget(sub)
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔎 Buscar função…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter)
        left.addWidget(self.search)
        self.list = QListWidget()
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setTextElideMode(Qt.TextElideMode.ElideRight)
        left.addWidget(self.list, 1)
        root.addWidget(side)

        self.stack = QStackedWidget()
        root.addWidget(self.stack, 1)

        self.pages = []
        for cat, classes in CATEGORIES:
            head = QListWidgetItem(cat.upper())
            head.setFlags(Qt.ItemFlag.NoItemFlags)
            f = QFont("Segoe UI", 8)
            f.setBold(True)
            head.setFont(f)
            head.setForeground(QColor("#8a93a8"))
            self.list.addItem(head)
            for cls in classes:
                page = cls()
                idx = self.stack.addWidget(page)
                self.pages.append(page)
                it = QListWidgetItem(f"{cls.ICON}  {cls.NAME}")
                it.setData(Qt.ItemDataRole.UserRole, idx)
                it.setData(Qt.ItemDataRole.UserRole + 1,
                           strip_accents(f"{cat} {cls.NAME} {cls.KEYWORDS}"))
                self.list.addItem(it)
        self.list.currentItemChanged.connect(self.on_select)
        self.list.setCurrentRow(1)

    def on_select(self, item, _prev=None):
        if item is not None and item.data(Qt.ItemDataRole.UserRole) is not None:
            self.stack.setCurrentIndex(item.data(Qt.ItemDataRole.UserRole))

    def filter(self, text):
        q = strip_accents(text.strip())
        head = None
        head_visible = False
        first = None
        for i in range(self.list.count()):
            it = self.list.item(i)
            if it.data(Qt.ItemDataRole.UserRole) is None:
                if head is not None:
                    head.setHidden(not head_visible)
                head, head_visible = it, False
                continue
            show = all(w in it.data(Qt.ItemDataRole.UserRole + 1) for w in q.split())
            it.setHidden(not show)
            if show:
                head_visible = True
                first = first or it
        if head is not None:
            head.setHidden(not head_visible)
        cur = self.list.currentItem()
        if first is not None and (cur is None or cur.isHidden()):
            self.list.setCurrentItem(first)


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(QSS)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
