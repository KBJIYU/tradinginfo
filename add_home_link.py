# -*- coding: utf-8 -*-
"""在每份報告加上固定的「回首頁」連結。可重複執行(idempotent)。

v2(2026/09/17):配合新版報告版型(左側 344px 常駐結論欄)調整——
  · 位置由左下改為**右下**(左下會被結論欄蓋住)
  · 配色改為 v2 藍(#1E46B8 / #BCC8DC / #55617A)、圓角 20px→6px
  · 字型改以 Noto Sans TC 優先
舊的 7 份 v1 報告已含 v1 版 SNIPPET,因 MARK 判斷會被跳過,不受影響。
"""
import glob, os, re, sys

SNIPPET = '''
<!-- 回首頁(由 add_home_link.py 注入,可重複執行) -->
<a href="index.html" id="homeLink" title="回研究報告目錄">
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor"
       stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M2.2 7.4 8 2.4l5.8 5"/><path d="M3.9 8.6V13a.6.6 0 0 0 .6.6h2.4V10h2.2v3.6h2.4a.6.6 0 0 0 .6-.6V8.6"/>
  </svg>回首頁</a>
<style>
#homeLink{position:fixed;right:16px;bottom:16px;z-index:80;display:inline-flex;align-items:center;gap:6px;
  background:#fff;border:1px solid #BCC8DC;border-radius:6px;padding:8px 14px;font-size:13px;line-height:1;
  color:#55617A;text-decoration:none;white-space:nowrap;box-shadow:0 2px 10px rgba(20,26,34,.10);
  font-family:"Noto Sans TC","PingFang TC","Microsoft JhengHei",system-ui,-apple-system,sans-serif;
  transition:color .15s,border-color .15s,box-shadow .15s;}
#homeLink:hover{color:#1E46B8;border-color:#A9BCE8;box-shadow:0 4px 14px rgba(30,70,184,.18);}
#homeLink:focus-visible{outline:2px solid #1E46B8;outline-offset:2px;}
@media(max-width:520px){#homeLink{padding:7px 12px;font-size:12.5px;right:12px;bottom:12px;}}
@media print{#homeLink{display:none;}}
</style>
'''

MARK = 'id="homeLink"'

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))
    changed = skipped = 0
    for path in sorted(glob.glob(os.path.join(root, '*.html'))):
        fn = os.path.basename(path)
        if fn == 'index.html':
            continue
        s = open(path, encoding='utf-8').read()
        if MARK in s:
            print('  = 已有  %s' % fn); skipped += 1; continue
        m = re.search(r'</body\s*>', s, re.I)
        if m:
            s = s[:m.start()] + SNIPPET + s[m.start():]
        else:
            s = s + SNIPPET          # 沒有 </body> 就附加在檔尾
        open(path, 'w', encoding='utf-8', newline='\n').write(s)
        print('  + 加入  %s' % fn); changed += 1
    print('完成 — 新增 %d 份,已有 %d 份' % (changed, skipped))

if __name__ == '__main__':
    main()
