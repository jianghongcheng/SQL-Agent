"""Own a temporary native Ollama process; never reconfigure the installed service.

Use with Docker API/Workers when the host has CUDA but Docker lacks its GPU runtime.
Model directory must already exist and be non-writable by this user. No pulls/pruning.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.request


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--models',type=Path,required=True)
    p.add_argument('runner_args',nargs=argparse.REMAINDER)
    args=p.parse_args()
    args.output=args.output.resolve(); args.models=args.models.resolve()
    args.output.mkdir(parents=True,exist_ok=False); args.output.chmod(0o700)
    if not args.models.is_dir() or os.access(args.models,os.W_OK):
        raise ValueError('existing non-writable model directory required')
    remainder=args.runner_args[1:] if args.runner_args[:1]==['--'] else args.runner_args
    if not remainder or '--base-url' in remainder or '--output' in remainder:
        raise ValueError('supply trial arguments, not output/base-url overrides')
    before={str(f.relative_to(args.models)):hashlib.sha256(f.read_bytes()).hexdigest()
            for f in (args.models/'manifests').rglob('*') if f.is_file()}
    evidence={'model_manifests_sha256':before,'existing_service_changed':False,
        'scope':'Native isolated inference process plus independent Docker API/Workers; not GPU-container deployment',
        'max_loaded_models':2,'parallel_requests_per_model':1,'context_length':4096,
        'flash_attention':True,'minimum_free_vram_mib':17000}
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    base='http://127.0.0.1:'+str(port)
    env={k:v for k,v in os.environ.items() if not k.startswith('OLLAMA_')}
    env.update(OLLAMA_HOST=base,OLLAMA_MODELS=str(args.models),OLLAMA_NOPRUNE='true',
        OLLAMA_NO_CLOUD='true',OLLAMA_MAX_LOADED_MODELS='2',OLLAMA_NUM_PARALLEL='1',
        OLLAMA_CONTEXT_LENGTH='4096',OLLAMA_KEEP_ALIVE='120s',OLLAMA_FLASH_ATTENTION='true')
    process=None
    try:
        deadline=time.monotonic()+240
        while True:
            free=int(subprocess.check_output(['nvidia-smi','--query-gpu=memory.free','--format=csv,noheader,nounits'],text=True).strip().splitlines()[0])
            if free>=17000: break
            if time.monotonic()>deadline: raise RuntimeError('insufficient free GPU memory; existing workloads were not stopped')
            print(json.dumps({'phase':'waiting_for_existing_residency_to_expire','free_mib':free}),flush=True)
            time.sleep(10)
        evidence['free_vram_before_mib']=free
        with (args.output/'inference.log').open('w') as log:
            process=subprocess.Popen(['/usr/local/bin/ollama','serve'],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            evidence.update(process_id=process.pid,base_url=base)
            deadline=time.monotonic()+30
            while True:
                try:
                    with urllib.request.urlopen(base+'/api/version',timeout=2) as response:
                        evidence['version']=json.load(response); break
                except OSError:
                    if process.poll() is not None or time.monotonic()>deadline:
                        raise RuntimeError('temporary inference server unavailable; inspect inference.log')
                    time.sleep(.2)
            (args.output/'inference.json').write_text(json.dumps(evidence,indent=2))
            command=[sys.executable,str(Path(__file__).with_name('validate_live_rag_deployment.py')),
                '--output',str(args.output/'trial'),'--base-url',base,*remainder]
            result=subprocess.run(command)
            evidence['trial_exit_code']=result.returncode
            with urllib.request.urlopen(base+'/api/ps',timeout=5) as response:
                evidence['final_model_residency']=json.load(response)
            if result.returncode: raise RuntimeError('live acceptance failed; inspect trial artifacts')
    finally:
        if process is not None:
            # This process owns its own process group; never match or kill by name.
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGTERM)
                try: process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
            evidence['temporary_inference_stopped']=True
        after={str(f.relative_to(args.models)):hashlib.sha256(f.read_bytes()).hexdigest()
               for f in (args.models/'manifests').rglob('*') if f.is_file()}
        evidence['original_model_manifests_unchanged']=before==after
        (args.output/'inference.json').write_text(json.dumps(evidence,indent=2))


if __name__=='__main__': main()
