# -*- coding: utf-8 -*-
"""md2site.py —— 零依赖（只用 Python 标准库）的 Markdown 书稿 -> 静态网站生成器。

用途：把一份 Markdown 书稿编译成一个可离线打开、可直接放到 GitHub Pages 的整站。
产出：
  index.html        —— 整本书（侧边目录 + 全文搜索 + 深浅色 + 打印样式）
  assets/book.css   —— 样式
  assets/book.js    —— 搜索/目录高亮/主题切换（原生 JS，无第三方库）
  assets/search.js  —— 构建期生成的全文检索索引
  print.html        —— 供 Edge/Chrome 无头打印成 PDF 的版本

用法：
  py -3 md2site.py <书稿.md> <输出目录> --title "书名" --subtitle "副标题" --author "整理者"
"""
import argparse
import html
import json
import os
import re
import sys
import unicodedata

# ---------------------------------------------------------------- 行内标记
INLINE = [
    (re.compile(r"`([^`]+)`"), r"<code>\1</code>"),
    (re.compile(r"\*\*([^*]+)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)"), r"<em>\1</em>"),
    (re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)"), r'<a href="\2">\1</a>'),
]


def inline(text):
    """先转义 HTML，再套行内标记（顺序保证 < > & 不会被二次解释）。"""
    out = html.escape(text, quote=False)
    for pat, rep in INLINE:
        out = pat.sub(rep, out)
    return out


def slug(text, used):
    """生成稳定锚点：中文保留，空格转 '-'，重复加序号。"""
    s = unicodedata.normalize("NFKC", text)
    s = re.sub(r"[\s\u3000]+", "-", s.strip())
    s = re.sub(r"[^\w\-\u4e00-\u9fff]", "", s)
    s = re.sub(r"-{2,}", "-", s) or "sec"
    base, n = s, 2
    while s in used:
        s = f"{base}-{n}"
        n += 1
    used.add(s)
    return s


# ---------------------------------------------------------------- 块级解析
def parse(md):
    """返回 [(level, title, anchor, html)]，level=0 表示正文块。"""
    lines = md.replace("\r\n", "\n").split("\n")
    used, out, buf, i = set(), [], [], 0

    def flush():
        if buf:
            para = " ".join(x.strip() for x in buf).strip()
            if para:
                out.append((0, None, None, "<p>" + inline(para) + "</p>"))
            buf.clear()

    while i < len(lines):
        ln = lines[i]
        s = ln.strip()

        # 围栏代码块
        if s.startswith("```"):
            flush()
            lang = s[3:].strip()
            i += 1
            code = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            i += 1
            cls = f' class="lang-{lang}"' if lang else ""
            out.append((0, None, None, f"<pre{cls}><code>{html.escape(chr(10).join(code))}</code></pre>"))
            continue

        # 标题
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if m:
            flush()
            lv, title = len(m.group(1)), m.group(2).strip()
            anchor = slug(title, used)
            tag = f"h{min(lv + 1, 6)}"          # 书内 h1 对应页面 h2，页面 h1 留给书名
            out.append((lv, title, anchor, f'<{tag} id="{anchor}">{inline(title)}</{tag}>'))
            i += 1
            continue

        # 分隔线
        if re.fullmatch(r"(-{3,}|\*{3,}|_{3,})", s):
            flush()
            out.append((0, None, None, "<hr>"))
            i += 1
            continue

        # 表格
        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:\-|]+\|$", lines[i + 1].strip()):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not re.match(r"^[\s:\-|]+$", "|".join(cells)):
                    rows.append(cells)
                i += 1
            if rows:
                w = max(len(r) for r in rows)
                head = "".join(f"<th>{inline(c)}</th>" for c in rows[0] + [""] * (w - len(rows[0])))
                body = "".join(
                    "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r + [""] * (w - len(r))) + "</tr>"
                    for r in rows[1:]
                )
                out.append((0, None, None,
                            f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'))
            continue

        # 引用
        if s.startswith(">"):
            flush()
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append((0, None, None, "<blockquote>" + inline(" ".join(quote)) + "</blockquote>"))
            continue

        # 列表
        m = re.match(r"^([-*+]|\d+\.)\s+(.*)$", s)
        if m:
            flush()
            ordered = m.group(1)[0].isdigit()
            items = []
            while i < len(lines):
                mm = re.match(r"^\s*(?:[-*+]|\d+\.)\s+(.*)$", lines[i])
                if not mm:
                    break
                items.append(mm.group(1).strip())
                i += 1
            tag = "ol" if ordered else "ul"
            out.append((0, None, None, f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>"))
            continue

        # 空行 = 段落结束
        if not s:
            flush()
            i += 1
            continue

        buf.append(ln)
        i += 1

    flush()
    return out


# ---------------------------------------------------------------- CSS
CSS = """\
:root{
  --bg:#faf9f7; --fg:#1d1c1a; --muted:#6b6862; --line:#e3e0da;
  --card:#ffffff; --accent:#b23a2f; --accent-soft:#f6e7e4; --mark:#ffe9a8;
  --sidebar:290px;
}
html[data-theme=dark]{
  --bg:#14140f; --fg:#e9e6df; --muted:#9a958b; --line:#2c2b25;
  --card:#1c1b16; --accent:#e0796a; --accent-soft:#2a1c19; --mark:#5a4a12;
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);
  font-family:"Noto Serif SC","Songti SC","Source Han Serif SC",Georgia,"Microsoft YaHei",serif;
  font-size:17px;line-height:1.95;-webkit-text-size-adjust:100%}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}

/* 顶栏 */
.topbar{position:sticky;top:0;z-index:40;display:flex;gap:12px;align-items:center;
  padding:10px 18px;background:color-mix(in srgb,var(--bg) 88%,transparent);
  backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.topbar .bt{font-size:15px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.topbar .sp{flex:1}
.iconbtn{border:1px solid var(--line);background:var(--card);color:var(--fg);
  border-radius:9px;padding:6px 11px;font-size:14px;cursor:pointer;font-family:inherit}
.iconbtn:hover{border-color:var(--accent);color:var(--accent)}
#q{flex:0 1 300px;min-width:110px;padding:7px 12px;border:1px solid var(--line);border-radius:9px;
  background:var(--card);color:var(--fg);font-family:inherit;font-size:14px}

/* 侧栏 */
.side{position:fixed;top:0;left:0;bottom:0;width:var(--sidebar);overflow-y:auto;
  padding:22px 16px 60px;border-right:1px solid var(--line);background:var(--card)}
.side h1{font-size:17px;line-height:1.5;margin:0 0 4px}
.side .sub{font-size:12.5px;color:var(--muted);margin-bottom:14px;line-height:1.6}
.side ol{list-style:none;margin:0;padding:0;counter-reset:c}
.side li.c1{counter-increment:c;margin:7px 0 2px}
.side li.c1>a{font-size:14.5px;font-weight:600;color:var(--fg)}
.side li.c2>a{font-size:13px;color:var(--muted);padding-left:14px;display:block}
.side li.c2{margin:2px 0}
.side li.c3>a{font-size:12.5px;color:var(--muted);padding-left:28px;display:block;opacity:.85}
.side a.on{color:var(--accent)!important}
.side .g{padding-left:6px}
.wrap{margin-left:var(--sidebar)}
.page{max-width:760px;margin:0 auto;padding:34px 26px 120px}

/* 正文 */
.page h1{font-size:30px;line-height:1.45;margin:6px 0 6px;letter-spacing:.5px}
.page h2{font-size:20.5px;margin:40px 0 12px;padding-top:16px;border-top:1px solid var(--line)}
.page h3{font-size:18.5px;margin:30px 0 10px}
.page h4{font-size:17px;margin:22px 0 8px;color:var(--muted)}
.page h5{font-size:15.5px;margin:18px 0 6px;color:var(--muted);font-weight:600}
.page h6{font-size:14.5px;margin:14px 0 6px;color:var(--muted)}
.page p{margin:0 0 15px;text-align:justify}
.page ul,.page ol{margin:0 0 16px;padding-left:1.5em}
.page li{margin:5px 0}
.page blockquote{margin:16px 0;padding:10px 16px;border-left:3px solid var(--accent);
  background:var(--accent-soft);border-radius:0 8px 8px 0;color:var(--fg)}
.page hr{border:0;border-top:1px solid var(--line);margin:34px 0}
.page code{background:var(--accent-soft);padding:1px 5px;border-radius:5px;font-size:.9em;
  font-family:ui-monospace,Consolas,monospace}
.page pre{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;overflow-x:auto}
.page pre code{background:none;padding:0}
.tw{overflow-x:auto;margin:16px 0}
.page table{border-collapse:collapse;width:100%;font-size:15px}
.page th,.page td{border:1px solid var(--line);padding:7px 10px;text-align:left;vertical-align:top}
.page th{background:var(--accent-soft);font-weight:600}
.cover{text-align:center;padding:56px 0 30px;border-bottom:1px solid var(--line);margin-bottom:26px}
.cover .t{font-size:34px;font-weight:700;line-height:1.4;margin-bottom:10px}
.cover .s{font-size:19px;color:var(--accent);margin-bottom:14px}
.cover .m{font-size:13.5px;color:var(--muted)}
.hl{background:var(--mark)}
#top{position:fixed;right:22px;bottom:22px;z-index:45;display:none}

/* 搜索结果 */
#res{position:fixed;inset:0;z-index:60;background:color-mix(in srgb,var(--bg) 70%,transparent);
  backdrop-filter:blur(4px);padding:70px 18px 18px;overflow-y:auto;display:none}
#res .box{max-width:760px;margin:0 auto;background:var(--card);border:1px solid var(--line);
  border-radius:14px;padding:14px}
#res .row{padding:11px 6px;border-bottom:1px solid var(--line);cursor:pointer}
#res .row:hover{background:var(--accent-soft)}
#res .row b{display:block;font-size:15px;margin-bottom:3px}
#res .row span{font-size:13.5px;color:var(--muted)}
#res .row mark{background:var(--mark);color:inherit}

@media (max-width:1000px){
  :root{--sidebar:0px}
  .side{transform:translateX(-100%);transition:.25s;width:288px;box-shadow:0 0 40px rgba(0,0,0,.15)}
  .side.open{transform:none}
  .wrap{margin-left:0}
  .page{padding:22px 18px 100px}
  body{font-size:16.5px}
  .topbar .bt{display:none}
  #q{flex:1}
}

/* 打印 / 导出 PDF */
@page{size:A4;margin:18mm 16mm}
@media print{
  .topbar,.side,#top,#res{display:none!important}
  .wrap{margin:0}
  .page{max-width:none;padding:0}
  body{background:#fff;color:#000;font-size:11.5pt;line-height:1.75}
  .page h2{page-break-before:always;border-top:0;padding-top:0}
  .page h1{page-break-before:always}
  .cover{page-break-after:always}
  a{color:#000;text-decoration:none}
  table,blockquote,pre{page-break-inside:avoid}
}
"""

# ---------------------------------------------------------------- JS
JS = """\
(function(){
  var root=document.documentElement, body=document.body;
  // 主题
  try{var t=localStorage.getItem('book-theme'); if(t) root.dataset.theme=t;}catch(e){}
  function flip(){var d=root.dataset.theme==='dark'?'light':'dark';root.dataset.theme=d;
    try{localStorage.setItem('book-theme',d)}catch(e){}}
  var tb=document.getElementById('theme'); if(tb) tb.onclick=flip;
  // 侧栏
  var side=document.querySelector('.side'), mb=document.getElementById('menu');
  if(mb) mb.onclick=function(){side.classList.toggle('open')};
  side.addEventListener('click',function(e){ if(e.target.tagName==='A') side.classList.remove('open'); });
  // 当前章节高亮
  var links=[].slice.call(document.querySelectorAll('.side a[href^="#"]'));
  var map={}; links.forEach(function(a){map[decodeURIComponent(a.getAttribute('href').slice(1))]=a;});
  var heads=[].slice.call(document.querySelectorAll('.page h2[id],.page h3[id],.page h4[id]'));
  var cur=null;
  function spy(){
    var y=window.scrollY+130, best=null;
    for(var i=0;i<heads.length;i++){ if(heads[i].offsetTop<=y) best=heads[i]; else break; }
    if(best&&best!==cur){ cur=best;
      links.forEach(function(a){a.classList.remove('on')});
      var a=map[best.id]; if(a){a.classList.add('on');} }
  }
  window.addEventListener('scroll',spy,{passive:true}); spy();
  // 回到顶部
  var top=document.getElementById('top');
  window.addEventListener('scroll',function(){ top.style.display=window.scrollY>700?'block':'none'; },{passive:true});
  top.onclick=function(){window.scrollTo({top:0,behavior:'smooth'})};
  // 全文搜索
  var IDX=(window.SEARCH_INDEX||[]);
  var res=document.getElementById('res'), box=res.querySelector('.box'), q=document.getElementById('q');
  function esc(s){return s.replace(/[&<>]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;'}[c]})}
  function run(){
    var kw=q.value.trim().toLowerCase();
    if(kw.length<1){res.style.display='none';box.innerHTML='';return;}
    var hit=[], n=0;
    for(var i=0;i<IDX.length&&hit.length<60;i++){
      var s=IDX[i], p=s.x.toLowerCase().indexOf(kw);
      if(p>=0){
        var a=Math.max(0,p-30), b=Math.min(s.x.length,p+kw.length+70);
        hit.push('<div class="row" data-h="'+s.i+'"><b>'+esc(s.t)+'</b><span>'+
          (a>0?'…':'')+esc(s.x.slice(a,p))+'<mark>'+esc(s.x.substr(p,kw.length))+'</mark>'+
          esc(s.x.slice(p+kw.length,b))+(b<s.x.length?'…':'')+'</span></div>');
      }
    }
    box.innerHTML = hit.length? hit.join('') : '<div class="row">没有找到「'+esc(q.value)+'」</div>';
    res.style.display='block';
    [].forEach.call(box.querySelectorAll('.row[data-h]'),function(r){
      r.onclick=function(){ location.hash=r.dataset.h; res.style.display='none'; };
    });
  }
  var tm=null;
  q.addEventListener('input',function(){clearTimeout(tm);tm=setTimeout(run,140)});
  res.addEventListener('click',function(e){ if(e.target===res) res.style.display='none'; });
  document.addEventListener('keydown',function(e){
    if(e.key==='/'&&document.activeElement!==q){e.preventDefault();q.focus();}
    if(e.key==='Escape'){res.style.display='none';q.blur();}
  });
})();
"""


def build(md_path, out_dir, title, subtitle, author, cover_note=""):
    md = open(md_path, encoding="utf-8").read()
    items = parse(md)
    os.makedirs(os.path.join(out_dir, "assets"), exist_ok=True)

    # 目录 + 正文
    toc, body, idx = [], [], []
    chapter = ""
    cur_id, cur_t, cur_buf = None, None, []

    def flush_idx():
        if cur_id and cur_buf:
            idx.append({"i": cur_id, "t": cur_t, "c": chapter, "x": " ".join(cur_buf)[:4000]})

    for lv, t, anchor, frag in items:
        if lv in (1, 2, 3):
            flush_idx()
            if lv <= 2:
                chapter = t
            cur_id, cur_t, cur_buf = anchor, t, []
            toc.append((lv, t, anchor))
        elif frag.startswith("<p>") or frag.startswith("<li>") or frag.startswith("<blockquote>"):
            if cur_id:
                cur_buf.append(re.sub(r"<[^>]+>", "", frag))
        body.append(frag)
    flush_idx()

    side = [f'<h1>{html.escape(title)}</h1>',
            f'<div class="sub">{html.escape(subtitle)}</div>',
            '<nav class="g"><ol>']
    for lv, t, a in toc:
        side.append(f'<li class="c{lv}"><a href="#{a}">{html.escape(t)}</a></li>')
    side += ["</ol></nav>"]
    side_html = "\n".join(side)

    cover = (f'<header class="cover"><div class="t">{html.escape(title)}</div>'
             f'<div class="s">{html.escape(subtitle)}</div>'
             f'<div class="m">{html.escape(author)}</div>'
             + (f'<div class="m">{html.escape(cover_note)}</div>' if cover_note else "")
             + "</header>")

    def page_html(for_print=False):
        return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(subtitle)}">
<link rel="stylesheet" href="assets/book.css">
</head>
<body>
<header class="topbar">
  <button class="iconbtn" id="menu" aria-label="目录">☰</button>
  <div class="bt">{html.escape(title)}</div>
  <div class="sp"></div>
  <input id="q" type="search" placeholder="搜索全文…（按 / 聚焦）" autocomplete="off">
  <button class="iconbtn" id="theme" aria-label="主题">◑</button>
</header>
<aside class="side">{side_html}</aside>
<div class="wrap"><main class="page">
{cover}
{chr(10).join(body)}
</main></div>
<button class="iconbtn" id="top">↑ 顶部</button>
<div id="res"><div class="box"></div></div>
<script src="assets/book.js"></script>
</body>
</html>
"""

    open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8").write(page_html())
    open(os.path.join(out_dir, "assets", "book.css"), "w", encoding="utf-8").write(CSS)
    open(os.path.join(out_dir, "assets", "book.js"), "w", encoding="utf-8").write(JS)
    open(os.path.join(out_dir, "assets", "search.js"), "w", encoding="utf-8").write(
        "window.SEARCH_INDEX=" + json.dumps(idx, ensure_ascii=False, separators=(",", ":")) + ";\n")
    # 打印版：不引侧栏脚本，直接干净排版
    open(os.path.join(out_dir, "print.html"), "w", encoding="utf-8").write(
        page_html(for_print=True).replace('<script src="assets/book.js"></script>', ""))

    return {"sections": len(toc), "blocks": len(body), "index": len(idx),
            "html_kb": round(os.path.getsize(os.path.join(out_dir, "index.html")) / 1024, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md")
    ap.add_argument("out")
    ap.add_argument("--title", default="未命名")
    ap.add_argument("--subtitle", default="")
    ap.add_argument("--author", default="")
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    st = build(a.md, a.out, a.title, a.subtitle, a.author, a.note)
    print("生成完成：", json.dumps(st, ensure_ascii=False))


if __name__ == "__main__":
    main()
