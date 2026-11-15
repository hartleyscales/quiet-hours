"""Builds design/homes-quiet.html: every Home in the quiet form, from the approved mock's own styles and art."""
import base64, os
S = os.path.dirname(os.path.abspath(__file__))
src = open('screens.html').read().split('\n')
head = ['<meta charset="utf-8">'] + [l.replace('<title>Quiet Hours Screens</title>', '<title>Quieter Homes</title>') for l in src[0:397]]
art = next(l for l in src[399:416] if l.startswith('<img class="art"'))
it7 = src[584:615]
moon = next(l for l in it7 if l.startswith('<img class="lmoon"'))
rows = [l for l in it7 if l.startswith('<div class="r9">')]
cmp9 = next(l for l in it7 if l.startswith('<div class="cmp9">'))
stars = '<img class="stars" src="data:image/png;base64,' + base64.b64encode(open(S + '/stars_quiet.png', 'rb').read()).decode() + '" alt="">'
draw = src[728:833]            # <script>, the IIFE's opening, the moon data, the shapes, M8 and fill
assert draw[0].strip() == '<script>' and draw[-1].strip() == '}', (draw[0], draw[-1])
gear = '<div class="bar"><button class="gear" type="button" aria-label="Settings"><svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/></svg></button></div>'
RAISED = 'inset 0 1px 0 rgba(255,255,255,.9),0 12px 18px -10px rgba(70,52,36,.4),0 1px 2px rgba(70,52,36,.12)'
css = '''
/* Quieter Homes (November 14): every Home is built like the intro screens. One picture, one statement, one grey line, one thing to do.
   The board is its own screen, one tap away. Opting out and leaving live behind the gear. */
.s.hm.q .bar{justify-content:flex-end}
.q canvas.pic{position:absolute;left:0;top:74px;width:390px;height:340px;display:block}
.q .art{top:49px}
.qbig{position:absolute;left:0;right:0;top:452px;margin:0;padding:0 28px;text-align:center;font-family:var(--serif);font-style:italic;font-weight:400;font-size:64px;line-height:68px}
.qsub{position:absolute;left:0;right:0;top:524px;margin:0;text-align:center;font-size:24px;line-height:30px}
.qline{position:absolute;left:0;right:0;top:564px;margin:0;padding:0 44px;text-align:center;font-size:15px;line-height:21px;color:#6A635B}
.qrow{position:absolute;left:24px;right:24px;bottom:46px;height:58px;border:0;border-radius:29px;background:#EFEBE5;color:#1C1A18;font:500 16px var(--sans);cursor:pointer;box-shadow:RAISED}
.qgo{position:absolute;left:24px;right:24px;bottom:46px;height:58px;border:0;border-radius:29px;background:#1C1A18;color:#F3EFE9;font:500 17px var(--sans);cursor:pointer;box-shadow:inset 0 1px 0 rgba(255,255,255,.16),0 14px 20px -10px rgba(28,26,24,.5)}
.qrow:focus-visible,.qopt:focus-visible{outline:2px solid #1C1A18;outline-offset:3px}
/* voting: the three choices are the screen */
.qv .qbig{padding:0 8px;font-size:54px;line-height:60px}
.qv .qline{top:522px}
.qopts{position:absolute;left:24px;right:24px;bottom:46px;display:flex;flex-direction:column;gap:12px}
.qopt{position:relative;height:58px;border:0;border-radius:29px;padding:0 24px;display:flex;align-items:center;justify-content:space-between;background:#EFEBE5;color:#1C1A18;font:500 17px var(--sans);cursor:pointer;overflow:hidden;box-shadow:RAISED;transition:background .2s,box-shadow .2s}
.qopt b{position:relative;font-weight:500}
.qopt i{position:relative;font-style:normal;font-weight:400;font-size:16px;color:#6A635B}
.qopt::before{content:"";position:absolute;left:0;top:0;bottom:0;width:0;background:rgba(28,26,24,.075);transition:width .6s cubic-bezier(.2,.8,.2,1)}
.voted .qopt::before{width:var(--w)}
.qopt.on{background:#E2DCD4;box-shadow:inset 0 2px 5px rgba(70,52,36,.18),0 1px 0 rgba(255,255,255,.8)}
/* summary: one thing people did, at a time */
.qs .qbig{top:432px;height:132px;display:flex;align-items:center;justify-content:center;font-size:38px;line-height:44px;transition:opacity .45s}
.qpips{position:absolute;left:0;right:0;top:580px;display:flex;justify-content:center;gap:8px}
.qpips i{width:7px;height:7px;border-radius:50%;background:#D5CEC5;transition:background .3s}
.qpips i.on{background:#1C1A18}
.qs .qline{top:606px}
/* out this week: the same screen, pale, with the one way back in */
.qout .art{opacity:.3}
.qout .qbig,.qout .qsub{color:#A9A299}
.qout .qline{color:#1C1A18}
/* locked: night */
.q.nt9 .lmoon{top:192px}
.q.nt9 .qbig{top:452px}
.q.nt9 .qline{top:528px;color:#9B9289}
.q.nt9 .qrow{background:#161412;color:#EAE5DE;box-shadow:inset 0 1px 0 rgba(255,255,255,.1),0 12px 16px -9px #000,0 0 0 1px rgba(255,255,255,.025)}
.q.nt9 .qrow:focus-visible{outline-color:#EAE5DE}
.qout.nt9 .lmoon{opacity:.22}
.qout.nt9 .stars{opacity:.55}
.qout.nt9 .qbig{color:#6B645C}
.qout.nt9 .qline{color:#EAE5DE}
.q.nt9 .golight{position:absolute;left:24px;right:24px;bottom:46px;height:58px;border:0;border-radius:29px;background:#EAE5DE;color:#1C1A18;font:500 17px var(--sans);cursor:pointer;box-shadow:inset 0 1px 0 rgba(255,255,255,.6),0 14px 20px -10px #000}
/* the board, as its own screen */
.qb .board9.open{top:0;border-radius:0;box-shadow:none;background:#0C0B0A}
.qb .s9head{padding:70px 26px 8px;align-items:baseline}
.qb .s9x{position:absolute;right:24px;top:70px;width:42px;height:42px;border-radius:50%;border:0;padding:0;background:#161412;color:#EAE5DE;display:grid;place-items:center;cursor:pointer;z-index:6;text-decoration:none;box-shadow:inset 0 1px 0 rgba(255,255,255,.1),0 12px 16px -9px #000,0 0 0 1px rgba(255,255,255,.025)}
.qb .s9x:focus-visible{outline:2px solid currentColor;outline-offset:2px}
.qb .s9head span{font-family:var(--serif);font-style:italic;font-size:38px;line-height:42px;color:#EAE5DE}
.qb .board9.open .s9list{top:128px}
/* settings: a sheet over whichever Home you were on, not a screen of its own. Four rows: this week, what stays open, how it works, the account. */
.qdim{position:absolute;inset:0;background:rgba(234,229,222,.62)}
.qset{position:absolute;left:0;right:0;bottom:0;border-radius:38px 38px 0 0;background:#F4F1EC;padding:10px 0 26px;box-shadow:inset 0 1px 0 rgba(255,255,255,.9),0 -18px 40px -18px rgba(70,52,36,.38)}
.qset::before{content:"";display:block;width:36px;height:4px;border-radius:2px;margin:0 auto 6px;background:rgba(28,26,24,.16)}
.qset button{display:flex;align-items:center;justify-content:space-between;gap:14px;width:calc(100% - 52px);margin:0 26px;height:64px;padding:0;border:0;border-bottom:1px solid rgba(70,52,36,.1);background:none;color:#1C1A18;font-family:var(--sans);text-align:left;cursor:pointer}
.qset button:last-child{border-bottom:0}
.qset b{display:block;font-size:16px;font-weight:500;line-height:22px}
.qset span{display:block;font-size:14px;line-height:20px;color:#6A635B}
.qset svg{flex:none;color:#8A8279}
.qset button:focus-visible{outline:2px solid #1C1A18;outline-offset:-2px;border-radius:12px}
.nt9 .qdim{background:rgba(8,7,6,.66)}
.nt9 .qset{background:#151311;box-shadow:inset 0 1px 0 rgba(255,255,255,.1),0 -18px 40px -18px #000}
.nt9 .qset::before{background:rgba(234,229,222,.2)}
.nt9 .qset button{color:#EAE5DE;border-bottom-color:rgba(255,255,255,.07)}
.nt9 .qset span,.nt9 .qset svg{color:#9B9289}
.nt9 .qset button:focus-visible{outline-color:#EAE5DE}
@media (prefers-reduced-motion: reduce){.qopt::before,.qs .qbig,.qv .qline{transition:none}}
'''.replace('RAISED', RAISED)
i = max(k for k, l in enumerate(head) if l.strip() == '</style>')
head[i:i] = css.strip('\n').split('\n')

def phone(label, cls, inner):
    return ['<div class="item">', '<p class="label">' + label + '</p>', '<div class="phone"><div class="s hm v9 q ' + cls + '">'] + inner + ['</div></div>', '</div>']
opts = ('<div class="qopts">'
        '<button class="qopt" type="button" style="--w:47%" data-why="Most classes are out. Sunset is at 4:48."><b>Thursday</b><i>5:00 – 7:00 PM</i></button>'
        '<button class="qopt" type="button" style="--w:34%" data-why="No home game, and the week hasn\'t begun."><b>Sunday</b><i>4:00 – 5:30 PM</i></button>'
        '<button class="qopt" type="button" style="--w:20%" data-why="Lunch, when most people are on campus."><b>Wednesday</b><i>12:00 – 1:00 PM</i></button></div>')
voted = opts.replace('<button class="qopt" type="button" style="--w:47%"', '<button class="qopt on" type="button" style="--w:47%"')
pips = '<div class="qpips"><i class="on"></i><i></i><i></i><i></i><i></i></div>'
items = []
items += phone('4 · Voting · tap a choice', 'qv', [gear, '<canvas class="pic" id="pv1" width="1170" height="1020" aria-hidden="true"></canvas>', '<h2 class="qbig">When this week?</h2>', '<p class="qline" data-rest="Closes Tuesday, 8:00 PM">Closes Tuesday, 8:00 PM</p>', opts])
items += phone('4 · Voting · after you vote', 'qv voted', [gear, '<canvas class="pic" id="pv2" width="1170" height="1020" aria-hidden="true"></canvas>', '<h2 class="qbig">When this week?</h2>', '<p class="qline">Most classes are out. Sunset is at 4:48.</p>', voted])
items += phone('5 · Decided', '', [gear, art, '<h2 class="qbig">Thursday</h2>', '<p class="qsub">5:00 – 7:00 PM</p>', '<p class="qline">In 1 day, 20 hours. 3,112 Trojans in.</p>'])
items += phone('5b · Decided · out this week', 'qout', [gear, art, '<h2 class="qbig">Thursday</h2>', '<p class="qsub">5:00 – 7:00 PM</p>', '<p class="qline">You\'re out this week.</p>', '<button class="qgo" type="button">Opt back in</button>'])
items += phone('6 · The day', '', [gear, art, '<h2 class="qbig">Today</h2>', '<p class="qsub">5:00 – 7:00 PM</p>', '<p class="qline">In 3 hours, 12 minutes. 3,112 Trojans in.</p>', '<button class="qrow" type="button">14 things going on</button>'])
items += phone('7 · Locked', 'nt nb nt9', [stars, gear, moon, '<h2 class="qbig">Until 7:00</h2>', '<p class="qline">3,098 Trojans in</p>', '<button class="qrow" type="button">14 things going on</button>'])
items += phone('7b · Locked · out, or left early', 'nt nb nt9 qout', [stars, gear, moon, '<h2 class="qbig">Until 7:00</h2>', '<p class="qline">You\'re out. 3,098 Trojans in.</p>', '<button class="golight" type="button">Join until 7:00</button>'])
items += phone('The board · one tap from The day and Locked', 'nt nb nt9 qb', ['<div class="sheet9 board9 open">', '<div class="s9head"><span>Going on now</span></div><button type="button" class="s9more s9x" aria-label="Close"><svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg></button>', '<div class="s9list">'] + rows + ['</div>', cmp9, '</div>'])
items += phone('9b · Summary · before it comes back', 'qs', [gear, '<canvas class="pic" id="ps1" width="1170" height="1020" aria-hidden="true"></canvas>', '<h2 class="qbig" style="font-size:52px;line-height:56px">Quiet hours are over.</h2>', '<p class="qline" style="top:584px">People are still writing. Back at 7:15.</p>'])
items += phone('9 · Summary · one at a time', 'qs', [gear, '<canvas class="pic" id="ps2" width="1170" height="1020" aria-hidden="true"></canvas>', '<h2 class="qbig" id="hl">41 people called a parent.</h2>', pips, '<p class="qline">3,041 of 3,112 stayed.</p>'])
chev = '<svg width="9" height="16" viewBox="0 0 9 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M1 1l7 7-7 7"/></svg>'
def sheet(first, firstsub):
    return ['<div class="qdim"></div>', '<div class="qset">',
            '<button type="button"><div><b>' + first + '</b><span>' + firstsub + '</span></div></button>',
            '<button type="button"><div><b>What stays open</b><span>Phone, Messages, Maps and 3 more</span></div>' + chev + '</button>',
            '<button type="button"><div><b>How it works</b></div>' + chev + '</button>',
            '<button type="button"><div><b>Sign out</b><span>ttrojan@usc.edu</span></div></button>', '</div>']
items += phone('Settings · behind the gear, over Decided', '', [gear, art, '<h2 class="qbig">Thursday</h2>', '<p class="qsub">5:00 – 7:00 PM</p>', '<p class="qline">In 1 day, 20 hours. 3,112 Trojans in.</p>'] + sheet('Opt out of this week', 'Thursday, 5:00 – 7:00 PM'))
items += phone('Settings · when you are out', 'qout', [gear, art, '<h2 class="qbig">Thursday</h2>', '<p class="qsub">5:00 – 7:00 PM</p>', '<p class="qline">You\'re out this week.</p>'] + sheet('Opt back in', 'Thursday, 5:00 – 7:00 PM'))
items += phone('Settings · during quiet hours', 'nt nb nt9', [stars, gear, moon, '<h2 class="qbig">Until 7:00</h2>', '<p class="qline">3,098 Trojans in</p>'] + sheet('Leave quiet hours', 'They run until 7:00'))
js = '''
  function still(id, fn, scale, cx, cy) {
    var c = document.getElementById(id); if (!c) return;
    var g = c.getContext("2d"), cols = Math.floor(c.width / 6), rws = Math.floor(c.height / 6);
    g.fillStyle = "#3A342E";
    for (var j = 0; j < rws; j++) for (var i2 = 0; i2 < cols; i2++) {
      var x = i2 * 2 + 1, y = j * 2 + 1, d = fn(195 + (x - cx) / scale, 224 + (y - cy) / scale);
      if (d > 0 && (M8[j & 7][i2 & 7] + 0.5) / 64 < d) g.fillRect((x - 0.67) * 3, (y - 0.67) * 3, 4, 4);
    }
  }
  still("pv1", clock, 0.8, 195, 196); still("pv2", clock, 0.8, 195, 196);
  still("ps1", bubble, 0.8, 195, 196); still("ps2", bubble, 0.8, 195, 196);
  // voting: a tap chooses, the choice presses in, the tallies fill, and the grey line gives that choice's reason
  Array.prototype.forEach.call(document.querySelectorAll(".qv"), function (scr) {
    var line = scr.querySelector(".qline");
    Array.prototype.forEach.call(scr.querySelectorAll(".qopt"), function (b) {
      b.addEventListener("click", function () {
        Array.prototype.forEach.call(scr.querySelectorAll(".qopt"), function (o) { o.classList.toggle("on", o === b); });
        scr.classList.add("voted"); line.textContent = b.getAttribute("data-why");
      });
    });
  });
  // summary: the five things, one at a time
  var hl = document.getElementById("hl"), said = ["41 people called a parent.", "Someone finished a painting they started in September.", "Spikeball on McCarthy Quad grew to about thirty.", "63 people took a nap.", "19 people cooked for someone else."], at = 0;
  var dots = hl.parentNode.querySelectorAll(".qpips i");
  function show(k) { at = (k + said.length) % said.length; hl.style.opacity = 0; setTimeout(function () { hl.textContent = said[at]; hl.style.opacity = 1; for (var d = 0; d < dots.length; d++) dots[d].classList.toggle("on", d === at); }, 420); }
  var still2 = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var timer = still2 ? 0 : setInterval(function () { show(at + 1); }, 3800);
  hl.parentNode.addEventListener("click", function () { clearInterval(timer); show(at + 1); });
})();
</script>
'''
open('homes-quiet.html', 'w').write('\n'.join(head + ['', '<div class="wrap">'] + items + ['</div>', ''] + draw + js.strip('\n').split('\n')))
print('written', os.path.getsize('homes-quiet.html'))
