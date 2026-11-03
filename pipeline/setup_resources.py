"""Provision reusable resources; safe to rerun after an interrupted download."""
import subprocess, sys
import requests
from .paths import ECDICT_PATH,KAIKKI_PATH,MT_MODEL_PATH

def download(url,path):
    path.parent.mkdir(parents=True,exist_ok=True); tmp=path.with_suffix('.part')
    with requests.get(url,stream=True,timeout=120) as response:
        response.raise_for_status()
        with tmp.open('wb') as f:
            for chunk in response.iter_content(1024*1024): f.write(chunk)
    tmp.replace(path)

def main():
    if not ECDICT_PATH.exists(): download('https://raw.githubusercontent.com/skywind3000/ECDICT/master/ecdict.csv',ECDICT_PATH)
    if not KAIKKI_PATH.exists():
        KAIKKI_PATH.parent.mkdir(parents=True,exist_ok=True); tmp=KAIKKI_PATH.with_suffix('.part')
        with requests.get('https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl',stream=True,timeout=120) as r:
            r.raise_for_status()
            proc=subprocess.Popen([sys.executable,'-m','pipeline.build_kaikki_mini',str(tmp)],stdin=subprocess.PIPE)
            try:
                for chunk in r.iter_content(1024*1024): proc.stdin.write(chunk)
                proc.stdin.close()
                if proc.wait(): raise RuntimeError('Kaikki conversion failed')
            except BaseException:
                proc.kill(); proc.wait(); raise
        tmp.replace(KAIKKI_PATH)
    if not (MT_MODEL_PATH/'model.bin').exists():
        subprocess.run([sys.executable,'-m','ctranslate2.converters.transformers','--model','Helsinki-NLP/opus-mt-en-zh','--output_dir',str(MT_MODEL_PATH),'--quantization','int16','--copy_files','source.spm','target.spm'],check=True)
    try:
        import spacy
        spacy.load('en_core_web_sm')
    except OSError: subprocess.run([sys.executable,'-m','spacy','download','en_core_web_sm'],check=True)
if __name__=='__main__': main()
