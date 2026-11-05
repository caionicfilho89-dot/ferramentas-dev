"""Lógica das Ferramentas Dev (sem interface). Só biblioteca padrão."""
import base64
import colorsys
import csv
import datetime as dt
import difflib
import hashlib
import html
import io
import json
import re
import urllib.parse
import uuid
from xml.dom import minidom
from xml.parsers.expat import ExpatError


class FdError(Exception):
    """Erro com mensagem amigável pro usuário."""


def _caret(text, lineno, colno):
    lines = text.splitlines() or [""]
    if 1 <= lineno <= len(lines):
        line = lines[lineno - 1].replace("\t", " ")
        if len(line) > 120:
            start = max(0, colno - 60)
            line = line[start:start + 120]
            colno -= start
        return f"\n\n{line}\n{' ' * max(0, colno - 1)}^"
    return ""


# ---------------------------------------------------------------- JSON
_JSON_MSGS = [
    ("Expecting property name enclosed in double quotes", "esperava o nome de uma chave entre aspas duplas"),
    ("Expecting value", "esperava um valor"),
    ("Expecting ',' delimiter", "esperava uma vírgula ','"),
    ("Expecting ':' delimiter", "esperava dois-pontos ':'"),
    ("Extra data", "tem dados sobrando depois do fim do JSON"),
    ("Unterminated string starting at", "texto (string) sem aspas de fechamento"),
    ("Invalid control character at", "caractere de controle inválido dentro do texto"),
    ("Invalid \\escape", "sequência de escape inválida"),
    ("Illegal trailing comma before end of object", "vírgula sobrando antes de '}'"),
    ("Illegal trailing comma before end of array", "vírgula sobrando antes de ']'"),
]


def json_load(text):
    if not text.strip():
        raise FdError("Cole um JSON na caixa de entrada.")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        msg = e.msg
        for en, pt in _JSON_MSGS:
            if msg.startswith(en):
                msg = pt
                break
        raise FdError(f"JSON inválido — linha {e.lineno}, coluna {e.colno}: {msg}"
                      + _caret(text, e.lineno, e.colno)) from None


def json_format(text, indent=2, sort_keys=False):
    data = json_load(text)
    return json.dumps(data, indent=indent, sort_keys=sort_keys, ensure_ascii=False)


def json_minify(text, sort_keys=False):
    data = json_load(text)
    return json.dumps(data, separators=(",", ":"), sort_keys=sort_keys, ensure_ascii=False)


def json_validate(text):
    data = json_load(text)
    tipo = {dict: "objeto", list: "lista", str: "texto", bool: "booleano",
            type(None): "null"}.get(type(data), "número")
    extra = ""
    if isinstance(data, dict):
        extra = f" com {len(data)} chave(s)"
    elif isinstance(data, list):
        extra = f" com {len(data)} item(ns)"
    return f"✅ JSON válido: {tipo}{extra}."


# ---------------------------------------------------------------- XML
_XML_MSGS = {
    "mismatched tag": "a tag de fechamento não confere com a de abertura",
    "not well-formed (invalid token)": "caractere ou token inválido",
    "unclosed token": "token não fechado",
    "no element found": "nenhum elemento encontrado (XML vazio ou incompleto)",
    "junk after document element": "tem conteúdo depois do elemento raiz",
    "unbound prefix": "prefixo de namespace não declarado",
    "duplicate attribute": "atributo repetido",
    "syntax error": "erro de sintaxe",
    "undefined entity": "entidade não definida (ex.: use &amp; em vez de &)",
}


def _xml_parse(text):
    if not text.strip():
        raise FdError("Cole um XML na caixa de entrada.")
    try:
        return minidom.parseString(text.strip().encode("utf-8"))
    except ExpatError as e:
        msg = str(e).split(":")[0]
        msg = _XML_MSGS.get(msg, msg)
        raise FdError(f"XML inválido — linha {e.lineno}, coluna {e.offset + 1}: {msg}"
                      + _caret(text.strip(), e.lineno, e.offset + 1)) from None


def _strip_ws_nodes(node):
    for child in list(node.childNodes):
        if child.nodeType == child.TEXT_NODE and not child.data.strip():
            node.removeChild(child)
        elif child.hasChildNodes():
            _strip_ws_nodes(child)


def xml_format(text, indent=2):
    doc = _xml_parse(text)
    _strip_ws_nodes(doc)
    out = doc.toprettyxml(indent=" " * indent)
    return "\n".join(line for line in out.splitlines() if line.strip())


def xml_minify(text):
    doc = _xml_parse(text)
    _strip_ws_nodes(doc)
    return doc.toxml()


def xml_validate(text):
    doc = _xml_parse(text)
    root = doc.documentElement
    count = len(root.getElementsByTagName("*")) + 1
    return f"✅ XML bem-formado. Raiz: <{root.tagName}>, {count} elemento(s)."


# ---------------------------------------------------------------- SQL
_SQL_TOKEN = re.compile(r"""
 (?P<ws>\s+)
|(?P<lcomment>--[^\n]*)
|(?P<bcomment>/\*.*?(?:\*/|$))
|(?P<str>'(?:[^']|'')*'?)
|(?P<qid>"(?:[^"]|"")*"?|`[^`]*`?)
|(?P<num>\d+(?:\.\d+)?)
|(?P<word>[A-Za-z_@#$][\w$#@]*)
|(?P<op><>|<=|>=|!=|\|\||::|.)
""", re.S | re.X)

SQL_KEYWORDS = set("""
SELECT FROM WHERE AND OR NOT IN IS NULL LIKE ILIKE BETWEEN EXISTS AS ON JOIN LEFT RIGHT INNER OUTER
FULL CROSS NATURAL USING GROUP BY ORDER HAVING LIMIT OFFSET UNION ALL DISTINCT INSERT INTO VALUES
UPDATE SET DELETE CREATE TABLE VIEW INDEX DROP ALTER ADD COLUMN PRIMARY KEY FOREIGN REFERENCES
UNIQUE DEFAULT CHECK CONSTRAINT CASE WHEN THEN ELSE END ASC DESC WITH RETURNING EXCEPT INTERSECT
COUNT SUM AVG MIN MAX COALESCE CAST TRUE FALSE IF REPLACE TOP FETCH NEXT ROWS ONLY OVER PARTITION
INTEGER INT VARCHAR TEXT DATE TIMESTAMP BOOLEAN DECIMAL NUMERIC SERIAL BIGINT CHAR FLOAT
TRUNCATE BEGIN COMMIT ROLLBACK TRANSACTION GRANT REVOKE ANY SOME RECURSIVE LATERAL WINDOW
""".split())
_SQL_CLAUSES = {"SELECT", "FROM", "WHERE", "GROUP", "ORDER", "HAVING", "LIMIT", "OFFSET", "UNION",
                "EXCEPT", "INTERSECT", "INSERT", "VALUES", "UPDATE", "SET", "DELETE", "WITH",
                "RETURNING", "JOIN"}
_SQL_FUNCS = {"COUNT", "SUM", "AVG", "MIN", "MAX", "COALESCE", "CAST", "REPLACE", "IF"}
_SQL_JOIN_PREFIX = {"LEFT", "RIGHT", "INNER", "FULL", "CROSS", "NATURAL"}


def sql_format(text, upper=True):
    if not text.strip():
        raise FdError("Cole uma consulta SQL na caixa de entrada.")
    toks = [(m.lastgroup, m.group()) for m in _SQL_TOKEN.finditer(text) if m.lastgroup != "ws"]
    out = []
    stack = []          # parênteses abertos: True = subconsulta
    clause = ["" ]      # cláusula atual por nível de subconsulta
    between = False
    prev_word = ""

    def level():
        return sum(1 for s in stack if s)

    def newline(extra=0):
        while out and out[-1] == " ":
            out.pop()
        if out:
            out.append("\n" + "    " * (level() + extra))

    def emit(tok):
        if out and not out[-1].startswith("\n") and out[-1] not in ("(", ".", "::") \
                and tok not in (",", ")", ";", ".", "::"):
            out.append(" ")
        out.append(tok)

    for i, (kind, tok) in enumerate(toks):
        nxt = next((t for k, t in toks[i + 1:] if k not in ("lcomment", "bcomment")), "")
        if kind == "word":
            up = tok.upper()
            if up in SQL_KEYWORDS:
                tok = up if upper else tok.lower()
            sub_ctx = not stack or stack[-1]
            if up in _SQL_CLAUSES and sub_ctx:
                is_join_cont = up == "JOIN" and prev_word in _SQL_JOIN_PREFIX | {"OUTER"}
                if not is_join_cont and not (up == "SET" and clause[-1] not in ("UPDATE", "")):
                    newline()
                if up != "JOIN":
                    clause[-1] = up
            elif up in _SQL_JOIN_PREFIX and sub_ctx and nxt.upper() in ("JOIN", "OUTER"):
                newline()
            elif up in ("AND", "OR") and sub_ctx:
                if between and up == "AND":
                    between = False
                else:
                    newline(1)
            if up == "BETWEEN":
                between = True
            emit(tok)
            prev_word = up
            continue
        if tok == "(":
            is_sub = nxt.upper() in ("SELECT", "WITH")
            pk, pt = toks[i - 1] if i else ("", "")
            is_func = pt.upper() not in SQL_KEYWORDS or pt.upper() in _SQL_FUNCS
            if pk in ("word", "qid") and is_func and out and not out[-1].startswith("\n"):
                out.append(tok)
            else:
                emit(tok)
            stack.append(is_sub)
            if is_sub:
                clause.append("")
            continue
        if tok == ")":
            if stack:
                was_sub = stack.pop()
                if was_sub:
                    clause.pop()
                    newline()
            emit(tok)
            continue
        if tok == ",":
            emit(tok)
            if (not stack or stack[-1]) and clause[-1] == "SELECT":
                newline(1)
            continue
        if tok == ";":
            emit(tok)
            out.append("\n")
            stack.clear()
            clause[:] = [""]
            continue
        if kind == "lcomment":
            emit(tok)
            out.append("\n" + "    " * level())
            continue
        emit(tok)
    result = "".join(out)
    return "\n".join(line.rstrip() for line in result.strip().splitlines())


# ---------------------------------------------------------------- CSV <-> JSON
DELIMS = {"Automático": None, "Vírgula (,)": ",", "Ponto e vírgula (;)": ";",
          "Tab": "\t", "Barra (|)": "|"}


def _num(v):
    s = v.strip()
    if re.fullmatch(r"-?\d+", s) and not (len(s) > 1 and s.lstrip("-").startswith("0")):
        return int(s)
    if re.fullmatch(r"-?\d+\.\d+", s):
        return float(s)
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    if low == "null" or s == "":
        return None if s else ""
    return v


def csv_to_json(text, delimiter=None, convert=True, indent=2):
    if not text.strip():
        raise FdError("Cole o CSV (com cabeçalho na 1ª linha).")
    if delimiter is None:
        try:
            delimiter = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|").delimiter
        except csv.Error:
            delimiter = ","
    rows = list(csv.reader(io.StringIO(text.strip()), delimiter=delimiter))
    if not rows:
        raise FdError("CSV vazio.")
    header = [h.strip() for h in rows[0]]
    data = []
    for row in rows[1:]:
        if not any(c.strip() for c in row):
            continue
        row = row + [""] * (len(header) - len(row))
        obj = {}
        for j, h in enumerate(header):
            obj[h or f"coluna{j + 1}"] = _num(row[j]) if convert else row[j]
        for j in range(len(header), len(row)):
            obj[f"coluna{j + 1}"] = _num(row[j]) if convert else row[j]
        data.append(obj)
    return json.dumps(data, indent=indent, ensure_ascii=False)


def json_to_csv(text, delimiter=","):
    data = json_load(text)
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
        raise FdError("O JSON precisa ser uma lista de objetos, ex.: [{\"a\": 1}, {\"a\": 2}]")
    cols = []
    for obj in data:
        for k in obj:
            if k not in cols:
                cols.append(k)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delimiter or ",", lineterminator="\n")
    w.writerow(cols)
    for obj in data:
        row = []
        for c in cols:
            v = obj.get(c, "")
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)
            elif v is None:
                v = ""
            elif isinstance(v, bool):
                v = "true" if v else "false"
            row.append(v)
        w.writerow(row)
    return buf.getvalue().rstrip("\n")


# ---------------------------------------------------------------- Regex
def regex_compile(pattern, ignorecase=False, multiline=False, dotall=False):
    flags = (re.I if ignorecase else 0) | (re.M if multiline else 0) | (re.S if dotall else 0)
    try:
        return re.compile(pattern, flags)
    except re.error as e:
        pos = e.pos if e.pos is not None else 0
        raise FdError(f"Regex inválida (posição {pos + 1}): {e.msg}\n{pattern}\n{' ' * pos}^") from None


def regex_matches(rx, text, limit=5000):
    res = []
    for m in rx.finditer(text):
        res.append({"start": m.start(), "end": m.end(), "text": m.group(0),
                    "groups": m.groups(), "named": m.groupdict()})
        if len(res) >= limit:
            break
    return res


def regex_report(matches):
    if not matches:
        return "Nenhuma correspondência."
    lines = [f"{len(matches)} correspondência(s):", ""]
    for i, m in enumerate(matches, 1):
        lines.append(f"#{i}  [{m['start']}–{m['end']}]  {m['text']!r}")
        for gi, g in enumerate(m["groups"], 1):
            lines.append(f"      grupo {gi}: {g!r}")
        for k, v in m["named"].items():
            lines.append(f"      <{k}>: {v!r}")
    return "\n".join(lines)


def regex_replace(rx, repl, text):
    try:
        return rx.subn(repl, text)
    except (re.error, IndexError) as e:
        raise FdError(f"Erro na substituição: {e}") from None


# ---------------------------------------------------------------- Diff
def _norm(line, ignore_ws, ignore_case):
    if ignore_ws:
        line = " ".join(line.split())
    if ignore_case:
        line = line.casefold()
    return line


def diff_texts(a, b, ignore_ws=False, ignore_case=False, context=3):
    """Retorna (linhas, unificado, adicionadas, removidas).
    linhas = lista de (tag, texto) com tag em ' ', '+', '-'."""
    al, bl = a.splitlines(), b.splitlines()
    ak = [_norm(x, ignore_ws, ignore_case) for x in al]
    bk = [_norm(x, ignore_ws, ignore_case) for x in bl]
    sm = difflib.SequenceMatcher(None, ak, bk, autojunk=False)
    rows, add, rem = [], 0, 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            rows += [(" ", x) for x in bl[j1:j2]]
        else:
            rows += [("-", x) for x in al[i1:i2]]
            rows += [("+", x) for x in bl[j1:j2]]
            rem += i2 - i1
            add += j2 - j1
    uni = []
    for group in sm.get_grouped_opcodes(context):
        if not uni:
            uni += ["--- original", "+++ modificado"]
        f, l = group[0], group[-1]
        uni.append(f"@@ -{f[1] + 1},{l[2] - f[1]} +{f[3] + 1},{l[4] - f[3]} @@")
        for tag, i1, i2, j1, j2 in group:
            if tag == "equal":
                uni += [" " + x for x in al[i1:i2]]
            else:
                uni += ["-" + x for x in al[i1:i2]]
                uni += ["+" + x for x in bl[j1:j2]]
    return rows, "\n".join(uni), add, rem


# ---------------------------------------------------------------- Contador
_COMMENT_PREFIXES = ("#", "//", "--", "/*", "*", "*/", ";", "<!--", "'", "rem ", "REM ")


def code_stats(text):
    lines = text.splitlines()
    blank = sum(1 for x in lines if not x.strip())
    comment = sum(1 for x in lines if x.strip() and x.strip().startswith(_COMMENT_PREFIXES))
    return {
        "linhas": len(lines),
        "codigo": len(lines) - blank - comment,
        "comentario": comment,
        "vazias": blank,
        "palavras": len(text.split()),
        "caracteres": len(text),
        "sem_espacos": len("".join(text.split())),
        "maior_linha": max((len(x) for x in lines), default=0),
    }


def code_stats_report(text):
    s = code_stats(text)
    return "\n".join([
        f"Linhas totais ........ {s['linhas']}",
        f"  de código .......... {s['codigo']}",
        f"  de comentário ...... {s['comentario']}",
        f"  em branco .......... {s['vazias']}",
        f"Palavras ............. {s['palavras']}",
        f"Caracteres ........... {s['caracteres']}",
        f"  sem espaços ........ {s['sem_espacos']}",
        f"Maior linha .......... {s['maior_linha']} caracteres",
    ])


# ---------------------------------------------------------------- Bases
BASES = {"Automático (0x / 0b / 0o)": 0, "Decimal": 10, "Hexadecimal": 16,
         "Binário": 2, "Octal": 8}


def convert_base(value, base=0):
    s = value.strip().replace("_", "").replace(" ", "")
    if not s:
        raise FdError("Digite um número.")
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    if base == 0 and not re.match(r"0[xXbBoO]", s):
        base = 10
    try:
        n = int(s, base)
    except ValueError:
        nomes = {2: "binário", 8: "octal", 10: "decimal", 16: "hexadecimal"}
        raise FdError(f"'{value.strip()}' não é um número {nomes.get(base, '')} válido.") from None
    if neg:
        n = -n
    sign = "-" if n < 0 else ""
    a = abs(n)
    b = bin(a)[2:]
    grouped = " ".join(b[max(0, i - 4):i] for i in range(len(b), 0, -4)[::-1])
    return {
        "dec": str(n),
        "hex": sign + "0x" + format(a, "X"),
        "bin": sign + "0b" + b,
        "bin_grupos": sign + grouped,
        "oct": sign + "0o" + format(a, "o"),
        "bits": a.bit_length(),
    }


def convert_base_report(value, base=0):
    r = convert_base(value, base)
    return "\n".join([
        f"Decimal ...... {r['dec']}",
        f"Hexadecimal .. {r['hex']}",
        f"Binário ...... {r['bin']}",
        f"               {r['bin_grupos']}",
        f"Octal ........ {r['oct']}",
        f"Bits usados .. {r['bits']}",
    ])


# ---------------------------------------------------------------- UUID
def make_uuids(n=1, version=4, upper=False, hyphens=True):
    out = []
    for _ in range(max(1, min(int(n), 10000))):
        u = str(uuid.uuid4() if version == 4 else uuid.uuid1())
        if not hyphens:
            u = u.replace("-", "")
        out.append(u.upper() if upper else u)
    return out


# ---------------------------------------------------------------- Cron
MONTHS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto",
          "setembro", "outubro", "novembro", "dezembro"]
WEEKDAYS = ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
            "sexta-feira", "sábado"]
_WD_PLURAL = ["domingos", "segundas-feiras", "terças-feiras", "quartas-feiras",
              "quintas-feiras", "sextas-feiras", "sábados"]
_MON_ABBR = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
_DOW_ABBR = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
_CRON_FIELDS = [  # nome, min, max, nomes
    ("minuto", 0, 59, None), ("hora", 0, 23, None), ("dia do mês", 1, 31, None),
    ("mês", 1, 12, _MON_ABBR), ("dia da semana", 0, 7, _DOW_ABBR)]
CRON_MACROS = {"@yearly": "0 0 1 1 *", "@annually": "0 0 1 1 *", "@monthly": "0 0 1 * *",
               "@weekly": "0 0 * * 0", "@daily": "0 0 * * *", "@midnight": "0 0 * * *",
               "@hourly": "0 * * * *"}


def _cron_val(s, idx):
    name, lo, hi, names = _CRON_FIELDS[idx]
    s = s.strip().lower()
    if names and s[:3] in names and not s.isdigit():
        v = names.index(s[:3]) + (1 if idx == 3 else 0)
    elif s.isdigit():
        v = int(s)
    else:
        raise FdError(f"Valor inválido no campo {name}: '{s}'")
    if not lo <= v <= hi:
        raise FdError(f"{name.capitalize()} fora do limite ({lo}–{hi}): {v}")
    return v


def _cron_parts(field, idx):
    """Lista de (inicio, fim, passo, tipo) com tipo em '*', 'range', 'value'."""
    name, lo, hi, _ = _CRON_FIELDS[idx]
    parts = []
    for part in field.split(","):
        if not part:
            raise FdError(f"Vírgula sobrando no campo {name}.")
        base, _, step = part.partition("/")
        if step:
            if not step.isdigit() or int(step) == 0:
                raise FdError(f"Passo inválido no campo {name}: '/{step}'")
            step = int(step)
        else:
            step = 1
        if base in ("*", "?"):
            parts.append((lo if idx != 4 else 0, hi if idx != 4 else 6, step, "*"))
        elif "-" in base:
            a, b = base.split("-", 1)
            a, b = _cron_val(a, idx), _cron_val(b, idx)
            if a > b:
                raise FdError(f"Intervalo invertido no campo {name}: {a}-{b}")
            parts.append((a, b, step, "range"))
        else:
            a = _cron_val(base, idx)
            parts.append((a, hi if part.count("/") else a, step,
                          "from" if part.count("/") else "value"))
    return parts


def _cron_set(parts, idx):
    vals = set()
    for a, b, step, _ in parts:
        vals.update(range(a, b + 1, step))
    if idx == 4 and 7 in vals:
        vals.discard(7)
        vals.add(0)
    return vals


def cron_parse(expr):
    expr = expr.strip()
    expr = CRON_MACROS.get(expr.lower(), expr)
    fields = expr.split()
    if len(fields) != 5:
        raise FdError(f"A expressão cron precisa de 5 campos (minuto hora dia mês dia-da-semana); "
                      f"veio {len(fields)}.")
    parts = [_cron_parts(f, i) for i, f in enumerate(fields)]
    sets = [_cron_set(p, i) for i, p in enumerate(parts)]
    return fields, parts, sets


def _join(items):
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " e " + items[-1]


def _fmt(v, idx):
    if idx == 3:
        return MONTHS[v - 1]
    if idx == 4:
        return WEEKDAYS[v % 7]
    if idx == 1:
        return f"{v:02d}h"
    return str(v)


_UNIT = {0: ("minuto", "minutos"), 1: ("hora", "horas"), 2: ("dia", "dias"),
         3: ("mês", "meses"), 4: ("dia da semana", "dias da semana")}


def _part_desc(p, idx):
    a, b, step, kind = p
    plural = _UNIT[idx][1]
    if kind == "*":
        return f"a cada {step} {plural}" if step > 1 else ""
    if kind == "value":
        return _fmt(a, idx)
    if kind == "from":
        return f"a cada {step} {plural} a partir de {_fmt(a, idx)}"
    if idx == 1:
        rng = f"das {_fmt(a, 1)} às {_fmt(b, 1)}"
    elif idx == 2:
        rng = f"do dia {a} ao {b}"
    else:
        rng = f"de {_fmt(a, idx)} a {_fmt(b, idx)}"
    return f"a cada {step} {plural}, {rng}" if step > 1 else rng


def _is_values(parts):
    return all(k == "value" for *_, k in parts)


def cron_describe(expr):
    fields, parts, sets = cron_parse(expr)
    mp, hp, dp, mop, wp = parts
    out = []
    # ---- horário
    if fields[0] == "*" and fields[1] == "*":
        out.append("a cada minuto")
    elif _is_values(mp) and _is_values(hp) and len(sets[0]) * len(sets[1]) <= 12:
        times = [f"{h:02d}:{m:02d}" for h in sorted(sets[1]) for m in sorted(sets[0])]
        out.append(("às " if len(times) > 1 or times[0][:2] != "01" else "à ") + _join(times))
    else:
        if fields[0] == "*":
            out.append("a cada minuto")
        elif _is_values(mp):
            vals = sorted(sets[0])
            if fields[1] == "*" and vals == [0]:
                out.append("no início de cada hora")
            else:
                pre = "no minuto " if len(vals) == 1 else "nos minutos "
                out.append(pre + _join(str(v) for v in vals)
                           + (" de cada hora" if fields[1] == "*" else ""))
        else:
            out.append(_join(_part_desc(p, 0) for p in mp))
        if fields[1] != "*":
            if _is_values(hp):
                vals = sorted(sets[1])
                pre = "na hora " if len(vals) == 1 else "nas horas "
                out.append(pre + _join(_fmt(v, 1) for v in vals))
            else:
                out.append(_join(_part_desc(p, 1) for p in hp))
    # ---- dias
    day_bits = []
    if fields[2] not in ("*", "?"):
        if _is_values(dp):
            vals = sorted(sets[2])
            day_bits.append(("no dia " if len(vals) == 1 else "nos dias ")
                            + _join(str(v) for v in vals) + " do mês")
        else:
            day_bits.append(_join(_part_desc(p, 2) for p in dp)
                            + (" do mês" if any(k == "range" for *_, k in dp) else ""))
    if fields[4] not in ("*", "?"):
        if _is_values(wp):
            vals = sorted({v % 7 for v in sets[4]})
            first = vals[0]
            pre = "aos " if first in (0, 6) else "às "
            day_bits.append(pre + _join(_WD_PLURAL[v] for v in vals))
        else:
            day_bits.append(_join(_part_desc(p, 4) for p in wp))
    if day_bits:
        out.append(" ou ".join(day_bits))
    if fields[3] != "*":
        if _is_values(mop):
            out.append("em " + _join(MONTHS[v - 1] for v in sorted(sets[3])))
        else:
            out.append(_join(_part_desc(p, 3) for p in mop))
    text = ", ".join(x for x in out if x)
    return text[:1].upper() + text[1:] + "."


def cron_next(expr, start=None, count=5):
    fields, _, sets = cron_parse(expr)
    mins, hours, doms, months, dows = sets
    dom_any = fields[2] in ("*", "?")
    dow_any = fields[4] in ("*", "?")
    t = (start or dt.datetime.now()).replace(second=0, microsecond=0) + dt.timedelta(minutes=1)
    res = []
    limit = t + dt.timedelta(days=366 * 5)
    while len(res) < count and t < limit:
        if t.month not in months:
            t = (t.replace(day=1, hour=0, minute=0) + dt.timedelta(days=32)).replace(day=1)
            continue
        wd = (t.weekday() + 1) % 7   # domingo = 0
        dm, ww = t.day in doms, wd in dows
        if dom_any and dow_any:
            day_ok = True
        elif dom_any:
            day_ok = ww
        elif dow_any:
            day_ok = dm
        else:
            day_ok = dm or ww
        if not day_ok:
            t = t.replace(hour=0, minute=0) + dt.timedelta(days=1)
            continue
        if t.hour not in hours:
            t = t.replace(minute=0) + dt.timedelta(hours=1)
            continue
        if t.minute not in mins:
            t += dt.timedelta(minutes=1)
            continue
        res.append(t)
        t += dt.timedelta(minutes=1)
    return res


def cron_report(expr, start=None):
    desc = cron_describe(expr)
    nxt = cron_next(expr, start)
    lines = [desc, "", "Próximas execuções:"]
    if not nxt:
        lines.append("  (nenhuma nos próximos 5 anos — data impossível?)")
    for t in nxt:
        lines.append(f"  {WEEKDAYS[(t.weekday() + 1) % 7]:<14} {t:%d/%m/%Y %H:%M}")
    return "\n".join(lines)


# ---------------------------------------------------------------- Cores
def parse_color(text):
    s = text.strip().lower()
    if not s:
        raise FdError("Digite uma cor: #7c5cff, rgb(124, 92, 255) ou hsl(252, 100%, 68%).")
    m = re.fullmatch(r"#?([0-9a-f]{3}|[0-9a-f]{6})", s)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = re.fullmatch(r"hsla?\(\s*([\d.]+)(?:deg)?\s*[, ]\s*([\d.]+)%?\s*[, ]\s*([\d.]+)%?.*\)", s)
    if m:
        hh, ss, ll = (float(x) for x in m.groups())
        if ss > 100 or ll > 100:
            raise FdError("Saturação e luminosidade vão de 0% a 100%.")
        r, g, b = colorsys.hls_to_rgb((hh % 360) / 360, ll / 100, ss / 100)
        return tuple(round(x * 255) for x in (r, g, b))
    m = re.fullmatch(r"(?:rgba?\()?\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*(?:[,/][^)]*)?\)?", s)
    if m:
        rgb = tuple(int(x) for x in m.groups())
        if any(v > 255 for v in rgb):
            raise FdError("Cada canal RGB vai de 0 a 255.")
        return rgb
    raise FdError("Formato não reconhecido. Use #RRGGBB, #RGB, rgb(r, g, b) ou hsl(h, s%, l%).")


def color_info(text):
    r, g, b = parse_color(text)
    h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    hx = f"#{r:02x}{g:02x}{b:02x}"
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return {"rgb": (r, g, b), "hex": hx,
            "hsl": (round(h * 360), round(s * 100), round(l * 100)),
            "text_color": "#000000" if lum > 140 else "#ffffff"}


def color_report(text):
    c = color_info(text)
    r, g, b = c["rgb"]
    hh, ss, ll = c["hsl"]
    return "\n".join([
        f"HEX ...... {c['hex']}",
        f"HEX ...... {c['hex'].upper()}",
        f"RGB ...... rgb({r}, {g}, {b})",
        f"HSL ...... hsl({hh}, {ss}%, {ll}%)",
        f"Qt/C ..... QColor({r}, {g}, {b})",
        f"0x ....... 0x{c['hex'][1:].upper()}",
    ])


# ---------------------------------------------------------------- Escape
ESCAPE_LANGS = ["JSON", "Python", "C / C++ / Java", "HTML", "Regex"]


def _c_escape(text, quote='"'):
    m = {"\\": "\\\\", "\n": "\\n", "\r": "\\r", "\t": "\\t", "\0": "\\0",
         "\b": "\\b", "\f": "\\f", "\v": "\\v", quote: "\\" + quote}
    out = []
    for ch in text:
        if ch in m:
            out.append(m[ch])
        elif ord(ch) < 32 or ord(ch) == 127:
            out.append(f"\\x{ord(ch):02x}")
        else:
            out.append(ch)
    return "".join(out)


def escape_text(text, lang):
    if lang == "JSON":
        return json.dumps(text, ensure_ascii=False)[1:-1]
    if lang == "Python":
        return _c_escape(text, "'").replace('"', '\\"')
    if lang.startswith("C"):
        return _c_escape(text, '"')
    if lang == "HTML":
        return html.escape(text, quote=True)
    if lang == "Regex":
        return re.escape(text)
    raise FdError(f"Linguagem desconhecida: {lang}")


def unescape_text(text, lang):
    try:
        if lang == "JSON":
            s = re.sub(r'(?<!\\)((?:\\\\)*)"', r'\1\\"', text)  # aspas soltas
            s = s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")
            return json.loads('"' + s + '"')
        if lang == "HTML":
            return html.unescape(text)
        if lang == "Regex":
            return re.sub(r"\\(.)", r"\1", text, flags=re.S)
        # Python e C: escapes estilo C
        fixed = re.sub(r"\\0(?![0-7])", r"\\x00", text)
        return fixed.encode("latin-1", "backslashreplace").decode("unicode_escape")
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise FdError(f"Não deu pra desescapar: {e}") from None


# ---------------------------------------------------------------- Base64 / URL
ENCODINGS = ["Base64", "Base64 (URL-safe)", "URL (percent-encoding)"]


def encode_text(text, kind):
    if kind == "Base64":
        return base64.b64encode(text.encode("utf-8")).decode("ascii")
    if kind == "Base64 (URL-safe)":
        return base64.urlsafe_b64encode(text.encode("utf-8")).decode("ascii").rstrip("=")
    return urllib.parse.quote(text, safe="")


def decode_text(text, kind):
    if kind.startswith("Base64"):
        s = "".join(text.split())
        s += "=" * (-len(s) % 4)
        try:
            raw = (base64.urlsafe_b64decode(s) if "URL" in kind or "-" in s or "_" in s
                   else base64.b64decode(s, validate=True))
        except (ValueError, base64.binascii.Error):
            raise FdError("Isso não é Base64 válido.") from None
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return "(binário, não é texto UTF-8) hex: " + raw.hex(" ")
    return urllib.parse.unquote(text)


# ---------------------------------------------------------------- Hash
HASHES = ["md5", "sha1", "sha256", "sha512", "sha3_256", "blake2b"]


def hash_report(text, upper=False):
    data = text.encode("utf-8")
    lines = []
    for name in HASHES:
        h = hashlib.new(name, data).hexdigest()
        lines.append(f"{name.upper():<9} {h.upper() if upper else h}")
    lines.append(f"{'CRC32':<9} {__import__('zlib').crc32(data):08x}")
    return "\n".join(lines)


# ---------------------------------------------------------------- Timestamp
def timestamp_report(text, now=None):
    s = text.strip()
    now = now or dt.datetime.now().astimezone()
    if not s or s.lower() == "agora":
        d = now
    elif re.fullmatch(r"-?\d+(\.\d+)?", s):
        v = float(s)
        unit = "segundos"
        if abs(v) >= 1e14:
            v, unit = v / 1e6, "microssegundos"
        elif abs(v) >= 1e11:
            v, unit = v / 1000, "milissegundos"
        try:
            d = dt.datetime.fromtimestamp(v, dt.timezone.utc).astimezone()
        except (OverflowError, OSError, ValueError):
            raise FdError("Timestamp fora do intervalo suportado.") from None
        s = f"{s} ({unit})"
    else:
        d = None
        txt = s.replace("T", " ").replace("Z", "+00:00")
        for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
            try:
                d = dt.datetime.strptime(s, fmt).astimezone()
                break
            except ValueError:
                pass
        if d is None:
            try:
                d = dt.datetime.fromisoformat(txt)
            except ValueError:
                raise FdError("Não entendi. Use um timestamp (1730000000) ou data "
                              "(05/11/2026 14:30 ou 2026-11-05T14:30:00).") from None
            d = d.astimezone() if d.tzinfo is None else d
    ts = d.timestamp()
    delta = d - now
    secs = abs(delta.total_seconds())
    if secs < 60:
        rel = "agora"
    else:
        for unit, n in (("ano(s)", 31536000), ("dia(s)", 86400), ("hora(s)", 3600), ("minuto(s)", 60)):
            if secs >= n:
                q = int(secs // n)
                rel = f"daqui a {q} {unit}" if delta.total_seconds() > 0 else f"há {q} {unit}"
                break
    local = d.astimezone()
    utc = d.astimezone(dt.timezone.utc)
    return "\n".join([
        f"Entrada ........... {s or 'agora'}",
        f"Timestamp (s) ..... {int(ts) if ts == int(ts) else round(ts, 3)}",
        f"Timestamp (ms) .... {round(ts * 1000)}",
        f"Data local ........ {WEEKDAYS[(local.weekday() + 1) % 7]}, {local:%d/%m/%Y %H:%M:%S} (UTC{local:%z})",
        f"UTC ............... {utc:%d/%m/%Y %H:%M:%S}",
        f"ISO 8601 .......... {local.isoformat()}",
        f"Relativo .......... {rel}",
    ])
