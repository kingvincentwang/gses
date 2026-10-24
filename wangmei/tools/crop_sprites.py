"""從角色設定圖裁切《望梅止渴》動畫所需角色並去背，輸出 assets/*.png 與 assets/meta.js（含嘴巴位置）。
用法：python3 crop_sprites.py <角色設定圖> [預覽圖輸出路徑]
"""
import numpy as np, json
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage
import sys, os
SRC=sys.argv[1]  # 上傳的角色設定圖（1536x1024）
OUT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','assets')+'/'
im=Image.open(SRC).convert('RGB')
# erase labels that intrude into crop boxes
d=ImageDraw.Draw(im); BGC=(237,229,220)
d.rectangle((22,62,102,256),fill=BGC)
ERASE={'caocao_horse':[(498,262,560,650)],'soldier_a':[(495,170,540,258)],'soldier_c':[(1088,345,1100,564)],'soldier_d':[(1075,296,1092,560)]}
base=im
# name: (box, mouth in full-image coords or None)
S={
 'caocao_horse':((5,8,545,650),(268,168,30)),
 'soldier_a':((500,178,722,564),(647,290,26)),
 'soldier_b':((728,198,940,564),(860,327,40)),
 'soldier_c':((938,45,1098,564),(1020,298,24)),
 'soldier_d':((1075,296,1287,564),(1200,438,30)),
 'soldier_horse':((1280,160,1536,564),(1377,285,26)),
 'caocao_face':((455,676,635,925),(548,848,32)),
 'caocao_front':((12,678,184,938),(103,741,14)),
 'soldier_front':((682,696,795,935),(737,782,12)),
 'soldier_side':((800,696,885,935),None),
 'soldier_back':((900,696,1015,935),None),
 'face_happy':((1060,700,1165,895),(1129,800,30)),
 'face_shock':((1165,700,1270,895),(1230,825,22)),
 'face_tired':((1275,700,1385,895),(1348,836,26)),
 'face_tongue':((1390,760,1510,930),(1462,842,30)),
}
BG=np.array([237,229,220],float)
meta={}
for name,(box,mouth) in S.items():
    im=base.copy(); dd=ImageDraw.Draw(im)
    for r in ERASE.get(name,[]): dd.rectangle(r,fill=BGC)
    c=np.asarray(im.crop(box)).astype(float)
    # local background estimate = median of border pixels
    border=np.concatenate([c[0],c[-1],c[:,0],c[:,-1]])
    bg=np.median(border,axis=0)
    dist=np.sqrt(((c-bg)**2).sum(-1))
    cand=dist<26
    lab,n=ndimage.label(cand)
    edge=set(np.unique(np.concatenate([lab[0],lab[-1],lab[:,0],lab[:,-1]])))-{0}
    bgmask=np.isin(lab,list(edge))
    # also remove ground-shadow greys near bottom: low saturation, light
    sat=c.max(-1)-c.min(-1); light=c.mean(-1)
    shadow=(sat<30)&(light>140)
    hh=c.shape[0]; low=np.zeros_like(shadow); low[int(hh*.85):]=True
    shadow|=low&(sat<55)&(light>165)
    lab2,_=ndimage.label(shadow|bgmask)
    e2=set(np.unique(np.concatenate([lab2[0],lab2[-1],lab2[:,0],lab2[:,-1]])))-{0}
    bgmask=bgmask|(np.isin(lab2,list(e2))&shadow)
    fg=~bgmask
    fg=ndimage.binary_opening(fg,iterations=1)
    lab3,n3=ndimage.label(fg)
    if n3>1:
        sizes=ndimage.sum(fg,lab3,range(1,n3+1)); keep=[i+1 for i,s in enumerate(sizes) if s>0.02*sizes.max()]
        fg=np.isin(lab3,keep)
    a=Image.fromarray((fg*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.8))
    rgba=im.crop(box).convert('RGBA'); rgba.putalpha(a)
    bb=rgba.getbbox(); rgba=rgba.crop(bb)
    rgba.save(OUT+name+'.png',optimize=True)
    m=None
    if mouth: m=[mouth[0]-box[0]-bb[0],mouth[1]-box[1]-bb[1],mouth[2]]
    meta[name]={'w':rgba.width,'h':rgba.height,'mouth':m}
open(OUT+'meta.js','w').write('window.SPRITES = '+json.dumps(meta)+';\n')
print(json.dumps(meta))
# contact sheet on dark bg to check matting
sheet=Image.new('RGB',(1600,900),(40,90,60)); x=y=0; rh=0
for name in S:
    p=Image.open(OUT+name+'.png')
    if x+p.width>1600: x=0; y+=rh+5; rh=0
    sheet.paste(p,(x,y),p); 
    if meta[name]['mouth']: 
        mx,my,_=meta[name]['mouth']; ImageDraw.Draw(sheet).ellipse((x+mx-3,y+my-3,x+mx+3,y+my+3),fill=(255,0,0))
    x+=p.width+5; rh=max(rh,p.height)
if len(sys.argv)>2: sheet.save(sys.argv[2])  # 檢查用預覽圖
