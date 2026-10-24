import sys, json, numpy as np, soundfile as sf, sherpa_onnx, opencc
M=sys.argv[1]; OUT=sys.argv[2]
cfg=sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
  model=f'{M}/model.onnx',voices=f'{M}/voices.bin',tokens=f'{M}/tokens.txt',data_dir=f'{M}/espeak-ng-data',dict_dir=f'{M}/dict',
  lexicon=f'{M}/lexicon-us-en.txt,{M}/lexicon-zh.txt'),num_threads=4),rule_fsts=f'{M}/date-zh.fst,{M}/phone-zh.fst,{M}/number-zh.fst')
tts=sherpa_onnx.OfflineTts(cfg); cc=opencc.OpenCC('t2s')
lines=json.load(open(sys.argv[3]))
SPK={'narr':(47,1.2),'guan':(52,0.95),'duke':(49,0.9)}
meta=[]
for i,l in enumerate(lines):
    sid,sp=SPK[l['who']]
    a=tts.generate(cc.convert(l.get('say',l['text'])),sid=sid,speed=sp)
    x=np.array(a.samples,dtype=np.float32); sr=a.sample_rate
    nz=np.where(np.abs(x)>0.01)[0]; x=x[max(0,nz[0]-int(.03*sr)):nz[-1]+int(.08*sr)]
    x=x/np.abs(x).max()*0.9
    sf.write(f'{OUT}/line{i}.wav',x,sr)
    hop=sr//100; n=len(x)//hop
    rms=np.array([np.sqrt(np.mean(x[k*hop:(k+1)*hop]**2)) for k in range(n)])
    env=np.clip((rms-0.015)/(np.percentile(rms,92)-0.015+1e-6),0,1)
    env=np.convolve(env,np.ones(3)/3,'same')
    meta.append({'dur':len(x)/sr,'env':[round(float(v),2) for v in env]})
    print(i,l['who'],round(len(x)/sr,2),'s')
json.dump(meta,open(f'{OUT}/voice.json','w'))
