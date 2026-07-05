#!/usr/bin/env python3
"""make_clip.py — produce ONE clip from the content_map, from the Zoom Speaker View source.
Shorts: kit render (9:16 reframe + brand captions + Auphonic enhance) + 9:16 end card.
Mids:   cut/stitch (16:9) + Auphonic enhance + 16:9 end card (no burned captions — YouTube).
Re-runs the sharing guard as a hard safety check. Delivers to Dropbox + Telegram.

Usage: make_clip.py <kind: short|mid> <index-in-that-list>
"""
import sys, os, json, subprocess, re, shutil
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hd_composite import build_composite

VE   = "/srv/ContentPipeline/vibe-editing"
PLUG = f"{VE}/plugins/vibe-editing"
PY   = f"{PLUG}/.venv/bin/python"
PROJ = f"{VE}/projects/2026-06-26-kirsten"
SPK  = f"{PROJ}/00_SOURCE/2026-06-26-recode-kirsten-speaker.mp4"
HD_LOCAL = f"{PROJ}/00_SOURCE/2026-06-26-recode-HD.mp4"   # full HD (Calvin cam); composite uses it
HD_OFFSET = 39.82                                          # HD = Zoom + offset (verified constant)
CAPPRESET = f"{PROJ}/10_WORK/calvin_y55.json"
EC_V = f"{VE}/brand/endcard_silent.mp4"          # 9:16
EC_H = f"{VE}/brand/endcard16x9_silent.mp4"      # 16:9
GUARD = f"{PLUG}/lib/_shared/sharing_guard.py"
ENHANCE = f"{PLUG}/skills/audio-enhance/scripts/enhance.py"
NOTIFY = f"{PLUG}/lib/_shared/notify_clip.py"
DBX_BASE = "/Simplero Team Folder/Calvin Content/2026-06-26 - Podcast - Recode Your Mind - Kirsten D'Andrea Hollander"
DBX_SUBDIR = {"short": "Shorts", "mid": "Mids", "carousel": "Carousels",
              "shorttext": "ShortText", "midtext": "MidText", "longtext": "LongText"}

def sh(cmd, **k): return subprocess.run(cmd, check=True, **k)
def slug(t): return re.sub(r'[^a-z0-9]+','-', t.lower()).strip('-')[:48]
def clean_name(t):
    # readable filename per convention: no path-breakers/illegal chars, keep spaces/apostrophes
    t = re.sub(r'\s*[/\\:]\s*', ' - ', t)
    t = re.sub(r'[*?"<>|]', '', t)
    return re.sub(r'\s+', ' ', t).strip()

def guard(windows):
    flat=[str(x) for w in windows for x in w]
    r=subprocess.run([PY,GUARD,PROJ]+flat,capture_output=True,text=True)
    if r.returncode!=0:
        raise SystemExit(f"GUARD BLOCKED: {r.stdout}")

def cut_windows(windows, outdir, vfilter):
    """Cut each window from Speaker View (video+audio), return list of part files."""
    parts=[]
    for i,(a,b) in enumerate(windows):
        p=f"{outdir}/part_{i:02d}.mp4"
        sh(["ffmpeg","-nostdin","-v","error","-ss",f"{a}","-t",f"{b-a}","-i",SPK,
            "-r","30","-c:v","libx264","-crf","18","-pix_fmt","yuv420p","-vf",vfilter,
            "-c:a","aac","-ar","48000","-ac","2",p,"-y"])
        parts.append(p)
    return parts

def concat(parts, out):
    lst=out+".txt"; Path(lst).write_text("".join(f"file '{os.path.basename(p)}'\n" for p in parts))
    sh(["ffmpeg","-nostdin","-v","error","-f","concat","-safe","0","-i",lst,"-c","copy",out,"-y"],
       cwd=os.path.dirname(out))

def append_endcard(body, ec):
    tmp=body[:-4]+"_ec.mp4"
    sh(["ffmpeg","-nostdin","-v","error","-i",body,"-i",ec,
        "-filter_complex","[0:v][0:a][1:v][1:a]concat=n=2:v=1:a=1[v][a]","-map","[v]","-map","[a]",
        "-c:v","libx264","-crf","18","-r","30","-pix_fmt","yuv420p","-c:a","aac","-ar","48000","-b:a","192k",tmp,"-y"])
    shutil.move(tmp, body)

def deliver(path, title, kind):
    # upload to Dropbox under Shorts/ or Mids/ (Text/ reserved for text posts)
    dest=f"{DBX_BASE}/{DBX_SUBDIR.get(kind,'Shorts')}/{os.path.basename(path)}"
    rb=f'''require_relative "/srv/ContentPipeline/content-pipeline/lib/content_pipeline"
dbx=ContentPipeline::DropboxClient.new
dbx.upload({json.dumps(path)}, {json.dumps(dest)})
puts (dbx.get_shared_link({json.dumps(dest)}) rescue dbx.get_direct_download_link({json.dumps(dest)}))'''
    import time
    link=""
    for attempt in range(4):
        r=subprocess.run(["ruby","-e",rb],capture_output=True,text=True,cwd="/srv/ContentPipeline/content-pipeline")
        out=(r.stdout or "").strip().splitlines()
        link=out[-1] if out else ""
        if link.startswith("http"): break
        print(f"upload attempt {attempt+1} failed (retrying): {r.stderr[-160:]!r}")
        time.sleep(5)
    if not link.startswith("http"):
        print(f"WARN upload/link ultimately failed for {path}")
    notify=[PY,NOTIFY,path,"--title",f"[{kind.upper()}] {title}"]
    if link.startswith("http"): notify+=["--link",link]
    sh(notify)
    return link

def main():
    kind, idx = sys.argv[1], int(sys.argv[2])
    cm=json.load(open(f"{PROJ}/content_map.json"))
    lst = cm["shorts"] if kind=="short" else cm["mids"]
    c = sorted(lst, key=lambda x:x["rank"])[idx]
    windows=[tuple(w) for w in c["windows"]]
    guard(windows)  # hard safety re-check
    name=f"2026-06-26 - Recode - {clean_name(c['title'])}"
    wdir=f"{VE}/projects/kirsten-batch/{kind}-{slug(c['title'])}"
    os.makedirs(f"{wdir}/10_WORK", exist_ok=True); os.makedirs(f"{wdir}/20_DELIVER", exist_ok=True)

    if kind=="mid":
        # 16:9, HD-for-Calvin composite (Speaker View for guest), no reframe, no burned captions
        body=build_composite(windows, f"{wdir}/10_WORK", "scale=1920:1080,fps=30",
                             SPK, HD_LOCAL, HD_OFFSET)
        # enhance audio
        enh=f"{wdir}/10_WORK/enh.wav"
        sh([PY,ENHANCE,body,"--out",enh,"--loudness","-16"])
        out=f"{wdir}/20_DELIVER/{name}.mp4"
        sh(["ffmpeg","-nostdin","-v","error","-i",body,"-i",enh,"-map","0:v","-map","1:a",
            "-c:v","copy","-c:a","aac","-b:a","192k","-shortest",out,"-y"])
        append_endcard(out, EC_H)
        link=deliver(out,c["title"],"mid")
        print(f"MID DONE {out} {link}")
    else:
        # 9:16 short via kit — HD-for-Calvin composite as the source, then reframe
        asm=build_composite(windows, f"{wdir}/10_WORK", "scale=1920:1080,fps=30",
                            SPK, HD_LOCAL, HD_OFFSET)
        sh(["ffmpeg","-nostdin","-v","error","-i",asm,"-vn","-ac","2","-ar","48000",
            f"{wdir}/10_WORK/assembled_audio.wav","-y"])
        dur=float(subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",asm],
                                 capture_output=True,text=True).stdout.strip())
        json.dump({"segments":[{"in":0.0,"out":round(dur-0.03,2),"text":c["title"]}]},
                  open(f"{wdir}/10_WORK/cuts.json","w"))
        m={"title":slug(c["title"]),"pipeline":"single","stages":{
            "cut":{"source_video":f"10_WORK/{os.path.basename(asm)}","source_audio":"10_WORK/assembled_audio.wav","spec":"10_WORK/cuts.json","snap_silence":False},
            "reframe":{"preset":"talking-head","zoom":1.0,"eye_y":0.30,"res":"4k","scene_split":True},
            "grade":{"filter":"eq=contrast=1.06:saturation=1.08:gamma=0.98,colorbalance=rm=0.015:gm=-0.022:bm=-0.035"},
            "captions":{"preset":CAPPRESET,"context":c.get("theme","")[:200],"no_layout":True},
            "enhance":{"enabled":True},
            "mix":{"music":None,"voice_lufs":-16,"fade_out":0.3,"limiter":0.45},
            "leadfix":{"head_trim":0.0}},
            "output":{"name":f"{name}.mp4","dir":"20_DELIVER"}}
        json.dump(m, open(f"{wdir}/manifest.json","w"), indent=2)
        env=dict(os.environ, CLAUDE_PLUGIN_ROOT=PLUG, VIBE_PIPELINE_ROOT=PLUG, PATH=f"{PLUG}/.venv/bin:"+os.environ["PATH"])
        sh([PY,f"{PLUG}/skills/render/engine.py",wdir,"--from","cut"], env=env)
        # capitalize leading lowercase conjunction in caption
        cache=sorted(Path(f"{wdir}/10_WORK/caption_gen_cache").glob("*/spice_norm.json"),
                     key=lambda p:p.stat().st_mtime, reverse=True)
        if cache:
            d=json.load(open(cache[0])); ws=d if isinstance(d,list) else d["words"]
            if ws and ws[0]["word"][:1].islower():
                ws[0]["word"]=ws[0]["word"][:1].upper()+ws[0]["word"][1:]
                json.dump(d, open(cache[0],"w"))
                for s in ["captions","enhance","mix","leadfix"]:
                    for f in Path(f"{wdir}/10_WORK/stages/{s}").glob("*"): f.unlink()
                sh([PY,f"{PLUG}/skills/render/engine.py",wdir,"--from","captions"], env=env)
        out=sorted(Path(f"{wdir}/20_DELIVER").rglob("*.mp4"))[0]
        append_endcard(str(out), EC_V)
        link=deliver(str(out),c["title"],"short")
        print(f"SHORT DONE {out} {link}")

if __name__=="__main__": main()
