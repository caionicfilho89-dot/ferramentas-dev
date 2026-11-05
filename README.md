# 💻 Ferramentas Dev

Canivete suíço do programador, **100% offline** (nada sai do PC). Feito em Python + PyQt6.

## Funções (16)

**Formatadores**
- 🧾 **JSON** — formatar, minificar, validar (mostra linha e coluna do erro), ordenar chaves
- 📰 **XML** — formatar, minificar, validar
- 🗃️ **SQL** — palavras-chave em maiúsculas + quebras de linha (SELECT, FROM, WHERE, JOIN, AND…)
- 📊 **CSV → JSON** (separador detectado sozinho) e 📑 **JSON → CSV**

**Texto e Regex**
- 🔍 **Testador de Regex** ao vivo — destaca as correspondências, lista grupos/posições e mostra prévia da substituição
- 🆚 **Comparar textos (diff)** — linhas adicionadas/removidas coloridas + diff unificado; ignora espaços/maiúsculas
- 🧷 **Escape de string** — JSON, Python, C/C++/Java, HTML, Regex (escapar e desescapar)
- 🔣 **Base64 / URL** — codificar e decodificar
- #️⃣ **Hash** — MD5, SHA-1, SHA-256, SHA-512, SHA3, BLAKE2, CRC32

**Conversores**
- 🔢 **Bases numéricas** — binário, octal, decimal, hexadecimal
- 🎨 **Cores** — HEX ↔ RGB ↔ HSL, com amostra e seletor
- 🕒 **Timestamp ↔ data** — Unix (s/ms) para data e vice-versa

**Geradores e outros**
- 🆔 **Gerador de UUID** (v4/v1, em lote)
- ⏰ **Cron explicado** — `*/5 * * * *` → "A cada 5 minutos", com as próximas execuções
- 📏 **Contador de linhas** — linhas de código/comentário/em branco, palavras e caracteres

## Como usar

```
pip install -r requirements.txt
python ferramentas_dev.pyw
```

Use a busca no canto esquerdo pra achar uma função rapidinho. Cada resultado tem o botão **📋 Copiar**.

## Licença

MIT — veja `LICENSE`.
