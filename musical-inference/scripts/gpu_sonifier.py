"""Live, adapter-specific PDH/NVML telemetry to a continuous musical audio stream."""
import ctypes as C, threading, time, json, re, wave, pathlib
from collections import defaultdict, deque
import numpy as np

class Fmt(C.Structure): _fields_=[('status',C.c_uint32),('value',C.c_double)]
class Item(C.Structure): _fields_=[('name',C.c_wchar_p),('fmt',Fmt)]
class Util(C.Structure): _fields_=[('gpu',C.c_uint),('memory',C.c_uint)]
class Memory(C.Structure): _fields_=[('total',C.c_uint64),('free',C.c_uint64),('used',C.c_uint64)]
class Format(C.Structure):
    _fields_=[('tag',C.c_ushort),('channels',C.c_ushort),('rate',C.c_uint),('bytes_sec',C.c_uint),('align',C.c_ushort),('bits',C.c_ushort),('extra',C.c_ushort)]
class Header(C.Structure):
    _fields_=[('data',C.c_void_p),('length',C.c_uint),('recorded',C.c_uint),('user',C.c_size_t),('flags',C.c_uint),('loops',C.c_uint),('next',C.c_void_p),('reserved',C.c_size_t)]

SCALE=(0,3,5,7,10,12,15,17,19,22,24)
VOICES={'vram':(40,'bass',0),'memory_io':(64,'shimmer',1),'compute':(52,'pluck',2),'3d':(64,'brass',3),'copy':(76,'marimba',4),'videodecode':(64,'flute',5),'videoencode':(52,'reed',6),'jpeg_decode_1':(76,'bell',7),'ofa_0':(64,'glass',8),'vr':(52,'organ',9),'security':(76,'click',10)}
def pitch(base,usage): return base+SCALE[min(10,max(0,int(usage/10)))]

class Telemetry:
    def __init__(self,index=0):
        self.index=index
        self.engine_gap_since=None; self.engine_dropouts=0
        cuda=C.WinDLL('nvcuda.dll'); self.pdh=C.WinDLL('pdh.dll'); self.nv=C.WinDLL('nvml.dll')
        if cuda.cuInit(0): raise RuntimeError('CUDA unavailable')
        luid=C.create_string_buffer(8); mask=C.c_uint()
        if cuda.cuDeviceGetLuid(luid,C.byref(mask),index): raise RuntimeError('Cannot identify CUDA adapter')
        low=int.from_bytes(luid.raw[:4],'little'); high=int.from_bytes(luid.raw[4:],'little')
        self.luid=f'luid_0x{high:08x}_0x{low:08x}'
        self.query=C.c_void_p(); self.counter=C.c_void_p()
        self.pdh.PdhOpenQueryW.argtypes=[C.c_wchar_p,C.c_size_t,C.POINTER(C.c_void_p)]
        self.pdh.PdhAddEnglishCounterW.argtypes=[C.c_void_p,C.c_wchar_p,C.c_size_t,C.POINTER(C.c_void_p)]
        if self.pdh.PdhOpenQueryW(None,0,C.byref(self.query)): raise RuntimeError('PDH query failed')
        if self.pdh.PdhAddEnglishCounterW(self.query,r'\GPU Engine(*)\Utilization Percentage',0,C.byref(self.counter)): raise RuntimeError('GPU counters unavailable')
        self.pdh.PdhCollectQueryData(self.query)
        if self.nv.nvmlInit_v2(): raise RuntimeError('NVML unavailable')
        self.device=C.c_void_p()
        name=C.create_string_buffer(128); cuda.cuDeviceGetPCIBusId(name,128,index)
        if self.nv.nvmlDeviceGetHandleByPciBusId_v2(name,C.byref(self.device)): raise RuntimeError('NVML adapter match failed')
    def read(self):
        if self.pdh.PdhCollectQueryData(self.query): raise RuntimeError('GPU telemetry collection failed')
        size=C.c_uint32(); count=C.c_uint32()
        self.pdh.PdhGetFormattedCounterArrayW(self.counter,0x200,C.byref(size),C.byref(count),None)
        buf=C.create_string_buffer(max(1,size.value))
        rc=self.pdh.PdhGetFormattedCounterArrayW(self.counter,0x200,C.byref(size),C.byref(count),buf)
        valid=rc==0
        if rc:
            if rc&0xffffffff not in (0xc0000bba,0x800007d2): raise RuntimeError(f'GPU engine formatting failed {rc}')
            self.engine_dropouts+=1
            if self.engine_gap_since is None: self.engine_gap_since=time.monotonic()
            if time.monotonic()-self.engine_gap_since>2: raise RuntimeError('Engine telemetry unavailable for more than two seconds')
            count.value=0
        else: self.engine_gap_since=None
        engine=defaultdict(float)
        for item in C.cast(buf,C.POINTER(Item*count.value)).contents:
            if self.luid not in item.name.lower() or item.fmt.status not in (0,1): continue
            m=re.search(r'_eng_(\d+)_engtype_(.+)',item.name.lower())
            if m: engine[(m[1],m[2])]+=max(0,item.fmt.value)
        types=defaultdict(float)
        for (idx,kind),v in engine.items(): types[kind]=max(types[kind],min(100,v))
        util=Util(); mem=Memory()
        if self.nv.nvmlDeviceGetUtilizationRates(self.device,C.byref(util)): raise RuntimeError('NVML activity unavailable')
        if self.nv.nvmlDeviceGetMemoryInfo(self.device,C.byref(mem)): raise RuntimeError('NVML memory unavailable')
        values={'vram':100*mem.used/max(1,mem.total),'memory_io':util.memory}
        values.update(types)
        temperature=C.c_uint(); power=C.c_uint()
        if self.nv.nvmlDeviceGetTemperature(self.device,0,C.byref(temperature)): raise RuntimeError('GPU temperature unavailable')
        power_rc=self.nv.nvmlDeviceGetPowerUsage(self.device,C.byref(power))
        return {'timestamp':time.time(),'gpu_index':self.index,'adapter':self.luid,'engine_data_valid':valid,'engine_dropouts':self.engine_dropouts,'usage':values,'memory_MiB':mem.used/1024**2,'gpu_pct':util.gpu,'temperature_C':temperature.value,'power_W':None if power_rc else power.value/1000}
    def close(self):
        self.pdh.PdhCloseQuery(self.query); self.nv.nvmlShutdown()

def synth(usage,step,rate=44100,duration=.125,transpose=0):
    n=int(rate*duration); t=np.arange(n)/rate; out=np.zeros((n,2))
    for kind,value in sorted(usage.items()):
        if value<.8 or kind.startswith('timer'): continue
        base,instrument,panid=VOICES.get(kind,(64,'glass',11))
        # Unknown exposed engines retain individual lanes and distinct stereo placement.
        if kind not in VOICES: panid=11+sum(map(ord,kind))%7; base=52+12*(panid%3)
        midi=min(100,pitch(base,value)+transpose); f=440*2**((midi-69)/12)
        if kind=='vram' and step%4: continue
        if kind!='vram' and value<20 and (step+panid)%4: continue
        env=np.minimum(1,t/.004)*np.exp(-t*(7 if kind=='vram' else 22))
        phase=2*np.pi*f*t
        if instrument=='bass': signal=np.sin(phase)+.25*np.sin(phase*2)
        elif instrument=='pluck': signal=np.sin(phase+1.8*np.exp(-t*13)*np.sin(phase*2))+.22*np.sin(phase*.5)+.10*np.sin(phase*2)
        elif instrument=='brass': signal=np.sin(phase)+.4*np.sin(phase*2)+.22*np.sin(phase*3)
        elif instrument=='marimba': signal=np.sin(phase)+.3*np.sin(phase*4)*np.exp(-t*40)
        elif instrument=='flute': signal=np.sin(phase)+.12*np.sin(phase*3)
        elif instrument=='reed': signal=np.sin(phase)+.3*np.sin(phase*3)+.15*np.sin(phase*5)
        elif instrument=='organ': signal=np.sin(phase)+.4*np.sin(phase*.5)
        elif instrument=='click': signal=np.sin(phase)*np.exp(-t*100)
        else: signal=np.sin(phase+.6*np.sin(phase*3))*np.exp(-t*8)
        # Shared pentatonic key; activity raises both pitch and strength.
        # A faint octave/fifth layer adds depth without changing the data-bearing root.
        harmonic=(.16*np.sin(phase*1.5)+.09*np.sin(phase*2))*np.exp(-t*10)
        sound=(signal+harmonic)*env*(.018+.055*value/100)
        pan=(panid%7)/6
        motion=.06*np.sin(2*np.pi*.4*(step*duration+t)+panid)
        left=np.clip(1-pan+motion,.12,.88); right=1-left
        # Soft detuned unisons give each instrument depth inside its GPU's stereo region.
        air_l=.055*np.sin(phase*.9991)*env*(value/100)*.05
        air_r=.055*np.sin(phase*1.0009)*env*(value/100)*.05
        out[:,0]+=sound*np.sqrt(left)+air_l; out[:,1]+=sound*np.sqrt(right)+air_r
    # Smooth block boundaries prevent clicks.
    out*=np.minimum(1,(duration-t)/.012)[:,None]
    return (np.tanh(out)*28000).astype('<i2').tobytes()

class Sonifier:
    def __init__(self,indices=(0,),seamless=False,telemetry_factory=None,output_dir=None,recording_seconds=None):
        self.indices=indices; self.seamless=seamless; self.finish_requested=threading.Event()
        self.telemetry_factory=telemetry_factory or Telemetry
        self.output_dir=pathlib.Path(output_dir or '.'); self.output_dir.mkdir(parents=True,exist_ok=True)
        self.recording_blocks=None if recording_seconds is None else max(8,min(960,int(recording_seconds*8)))
        self.stop_event=threading.Event(); self.error=None; self.rows=[] if self.recording_blocks is None else deque(maxlen=self.recording_blocks); self.latest=None
    def start(self):
        self.telemetries=[self.telemetry_factory(i) for i in self.indices]; self.latest=self.telemetries[0].read()
        if self.seamless:
            from gpu_test_audio import prepare
            prepare()
            self.cues={}
            for kind in ('start','finish'):
                with wave.open(f'gpu-{kind}-jingle.wav','rb') as w:
                    self.cues[kind]=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2).astype(float)
        self.thread=threading.Thread(target=self.run,daemon=True); self.thread.start()
    def run(self):
        win=C.WinDLL('winmm.dll'); handle=C.c_void_p(); fmt=Format(1,2,44100,176400,4,16,0)
        win.waveOutOpen.argtypes=[C.POINTER(C.c_void_p),C.c_uint,C.POINTER(Format),C.c_size_t,C.c_size_t,C.c_uint]
        active=[]; recording=[] if self.recording_blocks is None else deque(maxlen=self.recording_blocks); step=0; finish_step=None; echo_history=[]
        try:
            rc=win.waveOutOpen(C.byref(handle),0xffffffff,C.byref(fmt),0,0,0)
            if rc: raise RuntimeError(f'Audio output failed {rc}')
            while not self.stop_event.is_set():
                if len(active)>=2:
                    data,header=active.pop(0)
                    while not header.flags&1 and not self.stop_event.is_set(): time.sleep(.002)
                    if self.stop_event.is_set(): active.insert(0,(data,header)); break
                    win.waveOutUnprepareHeader(handle,C.byref(header),C.sizeof(header))
                rows=[]; mixed=np.zeros((5512,2))
                for pos,telemetry in enumerate(self.telemetries):
                    row=telemetry.read(); row['step']=step
                    transpose=12*pos if len(self.indices)>1 else 0
                    row['notes']={k:min(100,pitch(VOICES.get(k,(52+12*((11+sum(map(ord,k))%7)%3),'glass',11))[0],v)+transpose) for k,v in row['usage'].items() if v>=.8}
                    rows.append(row); self.rows.append(row)
                    stream=np.frombuffer(synth(row['usage'],step,transpose=transpose),dtype='<i2').reshape(-1,2).astype(float)
                    if len(self.indices)==1: mixed+=stream
                    else:
                        pan=pos/max(1,len(self.indices)-1)
                        mid=stream.mean(axis=1); side=(stream[:,0]-stream[:,1])*.5
                        mixed[:,0]+=(mid+side*.4)*(.95-.70*pan)
                        mixed[:,1]+=(mid-side*.4)*(.25+.70*pan)
                self.latest=rows[0] if len(rows)==1 else {'devices':rows}
                if self.seamless:
                    if self.finish_requested.is_set() and finish_step is None:
                        finish_step=((step+3)//4)*4
                    kind='finish' if finish_step is not None and step>=finish_step else 'start'
                    cue=self.cues[kind]; cue_pos=(step-finish_step if kind=='finish' else step)*5512
                    if cue_pos<len(cue):
                        block=np.zeros_like(mixed); piece=cue[cue_pos:cue_pos+5512]; block[:len(piece)]=piece
                        if kind=='start':
                            blend=np.clip((np.arange(5512)+cue_pos-(len(cue)-22050))/22050,0,1)[:,None]
                            mixed=block+mixed*blend
                        else:
                            blend=np.maximum(0,1-(np.arange(5512)+cue_pos)/22050)[:,None]
                            mixed=block+mixed*blend
                    elif kind=='finish':
                        if cue_pos<len(cue)+4*5512: mixed*=0
                        else: break
                dry=mixed.copy()
                # Beat-locked cross-channel echoes unify the intro, live voices, and outro.
                if len(echo_history)>=2: mixed+=echo_history[-2][:,::-1]*.17
                if len(echo_history)>=3: mixed+=echo_history[-3]*.09
                if len(echo_history)>=5: mixed+=echo_history[-5][:,::-1]*.05
                echo_history.append(dry)
                if len(echo_history)>6: echo_history.pop(0)
                audio=np.clip(mixed,-32767,32767).astype('<i2').tobytes(); recording.append(audio)
                data=C.create_string_buffer(audio); header=Header(C.cast(data,C.c_void_p),len(audio),0,0,0,0,None,0)
                if win.waveOutPrepareHeader(handle,C.byref(header),C.sizeof(header)): raise RuntimeError('Audio prepare failed')
                if win.waveOutWrite(handle,C.byref(header),C.sizeof(header)): raise RuntimeError('Audio write failed')
                active.append((data,header)); step+=1
        except Exception as e: self.error=str(e)
        finally:
            if handle.value:
                if self.seamless and finish_step is not None and not self.error:
                    drain_deadline=time.monotonic()+2
                    while any(not header.flags&1 for data,header in active) and time.monotonic()<drain_deadline: time.sleep(.002)
                win.waveOutReset(handle)
                for data,header in active: win.waveOutUnprepareHeader(handle,C.byref(header),C.sizeof(header))
                win.waveOutClose(handle)
            for telemetry in self.telemetries: telemetry.close()
            with wave.open(str(self.output_dir/'gpu-live-soundtrack.wav'),'wb') as w:
                w.setnchannels(2); w.setsampwidth(2); w.setframerate(44100); w.writeframes(b''.join(recording))
            with (self.output_dir/'gpu-sonification-telemetry.json').open('w') as f: json.dump({'error':self.error,'samples':list(self.rows)},f)
    def stop(self):
        if self.seamless:
            self.finish_requested.set(); self.thread.join(4)
        self.stop_event.set(); self.thread.join(5)

