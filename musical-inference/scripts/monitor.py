"""Explicit-process musical GPU monitor. Offline demo never opens a sound device."""
import argparse, json, math, os, pathlib, sys, time, wave
import numpy as np
from gpu_sonifier import synth

def positive(value):
    n=int(value)
    if not 1<=n<=600:raise argparse.ArgumentTypeError('seconds must be 1..600')
    return n

def demo(out):
    with wave.open(str(out/'synthetic-demo.wav'),'wb') as w:
        w.setnchannels(2);w.setsampwidth(2);w.setframerate(44100)
        for step in range(32):w.writeframes(synth({'compute':(step*7)%100,'copy':20},step))
    return {'source':'synthetic','measured_inference':False,'frames':32*5512,'sample_rate_hz':44100}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--discover',action='store_true');ap.add_argument('--demo',action='store_true');ap.add_argument('--play',action='store_true');ap.add_argument('--pid',type=int);ap.add_argument('--adapter-index',type=int);ap.add_argument('--seconds',type=positive,default=10);ap.add_argument('--output',type=pathlib.Path,default=pathlib.Path('runs'));a=ap.parse_args()
    if a.demo and (a.play or a.pid is not None or a.discover):ap.error('demo is separate from live capture')
    if a.discover:
        if os.name!='nt':ap.error('live discovery requires Windows')
        from telemetry import radeon
        print(json.dumps({'adapters':list(enumerate(radeon()))}));return
    if not a.demo and (a.pid is None or a.pid<=0 or a.adapter_index is None or not 0<=a.adapter_index<16):ap.error('live capture requires positive --pid and --adapter-index 0..15')
    if a.output.exists() and a.output.is_symlink():ap.error('output symlinks are refused')
    a.output.mkdir(parents=True,exist_ok=True)
    lock=a.output/'.monitor.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    except FileExistsError:ap.error('output already in use; inspect stale lock after verifying no monitor is running')
    sound=None;telemetry=None
    try:
        if a.demo:result=demo(a.output)
        else:
            if os.name!='nt':raise RuntimeError('live capture requires Windows')
            import psutil
            if psutil.virtual_memory().available<8*1024**3:raise RuntimeError('less than 8 GiB RAM available')
            from telemetry import radeon, ProcessTelemetry
            from gpu_sonifier import Sonifier
            adapters=radeon()
            if a.adapter_index>=len(adapters):raise ValueError('adapter does not exist')
            process=psutil.Process(a.pid);birth=process.create_time();telemetry=ProcessTelemetry(a.pid,adapters[a.adapter_index]);time.sleep(.5)
            first=telemetry.read()
            if not first['engine_data_valid'] or not first['matched_counters']:raise RuntimeError('no valid process counters on selected adapter')
            if a.play:
                telemetry.close();telemetry=None
                sound=Sonifier(telemetry_factory=lambda _:ProcessTelemetry(a.pid,adapters[a.adapter_index]),output_dir=a.output,recording_seconds=120);sound.start()
            rows=[];deadline=time.monotonic()+a.seconds;state='completed'
            try:
                while time.monotonic()<deadline:
                    if not process.is_running() or process.create_time()!=birth:raise RuntimeError('selected process exited or identity changed')
                    if psutil.virtual_memory().available<8*1024**3:raise RuntimeError('less than 8 GiB RAM available; stopping observer')
                    if sound and sound.error:raise RuntimeError(sound.error)
                    row=sound.latest if sound else telemetry.read()
                    if row:rows.append(row)
                    time.sleep(.5)
            except KeyboardInterrupt:state='cancelled'
            if sound:
                sound.stop()
                error=sound.error;sound=None
                if error:raise RuntimeError(error)
            valid=sum(bool(r.get('engine_data_valid') and r.get('matched_counters')) for r in rows)
            if not valid and state!='cancelled':raise RuntimeError('no valid samples retained')
            result={'source':'live_PDH','state':state,'process_id':a.pid,'process_birth':birth,'samples':rows,'valid_samples':valid,'audio_requested':a.play,'human_hearing':'unconfirmed','model_tokens_per_second':None}
        (a.output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in result.items() if k!='samples'}))
    finally:
        if sound:sound.stop()
        if telemetry:telemetry.close()
        os.close(fd);lock.unlink(missing_ok=True)

if __name__=='__main__':
    try:main()
    except Exception as e:print(str(e),file=sys.stderr);raise SystemExit(1)
