import sys, random, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter
F='fonts/'; W,H=1640,856
def lerp(a,b,t): return tuple(int(a[i]+(b[i]-a[i])*t) for i in range(3))
CFG={
 'birds':dict(g=[(0,150,136),(34,90,160),(255,120,60)],blobs=[(255,210,0,140),(0,230,120,120),(255,70,90,130),(80,180,255,130)],
   big='BIRDS',script='of the World',sub='Nature Documentaries',ribbon='COLORS  •  SOUNDS  •  HABITATS  •  FACTS',
   face=[(0,200,120),(0,170,255),(255,200,0),(255,90,60)],side=(10,40,60),order=['p1','p0','p3','p4','p6','p7'],logo='p0',
   panel=(240,255,250,235),outline=(0,170,140),subc=(20,70,90),rb=[(0,170,140),(0,130,220),(255,120,60)]),
 'pets':dict(g=[(255,140,100),(240,90,150),(90,140,240)],blobs=[(255,220,120,140),(120,230,255,120),(255,120,200,130),(170,120,255,130)],
   big='DOGS & CATS',script='World',sub='Cute  •  Funny  •  Lovable',ribbon='PUPPIES  •  KITTENS  •  BREEDS  •  CARE TIPS',
   face=[(255,90,120),(255,150,0),(255,210,0),(255,90,120)],side=(90,20,50),order=['p0','p1','p4','p3','p2','p5'],logo='p0',
   panel=(255,245,240,235),outline=(255,90,140),subc=(110,40,80),rb=[(170,90,255),(255,90,140),(255,150,0)]),
}
name=sys.argv[1]; C=CFG[name]; D=f'docs/brand/{name}/'
def grad(w,h,cols,diag=True):
    im=Image.new('RGB',(w,h)); px=im.load()
    for y in range(h):
        for x in range(w):
            t=(x/w*0.7+y/h*0.3) if diag else y/h
            n=len(cols)-1; i=min(int(t*n),n-1); px[x,y]=lerp(cols[i],cols[i+1],t*n-i)
    return im
def blobs(img,pts):
    b=Image.new('RGBA',img.size,(0,0,0,0)); bd=ImageDraw.Draw(b)
    for x,y,r,c in pts: bd.ellipse([x-r,y-r,x+r,y+r],fill=c)
    return Image.alpha_composite(img.convert('RGBA'),b.filter(ImageFilter.GaussianBlur(img.size[0]//14)))
def star(d,x,y,r,c):
    d.polygon([(x+math.cos(i*math.pi/4)*(r if i%2==0 else r*.28),y+math.sin(i*math.pi/4)*(r if i%2==0 else r*.28)) for i in range(8)],fill=c)
def text3d(bg,xy,t,f,depth,side,face):
    d=ImageDraw.Draw(bg)
    for i in range(depth,0,-1): d.text((xy[0]+i*.6,xy[1]+i),t,font=f,fill=side,anchor='ms')
    m=Image.new('L',bg.size,0); ImageDraw.Draw(m).text(xy,t,font=f,fill=255,anchor='ms'); bb=m.getbbox()
    gr=Image.new('RGB',bg.size); g=ImageDraw.Draw(gr)
    for x in range(bb[0],bb[2]+1):
        tt=(x-bb[0])/max(1,bb[2]-bb[0])*(len(face)-1); i=min(int(tt),len(face)-2); g.line([(x,bb[1]),(x,bb[3])],fill=lerp(face[i],face[i+1],tt-i))
    bg.paste(gr,(0,0),m)
rainbow=[(255,60,172),(255,179,0),(0,212,180),(43,134,197),(166,75,255),(255,60,172)]
def card(bg,fn,cx,cy,w,h,rot):
    im=Image.open(fn).convert('RGB').resize((w,h)); bw=10
    fr=Image.new('RGBA',(w+2*bw,h+2*bw)); fd=ImageDraw.Draw(fr)
    for yy in range(h+2*bw):
        t=yy/(h+2*bw)*(len(rainbow)-1); i=min(int(t),len(rainbow)-2); fd.line([(0,yy),(w+2*bw,yy)],fill=lerp(rainbow[i],rainbow[i+1],t-i)+(255,))
    m=Image.new('L',fr.size,0); ImageDraw.Draw(m).rounded_rectangle([0,0,fr.size[0]-1,fr.size[1]-1],28,fill=255)
    m2=Image.new('L',(w,h),0); ImageDraw.Draw(m2).rounded_rectangle([0,0,w-1,h-1],20,fill=255); fr.paste(im,(bw,bw),m2)
    fr.putalpha(m); fr=fr.rotate(rot,expand=True,resample=Image.BICUBIC)
    bg.alpha_composite(fr,(int(cx-fr.size[0]/2),int(cy-fr.size[1]/2)))
def font(fn,sz,wt=None):
    f=ImageFont.truetype(F+fn,sz)
    if wt:
        try: f.set_variation_by_axes([wt])
        except Exception: pass
    return f
# ---------- COVER ----------
bg=blobs(grad(W,H,C['g']),[(250,180,330,C['blobs'][0]),(1420,700,380,C['blobs'][1]),(1400,100,260,C['blobs'][2]),(180,760,300,C['blobs'][3])])
d=ImageDraw.Draw(bg); random.seed(5)
for _ in range(45):
    sx,sy=random.randint(0,W),random.randint(0,H)
    if 560<sx<1080 and 230<sy<660: continue
    star(d,sx,sy,random.randint(5,16),(255,255,255,random.randint(70,170)))
o=C['order']
for fn,cx,cy,rot in [(o[0],150,450,6),(o[1],330,420,-4),(o[2],500,460,3),(o[3],1140,460,-3),(o[4],1310,420,4),(o[5],1490,450,-6)]:
    card(bg,D+fn+'.jpg',cx,cy,190,254,rot)
sh=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(sh).rounded_rectangle([580,262,1060,656],50,fill=(20,0,30,140)); bg=Image.alpha_composite(bg,sh.filter(ImageFilter.GaussianBlur(20)))
gl=Image.new('RGBA',(W,H),(0,0,0,0)); ImageDraw.Draw(gl).rounded_rectangle([580,250,1060,640],50,fill=C['panel']); bg=Image.alpha_composite(bg,gl)
d=ImageDraw.Draw(bg); d.rounded_rectangle([580,250,1060,640],50,outline=C['outline'],width=8)
big=C['big']; bf=font('Cinzel.ttf',100 if len(big)<7 else 52,900)
text3d(bg,(822,390),big,bf,12,C['side'],C['face'])
text3d(bg,(820,505),C['script'],font('GreatVibes.ttf',110),8,C['side'],C['face'][::-1])
d=ImageDraw.Draw(bg); d.text((820,590),C['sub'],font=font('PlayfairDisplay-Italic.ttf',36,700),fill=C['subc'],anchor='ms')
for x,y,r,c in [(1010,300,24,(255,208,0)),(630,320,18,(255,60,172)),(1015,600,15,(0,212,180))]: star(d,x,y,r,c)
rb=Image.new('RGBA',(W,H)); rd=ImageDraw.Draw(rb); c=C['rb']
for x in range(430,1211):
    t=(x-430)/780; rd.line([(x,690),(x,760)],fill=(lerp(c[0],c[1],t*2) if t<.5 else lerp(c[1],c[2],(t-.5)*2))+(255,))
m=Image.new('L',(W,H),0); ImageDraw.Draw(m).rounded_rectangle([430,690,1210,760],35,fill=255); rb.putalpha(m); bg.alpha_composite(rb)
ImageDraw.Draw(bg).text((820,736),C['ribbon'],font=font('NotoSans-Bold.ttf',28),fill='white',anchor='ms')
bg.convert('RGB').save(f'docs/brand/{name}_cover.jpg',quality=88)
# ---------- LOGO ----------
S=1024; lg=blobs(grad(S,S,C['g']),[(200,200,300,C['blobs'][0]),(820,820,320,C['blobs'][1])])
ring=Image.new('RGBA',(S,S)); rd=ImageDraw.Draw(ring)
for a in range(360):
    t=a/360*(len(rainbow)-1); i=min(int(t),len(rainbow)-2); rd.pieslice([92,72,932,912],a-90,a-89+1.5,fill=lerp(rainbow[i],rainbow[i+1],t-i)+(255,))
sh=Image.new('RGBA',(S,S)); ImageDraw.Draw(sh).ellipse([100,100,940,940],fill=(0,0,0,150)); lg=Image.alpha_composite(lg,sh.filter(ImageFilter.GaussianBlur(25)))
lg=Image.alpha_composite(lg,ring)
ph=Image.open(D+C['logo']+'.jpg').convert('RGB'); pw=800; ph=ph.resize((pw,int(ph.size[1]*pw/ph.size[0]))).crop((0,40,pw,40+pw))
mk=Image.new('L',(pw,pw),0); ImageDraw.Draw(mk).ellipse([0,0,pw-1,pw-1],fill=255); lg.paste(ph,(112,92),mk)
gloss=Image.new('RGBA',(S,S)); ImageDraw.Draw(gloss).ellipse([180,110,840,470],fill=(255,255,255,55)); lg=Image.alpha_composite(lg,gloss.filter(ImageFilter.GaussianBlur(30)))
rb=Image.new('RGBA',(S,S)); rd=ImageDraw.Draw(rb)
for x in range(140,885):
    t=(x-140)/745; rd.line([(x,700),(x,820)],fill=(lerp(c[0],c[1],t*2) if t<.5 else lerp(c[1],c[2],(t-.5)*2))+(255,))
m=Image.new('L',(S,S),0); ImageDraw.Draw(m).rounded_rectangle([140,700,884,820],60,fill=255); rb.putalpha(m)
sh=Image.new('RGBA',(S,S)); sh.putalpha(m.filter(ImageFilter.GaussianBlur(18)).point(lambda v:int(v*.5))); lg.alpha_composite(sh,(0,12)); lg.alpha_composite(rb)
lt='BIRDS OF THE WORLD' if name=='birds' else 'DOGS & CATS WORLD'
lf=font('Cinzel.ttf',46,900)
text3d(lg,(512,778),lt,lf,6,(40,10,40),[(255,255,255),(255,240,180),(255,255,255)])
BUB={'birds':['p1','p4','p5'],'pets':['p1','p3','p2']}[name]
for fn,(bx,by),br in zip(BUB,[(235,290),(789,290),(800,590)],[108,108,92]):
    ph=Image.open(D+fn+'.jpg').convert('RGB'); w=2*br; ph=ph.resize((w,int(ph.size[1]*w/ph.size[0]))); ph=ph.crop((0,int(w*0.12),w,int(w*0.12)+w))
    rg=Image.new('RGBA',(S,S)); rgd=ImageDraw.Draw(rg)
    for a in range(0,360,2):
        t=a/360*(len(rainbow)-1); i=min(int(t),len(rainbow)-2); rgd.pieslice([bx-br-14,by-br-14,bx+br+14,by+br+14],a,a+3,fill=lerp(rainbow[i],rainbow[i+1],t-i)+(255,))
    shd=Image.new('RGBA',(S,S)); ImageDraw.Draw(shd).ellipse([bx-br-14,by-br-4,bx+br+14,by+br+24],fill=(0,0,0,140)); lg=Image.alpha_composite(lg,shd.filter(ImageFilter.GaussianBlur(10)))
    lg=Image.alpha_composite(lg,rg); mk=Image.new('L',(w,w),0); ImageDraw.Draw(mk).ellipse([0,0,w-1,w-1],fill=255); lg.paste(ph,(bx-br,by-br),mk)
    gl=Image.new('RGBA',(S,S)); ImageDraw.Draw(gl).ellipse([bx-br*0.7,by-br*0.9,bx+br*0.7,by-br*0.1],fill=(255,255,255,50)); lg=Image.alpha_composite(lg,gl.filter(ImageFilter.GaussianBlur(8)))
lg.alpha_composite(sh,(0,12)) if False else None
lg.alpha_composite(rb)
text3d(lg,(512,778),lt,lf,6,(40,10,40),[(255,255,255),(255,240,180),(255,255,255)])
d=ImageDraw.Draw(lg)
for x,y,r,cc in [(720,150,30,(255,215,0)),(250,560,24,(255,255,255)),(640,880,18,(255,255,255))]: star(d,x,y,r,cc)
lg.convert('RGB').save(f'docs/brand/{name}_logo.jpg',quality=90)
print('done',name)
