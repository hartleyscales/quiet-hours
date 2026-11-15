"""build_preview.py: one local page of every slide written so far, at half size, with the app's own font files."""
import os, re, sys
D=os.path.dirname(os.path.abspath(__file__)); OUT=os.path.join(D,'preview')
os.makedirs(OUT, exist_ok=True)
order=[l.strip() for l in open(os.path.join(D,'order.txt')) if l.strip()]
F='/Users/hartleyscales/quiet-hours/ios/App/Resources/Fonts/'
for f in os.listdir(F):
    if f.endswith('.ttf') and not os.path.exists(os.path.join(OUT,f)): os.system('cp "%s" "%s"' % (F+f, OUT))
os.system('rm -rf "%s/assets" && cp -R "%s/assets" "%s/assets"' % (OUT, D, OUT))
faces=''.join("@font-face{font-family:'Outfit';font-weight:%d;src:url(%s)}" % (w,n) for w,n in ((300,'Outfit-Light.ttf'),(400,'Outfit-Regular.ttf'),(500,'Outfit-Medium.ttf')))+"@font-face{font-family:'Instrument Serif';font-style:italic;src:url(InstrumentSerif-Italic.ttf)}"
base="*{margin:0} body{background:#444;zoom:%s} body>section{width:1920px!important;height:1080px!important;overflow:hidden!important;box-sizing:border-box!important;position:relative;isolation:isolate;margin-bottom:24px} aside{display:none!important} p,li,h1,h2,h3{overflow-wrap:break-word;text-wrap:pretty}"
zoom=sys.argv[1] if len(sys.argv)>1 else '0.4'
html='<!doctype html><meta charset="utf-8"><title>deck preview</title><style>'+faces+base % zoom+'</style><style>'+open(os.path.join(D,'deck.css')).read()+'</style><body>'
for s in order:
    p=os.path.join(D,'slides',s+'.html')
    if os.path.exists(p): html+=re.sub(r'asset:([\w.\-]+)', r'assets/\1', open(p).read())
open(os.path.join(OUT,'index.html'),'w').write(html); print('built', len(order))
