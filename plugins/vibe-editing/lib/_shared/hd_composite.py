#!/usr/bin/env python3
"""hd_composite.py — build a speaker-aware source: HD camera whenever CALVIN is on screen,
Zoom Speaker View for the GUEST. Audio always from Zoom (continuous, in-sync). Reusable.

Detection: the Zoom Speaker View auto-switches to the active speaker. Classify each sampled
frame by the guest's distinct red/magenta torso (Kirsten) vs Calvin. Segment, median-smooth,
then composite video per segment; audio taken from Zoom throughout.

API: build_composite(windows, workdir, vfilter, spk, hd_local, offset) -> path to composite mp4
     (windows = [(zoom_in, zoom_out), ...] in Zoom source seconds)
"""
import subprocess, tempfile, os, glob
import numpy as np
from PIL import Image

def sh(cmd): subprocess.run(cmd, check=True)

def _labels(spk, a, b, fps=2.5, red_thresh=0.40):
    """Return [(t, 'CAL'|'KIR'), ...] sampled across [a,b] of the Speaker View."""
    d = tempfile.mkdtemp(prefix="lbl_")
    sh(["ffmpeg","-nostdin","-v","error","-ss",str(a),"-t",str(b-a),"-i",spk,
        "-vf",f"fps={fps},scale=160:90","-q:v","4",f"{d}/f_%05d.jpg"])
    out=[]
    for i,fp in enumerate(sorted(glob.glob(f"{d}/f_*.jpg"))):
        arr=np.asarray(Image.open(fp).convert("RGB")).astype(int)
        h,w,_=arr.shape
        reg=arr[int(h*0.62):, int(w*0.30):int(w*0.70)]
        R,G,B=reg[...,0],reg[...,1],reg[...,2]
        red=((R>G+35)&(R>B+15)).mean()
        out.append((a+i/fps, "KIR" if red>red_thresh else "CAL"))
        os.remove(fp)
    os.rmdir(d)
    return out

def _median_smooth(labels, k=5):
    """Mode filter over a window of k samples to kill 1-2 frame blips."""
    vals=[w for _,w in labels]; out=[]
    half=k//2
    for i in range(len(vals)):
        win=vals[max(0,i-half):i+half+1]
        out.append(max(set(win), key=win.count))
    return [(labels[i][0], out[i]) for i in range(len(vals))]

def _runs(labels, a, b, fps=2.5):
    """Collapse smoothed labels into (who, start, end) runs spanning [a,b]."""
    if not labels: return [("KIR" if False else "CAL", a, b)]
    runs=[]; step=1.0/fps
    for t,who in labels:
        if runs and runs[-1][0]==who: runs[-1][2]=t+step
        else: runs.append([who, t, t+step])
    runs[0][1]=a; runs[-1][2]=b
    # stitch boundaries
    for i in range(1,len(runs)): runs[i][1]=runs[i-1][2]
    return [(w,s,e) for w,s,e in runs]

def build_composite(windows, workdir, vfilter, spk, hd_local, offset=39.82, minseg=1.0):
    os.makedirs(workdir, exist_ok=True)
    have_hd = hd_local and os.path.exists(hd_local) and os.path.getsize(hd_local) > 100_000_000
    parts=[]; idx=0
    for (a,b) in windows:
        if have_hd:
            runs=_runs(_median_smooth(_labels(spk,a,b)), a, b)
            # merge runs shorter than minseg into previous (avoid flicker)
            merged=[]
            for r in runs:
                if merged and (r[2]-r[1])<minseg: merged[-1]=(merged[-1][0],merged[-1][1],r[2])
                else: merged.append(r)
            runs=merged
        else:
            runs=[("KIR",a,b)]  # fallback: plain Speaker View
        for (who,s,e) in runs:
            dur=e-s
            if dur<=0.05: continue
            p=f"{workdir}/seg_{idx:03d}.mp4"; idx+=1
            if who=="CAL" and have_hd:
                # video from HD (shifted by offset), audio from Zoom
                sh(["ffmpeg","-nostdin","-v","error","-ss",f"{s+offset}","-i",hd_local,
                    "-ss",f"{s}","-t",f"{dur}","-i",spk,"-map","0:v","-map","1:a",
                    "-r","30","-c:v","libx264","-crf","18","-pix_fmt","yuv420p","-vf",vfilter,
                    "-c:a","aac","-ar","48000","-ac","2","-t",f"{dur}",p,"-y"])
            else:
                sh(["ffmpeg","-nostdin","-v","error","-ss",f"{s}","-t",f"{dur}","-i",spk,
                    "-r","30","-c:v","libx264","-crf","18","-pix_fmt","yuv420p","-vf",vfilter,
                    "-c:a","aac","-ar","48000","-ac","2",p,"-y"])
            parts.append(p)
    # concat
    lst=f"{workdir}/_parts.txt"
    open(lst,"w").write("".join(f"file '{os.path.basename(p)}'\n" for p in parts))
    comp=f"{workdir}/composite.mp4"
    sh(["ffmpeg","-nostdin","-v","error","-f","concat","-safe","0","-i",os.path.basename(lst),
        "-c","copy","composite.mp4","-y"] if False else
       ["ffmpeg","-nostdin","-v","error","-f","concat","-safe","0","-i",lst,"-c","copy",comp,"-y"])
    return comp
