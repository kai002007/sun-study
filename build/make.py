# -*- coding: utf-8 -*-
"""一键更新：把 src/book.md 重新排印成 index.html / print.html / assets/。

用法：双击书籍目录里的「更新网页.bat」，或者在这个目录下执行 py -3 build/make.py。
不需要联网、不需要安装任何第三方库。
"""
import sys, pathlib

HERE = pathlib.Path(__file__).resolve().parent      # …/build
ROOT = HERE.parent                                   # 书籍目录
sys.path.insert(0, str(HERE))
import md2site                                       # noqa: E402

TITLE = "AI 时代个人操作系统"
SUBTITLE = "认知、健康与财富自由的地球 Online 攻略"
AUTHOR = "孙宇晨 口述 · 邵艾伦 对谈 · 4 小时 22 分完整实录 + 精读手册 合编"
NOTE = "内容来源：播客《对话孙宇晨：年轻人如何抓住 AI 时代的机会？》｜青云学长 整理｜学习性整理，非商业出版"


if __name__ == "__main__":
    md = ROOT / "src" / "book.md"
    if not md.exists():
        print("找不到 src/book.md —— 请确认这个脚本还在书籍目录的 build 文件夹里。")
        sys.exit(1)
    print("正在把 %s 排印成网页…" % md)
    st = md2site.build(str(md), str(ROOT), TITLE, SUBTITLE, AUTHOR, NOTE)
    print("完成：", st)
    print("已重新生成 index.html / print.html / assets/")
