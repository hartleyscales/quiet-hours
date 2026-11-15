import bpy, numpy as np, sys
def load(p):
    im = bpy.data.images.load(p); im.colorspace_settings.name='Non-Color'
    w,h = im.size; a = np.empty(w*h*4, dtype=np.float32); im.pixels.foreach_get(a)
    return a.reshape(h,w,4)[::-1]  # top-down
S='/Users/hartleyscales/quiet-hours/submission/screens/'
v = load(S+'vote.png'); L = v[...,:3].mean(-1)
print('vote size', v.shape, 'bg', (v[300,100,:3]*255).round(1))
dark = L < 0.45
def bbox(m, y0,y1,x0=0,x1=None):
    sub = m[y0:y1, x0:x1]; ys,xs = np.nonzero(sub)
    return (xs.min()+x0, ys.min()+y0, xs.max()+x0, ys.max()+y0)
print('clock bbox', bbox(dark, 400, 1300))
print('headline bbox', bbox(dark, 1350, 1600)); print('sub bbox', bbox(L<0.6, 1610, 1700))
# pills: row profile at x=603 and column profile
col = L[:,603]; 
for y in range(1800,2560,4): pass
# pill edges: use brightness > bg
bgL = L[300,100]
print('bgL', bgL, 'pill face', (v[1950,603,:3]*255).round(1), (v[2160,603,:3]*255).round(1))
row = L[1945]; xs = np.nonzero(row > bgL+0.012)[0]; print('pill x extent', xs.min(), xs.max())
for name,(a,b) in {'p1':(1800,2060),'p2':(2040,2270),'p3':(2260,2520)}.items():
    c = L[a:b,603]; ys = np.nonzero(c > bgL+0.012)[0]; print(name,'y extent', ys.min()+a, ys.max()+a)
# gear
g = L[100:340, 950:1206]; ys,xs = np.nonzero(g > bgL+0.012); print('gear', xs.min()+950, xs.max()+950, ys.min()+100, ys.max()+100)
# text in pills
print('thu label', bbox(dark, 1880,2010, 100, 600), 'thu time', bbox(L<0.6, 1880,2010, 600, 1130))
k = load(S+'locked.png'); KL = k[...,:3].mean(-1)
print('locked bg', (k[2000,300,:3]*255).round(1), (k[60,600,:3]*255).round(1))
# moon: dense region
m = KL > 0.25
rows = m[:, :].sum(1); 
ys = np.nonzero(rows > 40)[0]; print('bright rows ranges', ys.min(), ys.max())
print('moon bbox approx', bbox(m, 580, 1350, 200, 1000))
print('until bbox', bbox(KL>0.5, 1380,1620,150,1050)); print('trojans bbox', bbox(KL>0.3,1630,1710,300,900))
prow = KL[2380]; print('pill row sample', (k[2380,603,:3]*255).round(1), (k[2380,90,:3]*255).round(1),(k[2380,30,:3]*255).round(1))
for x in range(40,140,6): print(x, (k[2380,x,:3]*255).round(0), end=' | ')
print()
for y in range(2260,2500,8): print(y, (k[y,300,:3]*255).round(0), end=' | ')
print()
st = load('/Users/hartleyscales/quiet-hours/web/assets/stars_quiet.png'); print('stars', st.shape, st[...,3].min(), st[...,3].max(), st[...,:3].max())
