"""Replace every Home in build_screens.py with the hero-and-sheet structure (V9)."""
t = open('build_screens.py').read()
END = "</div></div>\n</div>\n"

def cut(label_start):
    global t
    i = t.index('<p class="label">' + label_start); i = t.rindex('<div class="item">', 0, i); j = t.index(END, i) + len(END)
    seg = t[i:j]; t = t[:i] + t[j:]; return seg

old6 = cut('6 · Home · the day · V9')
g = old6.index('<button class="gear"'); GEAR = old6[g:old6.index('</button>', g) + 9]
for lab in ('4 · Home · voting', '5 · Home · selected', '4b · Home', '5b · Home', '6 · Home · the day · V8', '6b · Home', '7 · Home · locked', '7b · Home', '9 · Home · summary', '9b · Home', '9c · Home'):
    cut(lab)

SEND = '<b aria-hidden="true"><svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 19V5M6 11l6-6 6 6"/></svg></b>'
BAR = '<div class="bar"><span class="wm">Quiet Hours</span>' + GEAR + '</div>\n'

def hero(cap, link, big, when, stats, bigcls=""):
    three = " three" if len(stats) == 3 else ""
    cells = "".join(f'<div><b>{v}</b><span>{l}</span></div>' for v, l in stats)
    lk = f'<button type="button">{link}</button>' if link else ''
    return (f'<div class="hero">\n<div class="h9top"><span>{cap}</span>{lk}</div>\n<p class="h9big{bigcls}">{big}</p>\n'
            f'<p class="h9when">{when}</p>\n<div class="h9stats{three}">{cells}</div>\n</div>\n')

def sheet(left, right, body, foot="", cls="", card=True):
    r = f'<button type="button" class="s9more">{right}</button>' if right and right.startswith('!') else (f'<span class="s9note">{right}</span>' if right else '')
    r = r.replace('>!', '>')
    if card:      # a card with margins, hugging its content; anything pinned sits on the base surface beneath it
        return f'<div class="sheet9 card9{cls}">\n<div class="s9head"><span>{left}</span>{r}</div>\n{body}\n</div>\n{foot}'
    return f'<div class="sheet9{cls}">\n<div class="s9head"><span>{left}</span>{r}</div>\n{body}\n{foot}</div>\n'

def phone(label, cls, inner, attrs=""):
    return f'<div class="item">\n<p class="label">{label}</p>\n<div class="phone"><div class="s hm v9 {cls}"{attrs}>\n{inner}</div></div>\n</div>\n'

POSTS = [("Guitar on the lawn, come sit", "McCarthy Quad", "2m", True), ("Spikeball, anyone welcome", "Alumni Park", "9m", False), ("Jam session, bring anything", "Village fountain", "14m", False),
         ("Cooking for whoever shows up", "Cale kitchen", "21m", False), ("Pickup soccer needs two more", "Brittingham Field", "26m", False), ("Sketching on the steps", "Doheny Library", "31m", False),
         ("Walking to the Rose Garden", "Leaving from Tommy Trojan", "38m", False), ("Frisbee, all levels", "Cromwell Field", "44m", False), ("Chess, two boards going", "Campus Center patio", "52m", False),
         ("Reading on the grass", "Founders Park", "1h", False), ("Sunset walk", "Leaving Leavey at 5:30", "1h", False), ("Hammocks up, room for more", "Trousdale by Bovard", "1h", False),
         ("Basketball, next five", "Lyon Center courts", "2h", False), ("Board games in the lounge", "Ginsburg Hall", "2h", False)]

def rows(ps, mine=True):
    out = []
    for a, b, c, me in ps:
        if me and not mine: continue
        tail = '<button type="button" class="td9">Take down</button>' if me else f'<i>{c}</i>'
        out.append(f'<div class="r9"><div><b>{a}</b><span>{"Yours · " if me else ""}{b}</span></div>{tail}</div>')
    return "\n".join(out)

def composer(): return f'<div class="cmp9"><span>What you\'re doing, and where</span>{SEND}</div>\n'

OPTS = [("Thursday", "5:00 – 7:00 PM", "Most classes are out. Sunset is at 4:48.", 1204, 47), ("Sunday", "4:00 – 5:30 PM", "No home game, and the week hasn't begun.", 867, 34), ("Wednesday", "12:00 – 1:00 PM", "Lunch, when most people are on campus.", 512, 20)]
def options(on=0, tag="button", why=True):
    out = []
    for k, (d, tm, w, n, pct) in enumerate(OPTS):
        cls = "o9 on" if k == on else "o9"
        whyh = f'<span class="why">{w}</span>' if why else ''
        attr = ' type="button"' if tag == "button" else ''
        out.append(f'<{tag} class="{cls}"{attr}><span class="r1"><span class="d">{d}</span><span class="t">{tm}</span></span>{whyh}<span class="r3"><span class="track"><b style="width:{pct}%"></b></span><span class="n">{n:,} votes</span></span></{tag}>')
    return '<div class="o9s">' + "\n".join(out) + '</div>'

items = []
# 4 voting
items.append(phone('4 · Home · voting · V3 · tap an option', 'vote9',
    BAR + hero("This week's quiet hours", "Opt out", "When this week?", "Closes Tuesday, 8:00 PM", [("1d 20h", "until voting closes"), ("3,112", "Trojans in")], " sm")
    + sheet("Pick a window", "2,583 votes", options(0), '<p class="s9foot">You can change your vote until it closes.</p>\n')))
items.append(phone('4b · Home · voting · opted out', 'vote9 out9',
    BAR + hero("You're out this week.", "", "When this week?", "Closes Tuesday, 8:00 PM", [("1d 20h", "until voting closes"), ("3,111", "Trojans in")], " sm")
    + sheet("The vote so far", "2,583 votes", options(-1, "div"), '<button class="go go9" type="button">Opt back in</button>\n')))
# 5 decided
items.append(phone('5 · Home · decided · V2', 'dec9',
    BAR + hero("This week's quiet hours", "Opt out", "Thursday", "5:00 – 7:00 PM", [("1d 20h", "until it starts"), ("3,112", "Trojans in")])
    + sheet("How the vote went", "2,583 votes", options(0, "div", why=False), '<p class="s9foot">The board opens Thursday morning: say what you\'re doing, and where.</p>\n')))
items.append(phone('5b · Home · decided · opted out', 'dec9 out9',
    BAR + hero("You're out this week.", "", "Thursday", "5:00 – 7:00 PM", [("1d 20h", "until it starts"), ("3,111", "Trojans in")])
    + sheet("How the vote went", "2,583 votes", options(0, "div", why=False), '<button class="go go9" type="button">Opt back in</button>\n')))
# 6 the day
items.append(phone('6 · Home · the day · V9 · tap "See all"', 'day9',
    BAR + hero("This week's quiet hours", "Opt out", "Today", "5:00 – 7:00 PM", [("3h 12m", "until it starts"), ("3,112", "Trojans in")])
    + sheet("Going on today", "!See all 14", '<div class="s9list">\n' + rows(POSTS) + '\n</div>', composer(), " board9", card=False)))
items.append(phone('6b · Home · the day · opted out', 'day9 out9',
    BAR + hero("You're out this week.", "", "Today", "5:00 – 7:00 PM", [("3h 12m", "until it starts"), ("3,111", "Trojans in")])
    + sheet("Going on today", "13", '<div class="s9list">\n' + rows(POSTS[:5], mine=False) + '\n</div>', '<button class="go go9" type="button">Opt back in</button>\n', card=False)))
# 7 locked
def locked(cap, link, cnt):
    lk = f'<button type="button">{link}</button>' if link else ''
    return ('<img class="stars" src="data:image/png;base64,@@STARS@@" alt="">\n' + BAR + '<img class="lmoon" src="data:image/png;base64,@@MOON@@" alt="">\n'
            f'<div class="l9cap"><span>{cap}</span>{lk}</div>\n<p class="l9big">Until 7:00</p>\n<p class="l9cnt">{cnt}</p>\n')
items.append(phone('7 · Home · locked · V3 · tap "See all"', 'nt nb nt9',
    locked("Quiet hours are on", "Leave", "3,098 Trojans in right now. One dot each.")
    + sheet("Going on now", "!See all 14", '<div class="s9list">\n' + rows(POSTS) + '\n</div>', composer(), " board9", card=False)))
items.append(phone('7b · Home · locked · opted out, or left early', 'nt nb nt9 off9',
    locked("You're out this week.", "", "3,097 Trojans in right now.")
    + sheet("Going on now", "13", '<div class="s9list">\n' + rows(POSTS[:4], mine=False) + '\n</div>', '<button class="go go9" type="button">Join until 7:00</button>\n', card=False)))
homes = "".join(items)

HL = ["41 people called a parent.", "Someone finished a painting they started in September.", "Spikeball on McCarthy Quad grew to about thirty.", "63 people took a nap.", "19 people cooked for someone else."]
hl = '<div class="hl9s">' + "\n".join(f'<p class="hl9">{x}</p>' for x in HL) + '</div>'
S3 = [("3,041", "of 3,112 stayed"), ("6,140", "hours back"), ("1,904", "reaches")]
sm = []
sm.append(phone('9 · Home · summary · V3', 'sum9',
    BAR + hero("Today, 5:00 – 7:00 PM", "", "How it went", "Quiet hours are over.", S3, " sm")
    + sheet("The hour, told back", "from 1,287 lines", hl, '<p class="s9foot">Voting for next week opens Sunday.</p>\n')))
sm.append(phone('9b · Home · summary · before the recap lands', 'sum9',
    BAR + hero("Today, 5:00 – 7:00 PM", "", "How it went", "Quiet hours are over.", S3, " sm")
    + sheet("The hour, told back", "at 7:15", '<p class="s9wait">People are still writing what they did. 1,287 lines so far.</p>', '<p class="s9foot">Voting for next week opens Sunday.</p>\n')))
sm.append(phone('9c · Home · summary · opted out', 'sum9',
    BAR + hero("You were out this week.", "", "How it went", "Quiet hours are over.", [("3,040", "of 3,111 stayed"), ("6,138", "hours back"), ("1,904", "reaches")], " sm").replace('<div class="h9top"><span>', '<div class="h9top me"><span>')
    + sheet("The hour, told back", "from 1,287 lines", hl, '<p class="s9foot">You\'re in again next week. Voting opens Sunday.</p>\n')))
summ = "".join(sm)

def esc(s): return s.replace('{', '{{').replace('}', '}}').replace('@@STARS@@', '{starsn}').replace('@@MOON@@', '{mcd}')
i = t.index('<p class="label">8 · The question'); i = t.rindex('<div class="item">', 0, i)
t = t[:i] + esc(homes) + t[i:]
i = t.index('<p class="label">8b · The question'); j = t.index(END, i) + len(END)
t = t[:j] + esc(summ) + t[j:]

CSS = '''
/* ---- Homes, V9: a hero and a sheet. Every element lives in one of the two; nothing floats loose. ---- */
.h9big.sm{font-size:50px}
.h9stats.three{grid-template-columns:1fr 1fr 1fr}
.h9stats.three > div{padding:14px 12px 16px 18px}
.h9stats.three b{font-size:27px;line-height:34px}
.h9top.me span,.out9 .h9top span,.off9 .l9cap span{color:#1C1A18;font-weight:500}
.s9note{font-size:14px;color:#8A8279}
.s9foot{position:absolute;left:26px;right:26px;bottom:34px;margin:0;font-size:13px;line-height:18px;color:#7A7269}
.s9wait{margin:10px 26px 0;font-size:16px;line-height:23px;color:#6A635B}
.go9{position:absolute;left:20px;right:20px;bottom:30px}
.td9{flex:none;border:0;background:none;padding:8px 0;color:#1C1A18;font:400 14px var(--sans);text-decoration:underline;text-underline-offset:3px;text-decoration-color:rgba(28,26,24,.35);cursor:pointer}
/* Only the board is an edge-to-edge sheet, because only it pulls up to fill the screen. Everything else that sits
   under the hero is a second card with the same margins, hugging its content. */
.sheet9.card9{left:20px;right:20px;top:382px;bottom:auto;border-radius:34px;padding-bottom:12px;background:#EFEBE5;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.95),0 16px 22px -12px rgba(70,52,36,.34),0 1px 2px rgba(70,52,36,.1)}
.card9 .s9head{padding:16px 22px 6px}
.card9 .o9{width:calc(100% - 20px);margin-left:10px;margin-right:10px}
.card9 .hl9{margin:0 22px}
.card9 .s9wait{margin:8px 22px 10px}
.out9 .sheet9.card9{border-top:0}
/* options, as rows on the sheet; the chosen one is pressed in */
.o9s{margin-top:2px}
.o9{display:block;box-sizing:border-box;width:calc(100% - 28px);margin:0 14px;padding:11px 12px 13px;border:0;border-radius:22px;background:transparent;text-align:left;font-family:var(--sans);color:#1C1A18;transition:background .2s,box-shadow .2s}
button.o9{cursor:pointer}
.o9 + .o9{margin-top:4px}
.o9.on{background:#E4DED6;box-shadow:inset 0 2px 5px rgba(70,52,36,.17),0 1px 0 rgba(255,255,255,.85)}
.o9 .r1{display:flex;justify-content:space-between;align-items:baseline;gap:12px}
.o9 .d{font-size:17px;font-weight:500}
.o9 .t{font-size:15px}
.o9 .why{display:block;margin-top:1px;font-size:14px;line-height:20px;color:#6A635B}
.o9 .r3{display:flex;align-items:center;gap:12px;margin-top:8px}
.o9 .n{font-size:12px;color:#6A635B;min-width:70px;text-align:right}
.o9:focus-visible{outline:2px solid #1C1A18;outline-offset:1px}
/* the board on the sheet: four rows at rest; the sheet pulls up to show them all */
.sheet9{transition:top .5s cubic-bezier(.2,.8,.2,1)}
.s9list{height:264px;overflow:hidden}
.board9.open{top:104px}
.board9.open .s9list{position:absolute;left:0;right:0;top:50px;bottom:104px;height:auto;overflow-y:auto;scrollbar-width:none;
  -webkit-mask-image:linear-gradient(to bottom,transparent 0,#000 26px,#000 calc(100% - 30px),transparent 100%);mask-image:linear-gradient(to bottom,transparent 0,#000 26px,#000 calc(100% - 30px),transparent 100%)}
.board9.open .s9list::-webkit-scrollbar{display:none}
.board9.open .s9list .r9:first-child{margin-top:14px}
.board9.open .s9list .r9:last-child{margin-bottom:22px}
/* the summary's highlights, as rows */
.hl9s{margin-top:2px}
.hl9{margin:0 26px;padding:12px 0 13px;border-bottom:1px solid rgba(70,52,36,.1);font-family:var(--serif);font-style:italic;font-size:22px;line-height:27px}
.hl9:last-child{border-bottom:0}
/* opted out: both parts stay but go flat and pale; one dark button is the only thing to press */
.out9 .hero,.out9 .sheet9{background:transparent;box-shadow:none}
.out9 .sheet9{border-top:1px solid rgba(70,52,36,.08)}
.out9 .h9big,.out9 .h9when,.out9 .h9stats b,.out9 .h9stats span,.out9 .s9head,.out9 .s9note,.out9 .r9 b,.out9 .r9 span,.out9 .r9 i,.out9 .o9,.out9 .o9 .why,.out9 .o9 .n{color:#ADA69C}
.out9 .h9stats,.out9 .h9stats > div + div,.out9 .r9{border-color:rgba(70,52,36,.07)}
.out9 .o9.on{background:transparent;box-shadow:none}
.out9 .o9 .track{box-shadow:none;background:rgba(28,26,24,.05)}
.out9 .o9 .track b{background:#CFC8BE}
.out9 .o9 .d{font-weight:400}
.out9 .r9 b{font-weight:400}
.out9 .s9list{height:198px}
/* locked: the night sky is the hero, the moon its object; the sheet is dark */
.s.nt9{background:#080706;color:#EAE5DE}
.nt9 .lmoon{top:92px}
.l9cap{position:absolute;left:26px;right:26px;top:344px;display:flex;justify-content:space-between;align-items:center;font-size:14px;color:#9B9289}
.l9cap button{border:0;background:none;padding:6px 0;color:#9B9289;font:400 14px var(--sans);text-decoration:underline;text-underline-offset:3px;cursor:pointer}
.l9big{position:absolute;left:24px;top:366px;margin:0;font-family:var(--serif);font-style:italic;font-size:58px;line-height:60px}
.l9cnt{position:absolute;left:26px;top:430px;margin:0;font-size:15px;color:#9B9289}
.nt9 .sheet9{top:478px;background:#151311;box-shadow:inset 0 1px 0 rgba(255,255,255,.1),0 -14px 26px -16px #000}
.nt9 .s9list{height:198px}
.nt9 .board9.open{top:104px}
.nt9 .s9head,.nt9 .s9head button,.nt9 .s9note,.nt9 .r9 span,.nt9 .r9 i{color:#9B9289}
.nt9 .r9{border-bottom-color:rgba(255,255,255,.07)}
.nt9 .td9{color:#EAE5DE;text-decoration-color:rgba(234,229,222,.4)}
.nt9 .cmp9{background:#070605;color:#8B837A;box-shadow:inset 0 2px 4px rgba(0,0,0,.85),0 1px 0 rgba(255,255,255,.07)}
.nt9 .cmp9 b{background:#EAE5DE;color:#1C1A18}
.off9 .lmoon{opacity:.2}
.off9 .stars{opacity:.6}
.off9 .l9cap span{color:#EAE5DE}
.off9 .l9big,.off9 .l9cnt,.off9 .s9head,.off9 .s9note,.off9 .r9 b,.off9 .r9 span,.off9 .r9 i{color:#5F5850}
.off9 .sheet9{background:transparent;box-shadow:none;border-top:1px solid rgba(255,255,255,.06)}
.off9 .r9{border-bottom-color:rgba(255,255,255,.04)}
.off9 .r9 b{font-weight:400}
.off9 .s9list{height:132px}
.off9 .go9{background:#EAE5DE;color:#1C1A18;box-shadow:inset 0 1px 0 rgba(255,255,255,.6),0 14px 20px -10px #000}
@media (prefers-reduced-motion: reduce){.sheet9,.o9{transition:none}}
'''.replace('{', '{{').replace('}', '}}')
a = '/* Home, selected: the time itself is the subject. */'; assert a in t
t = t.replace(a, CSS + a)

JS = '''  // Homes, V9: choosing a window, and pulling the board's sheet up and down.
  Array.prototype.forEach.call(document.querySelectorAll("button.o9"), function (b) {
    b.addEventListener("click", function () {
      Array.prototype.forEach.call(b.parentNode.querySelectorAll(".o9"), function (o) { o.classList.toggle("on", o === b); });
    });
  });
  Array.prototype.forEach.call(document.querySelectorAll(".board9"), function (sh) {
    var more = sh.querySelector(".s9more"), list = sh.querySelector(".s9list"), label = more.textContent;
    more.addEventListener("click", function () {
      var open = sh.classList.toggle("open");
      more.textContent = open ? "Close" : label;
      if (!open) list.scrollTop = 0;
    });
  });
'''
a = '  var lk = document.getElementById("lkc");'; assert a in t
t = t.replace(a, JS + a)
open('build_screens.py', 'w').write(t)
print('ok')
