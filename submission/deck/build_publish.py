"""build_publish.py: copies the slides written so far into the artifact's folder, with each picture's published address."""
import json, os, re, sys
D=os.path.dirname(os.path.abspath(__file__)); R='/private/tmp/claude-501/-Users-hartleyscales/b489eb9f-2d5e-48bd-913b-c893d5115106/scratchpad/deck/project'
A=json.load(open(os.path.join(D,'assets.json')))
order=[l.strip() for l in open(os.path.join(D,'order.txt')) if l.strip() and os.path.exists(os.path.join(D,'slides',l.strip()+'.html'))]
os.makedirs(R+'/slides', exist_ok=True)
missing=set()
def sub(m):
    if m.group(1) not in A: missing.add(m.group(1)); return m.group(0)
    return A[m.group(1)]
for s in order:
    open(R+'/slides/%s.html'%s,'w').write(re.sub(r'asset:([\w.\-]+)', sub, open(os.path.join(D,'slides',s+'.html')).read()))
open(R+'/deck.css','w').write(open(os.path.join(D,'deck.css')).read())
F="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Outfit:wght@300..600&display=swap"
deck={"v":5,"createdOnFiles":{"v":1,"at":"2026-11-15T09:25:00Z"},"lists":"css","format":{"v":1,"shared":["project/deck.css"]},"title":"Quiet Hours","order":order,"cover":"cover",
 "sections":{"why":{"description":"The problem Quiet Hours answers, why the apps people already use don't solve it, and the idea in one line.","start":"cover"}},
 "faces":{"outfit":{"family":"Outfit","href":F},"instrument-serif":{"family":"Instrument Serif","href":F}},"designSystems":[]}
if 'week' in order: deck["sections"]["what"]={"description":"How a week goes, what happens inside the window, and what the AI does.","start":"week"}
if 'path' in order: deck["sections"]["real"]={"description":"What it takes to run at USC.","start":"path"}
json.dump(deck, open(R+'/deck.json','w'), indent=1, ensure_ascii=False)
print('order', order, 'missing assets', sorted(missing))
