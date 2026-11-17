#!/usr/bin/env python3
"""Inject faults with random.Random(seed).

The seed is the only random input. The same seed and fault-count always
rebuild the same delivery and the same ground truth. Students pick seeds
while tuning. The instructor later names one seed; students run that number
and read the report. Scene ids here are synthetic, not COCO sequences.
"""
import argparse, hashlib, json, random, shutil
from pathlib import Path
TYPES=['missing_image','wrong_hash','invalid_class','bbox_out_of_bounds','bbox_drift','class_swap','scene_leak','guideline_mismatch']

def sha(path):
    h=hashlib.sha256();
    with open(path,'rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def lines(path):return path.read_text(encoding='utf-8').strip().splitlines()
def alter(path,func):
    content=lines(path);idx=next((i for i,x in enumerate(content) if len(x.split())>=5),None)
    if idx is None:raise ValueError(f'No box in {path}')
    cols=content[idx].split();updated=func(cols)
    if updated is None:return False
    content[idx]=' '.join(updated);path.write_text('\n'.join(content)+'\n',encoding='utf-8')
    return True

def drift_of(cols):
    x=float(cols[1]);w=float(cols[3]);lo=w/2+.001;hi=1-w/2-.001
    if hi<=lo:return None
    nx=min(hi,max(lo,x+(0.05 if x<=0.5 else -0.05)))
    token=f'{nx:.6f}'
    # A shift that rounds back to the same token must not be recorded as a fault.
    if token==cols[1]:return None
    return [cols[0],token]+cols[2:]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',default='data_source/coco500')
    ap.add_argument('--seed',type=int,required=True)
    ap.add_argument('--out',required=True)
    ap.add_argument('--fault-count',type=int,default=8)
    ap.add_argument('--dev-truth',action='store_true',help='Print the ground truth for this seed. The file is always written to <out>/_private/truth.json')
    a=ap.parse_args(); rng=random.Random(a.seed)
    src=Path(a.source); imgs=sorted(src.rglob('images/train2017/*.jpg'));labs=sorted(src.rglob('labels/train2017/*.txt'))
    if len(imgs)<20 or len(labs)<20:raise SystemExit('Source not found. Run scripts/download_public.py first.')
    out=Path(a.out)
    if out.exists():shutil.rmtree(out)
    delivery=out/'delivery';(delivery/'images').mkdir(parents=True);(delivery/'labels').mkdir()
    images={p.stem:p for p in imgs};labels={p.stem:p for p in labs};stems=sorted(set(images)&set(labels))
    if len(stems)<20:raise SystemExit('Too few matching image/label pairs')
    for stem in stems:
        shutil.copyfile(images[stem],delivery/'images'/images[stem].name)
        shutil.copyfile(labels[stem],delivery/'labels'/labels[stem].name)
    meta=[]
    for idx,stem in enumerate(stems):
        group=idx//8
        meta.append({'image_id':stem,'scene_id':f'simulated_group_{group:03d}',
                     'split':'train' if group%2==0 else 'val','guideline_version':'v1.3'})
    meta_by={row['image_id']:row for row in meta}
    manifest={stem:{'image':f'images/{images[stem].name}','label':f'labels/{labels[stem].name}',
                    'image_sha256':sha(delivery/'images'/images[stem].name)} for stem in stems}
    truths=[];used=set();used_scenes=set()
    kinds=TYPES[:]
    if a.fault_count>len(kinds):kinds+=rng.choices(TYPES,k=a.fault_count-len(kinds))
    kinds=kinds[:a.fault_count];rng.shuffle(kinds)
    for kind in kinds:
        candidates=[st for st in stems if st not in used]
        if kind in ('invalid_class','bbox_out_of_bounds','bbox_drift','class_swap'):
            candidates=[st for st in candidates if any(len(line.split())>=5 for line in lines(delivery/'labels'/labels[st].name))]
        if kind=='bbox_drift':
            candidates=[st for st in candidates if drift_of(next(line.split() for line in lines(delivery/'labels'/labels[st].name) if len(line.split())>=5)) is not None]
        if kind=='scene_leak':
            candidates=[st for st in candidates if meta_by[st]['scene_id'] not in used_scenes]
        if not candidates:raise SystemExit('Insufficient distinct candidates')
        stem=rng.choice(candidates);used.add(stem)
        label_file=delivery/'labels'/labels[stem].name
        if kind=='missing_image':(delivery/'images'/images[stem].name).unlink()
        elif kind=='wrong_hash':manifest[stem]['image_sha256']='0'*64
        elif kind=='invalid_class':alter(label_file,lambda c:['99']+c[1:])
        elif kind=='bbox_out_of_bounds':alter(label_file,lambda c:[c[0],'1.200000']+c[2:])
        elif kind=='bbox_drift':
            if not alter(label_file,drift_of):raise SystemExit(f'bbox_drift did not change {stem}')
        elif kind=='class_swap':alter(label_file,lambda c:[str((int(float(c[0]))+1)%80)]+c[1:])
        elif kind=='scene_leak':
            row=meta_by[stem];row['split']='val' if row['split']=='train' else 'train';used_scenes.add(row['scene_id'])
        elif kind=='guideline_mismatch':meta_by[stem]['guideline_version']='v1.2'
        target=meta_by[stem]['scene_id'] if kind=='scene_leak' else stem
        unit='scene' if kind=='scene_leak' else 'image'
        truths.append({'type':kind,'target':target,'unit':unit})
    (delivery/'manifest.json').write_text(json.dumps({'dataset':'COCO500','num_classes':80,'guideline':'v1.3','items':manifest},indent=2))
    (delivery/'metadata.json').write_text(json.dumps({'meta_source':'SYNTHETIC for teaching: not real COCO scenes','items':meta},indent=2))
    public_release_id='coco500_'+hashlib.sha256((delivery/'manifest.json').read_bytes()+(delivery/'metadata.json').read_bytes()).hexdigest()[:12]
    (delivery/'release.json').write_text(json.dumps({'release_id':public_release_id,'source_url':'https://cocodataset.org/#download','note':'500 COCO val2017 images. Synthetic scene IDs, not real COCO sequences.'},indent=2))
    private=out/'_private';private.mkdir()
    (private/'truth.json').write_text(json.dumps({'seed':a.seed,'task':'detection','errors':truths},indent=2))
    if not a.dev_truth:
        print('Ground truth written to', private, '(the validator must not read this folder)')
    else:
        print('Ground truth:', truths)
    print(f'Seed={a.seed}, images={len(stems)}, faults={len(truths)}, delivery={delivery}')
if __name__=='__main__':main()
