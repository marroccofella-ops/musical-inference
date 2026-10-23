"""Windows DXGI/PDH telemetry; no model text, command lines or network access."""
import ctypes as C, json, re, time, uuid
from collections import defaultdict
from gpu_sonifier import Fmt, Item
class Luid(C.Structure): _fields_=[('low',C.c_uint32),('high',C.c_int32)]
class Desc(C.Structure):
    _fields_=[('name',C.c_wchar*128),('vendor',C.c_uint32),('device',C.c_uint32),('subsys',C.c_uint32),('revision',C.c_uint32),('dedicated',C.c_size_t),('system',C.c_size_t),('shared',C.c_size_t),('luid',Luid),('flags',C.c_uint32)]
def method(ptr,index,restype,*args):
    table=C.cast(ptr,C.POINTER(C.POINTER(C.c_void_p))).contents
    return C.WINFUNCTYPE(restype,C.c_void_p,*args)(table[index])
def radeon():
    dxgi=C.WinDLL('dxgi.dll'); factory=C.c_void_p()
    iid=(C.c_ubyte*16).from_buffer_copy(uuid.UUID('770aae78-f26f-4dba-a829-253c83d1b387').bytes_le)
    dxgi.CreateDXGIFactory1.argtypes=[C.c_void_p,C.POINTER(C.c_void_p)];dxgi.CreateDXGIFactory1.restype=C.c_long
    if dxgi.CreateDXGIFactory1(C.byref(iid),C.byref(factory))<0:raise RuntimeError('DXGI discovery failed')
    matches=[]; observed=[]
    try:
        for i in range(16):
            adapter=C.c_void_p()
            if method(factory,12,C.c_long,C.c_uint,C.POINTER(C.c_void_p))(factory,i,C.byref(adapter))<0:break
            try:
                desc=Desc()
                if method(adapter,10,C.c_long,C.POINTER(Desc))(adapter,C.byref(desc))<0:continue
                observed.append({'name':desc.name,'vendor':desc.vendor})
                if not (desc.flags & 2):
                    matches.append({'name':desc.name,'luid':f'luid_0x{desc.luid.high&0xffffffff:08x}_0x{desc.luid.low:08x}','flags':desc.flags,'dedicated':desc.dedicated,'shared':desc.shared})
            finally:method(adapter,2,C.c_ulong)(adapter)
    finally:method(factory,2,C.c_ulong)(factory)
    matches=list({v['luid']:v for v in matches}.values())
    if not matches:raise RuntimeError('No hardware DXGI adapter; observed '+json.dumps(observed))
    return matches

class ProcessTelemetry:
    def __init__(self,pid,adapter):
        self.pid=pid;self.adapter=adapter;self.pdh=C.WinDLL('pdh.dll');self.query=C.c_void_p();self.counter=C.c_void_p()
        self.pdh.PdhOpenQueryW.argtypes=[C.c_wchar_p,C.c_size_t,C.POINTER(C.c_void_p)]
        self.pdh.PdhAddEnglishCounterW.argtypes=[C.c_void_p,C.c_wchar_p,C.c_size_t,C.POINTER(C.c_void_p)]
        self.pdh.PdhCollectQueryData.argtypes=[C.c_void_p]
        self.pdh.PdhGetFormattedCounterArrayW.argtypes=[C.c_void_p,C.c_uint32,C.POINTER(C.c_uint32),C.POINTER(C.c_uint32),C.c_void_p]
        self.pdh.PdhCloseQuery.argtypes=[C.c_void_p]
        if self.pdh.PdhOpenQueryW(None,0,C.byref(self.query)):raise RuntimeError('PDH open failed')
        if self.pdh.PdhAddEnglishCounterW(self.query,r'\GPU Engine(*)\Utilization Percentage',0,C.byref(self.counter)):raise RuntimeError('GPU engine counter unavailable')
        self.pdh.PdhCollectQueryData(self.query)
        self.gap=None;self.dropouts=0;self.cached=None;self.last_read=0
    def read(self):
        # Music renders at 8 Hz; GPU telemetry needs only 2 Hz. Reusing a
        # timestamped sample avoids polling all Windows GPU counters per note.
        if self.cached is not None and time.monotonic()-self.last_read<.5:
            return dict(self.cached,cached_sample=True)
        if self.pdh.PdhCollectQueryData(self.query):raise RuntimeError('PDH collection failed')
        size=C.c_uint32();count=C.c_uint32()
        self.pdh.PdhGetFormattedCounterArrayW(self.counter,0x200,C.byref(size),C.byref(count),None)
        buffer=C.create_string_buffer(max(1,size.value))
        rc=self.pdh.PdhGetFormattedCounterArrayW(self.counter,0x200,C.byref(size),C.byref(count),buffer)
        valid=rc==0
        if rc:
            self.dropouts+=1
            if self.gap is None:self.gap=time.monotonic()
            if time.monotonic()-self.gap>3:raise RuntimeError('Live GPU counters unavailable for three seconds')
            count.value=0
        else:self.gap=None
        usage=defaultdict(float);matches=0
        for item in C.cast(buffer,C.POINTER(Item*count.value)).contents:
            name=item.name.lower()
            if not name.startswith(f'pid_{self.pid}_') or self.adapter['luid'] not in name or item.fmt.status not in (0,1):continue
            match=re.search(r'_eng_\d+_engtype_(.+)',name)
            if match:usage[match[1]]=max(usage[match[1]],max(0,min(100,item.fmt.value)));matches+=1
        row={'timestamp':time.time(),'adapter':self.adapter['luid'],'adapter_name':self.adapter['name'],'process_id':self.pid,
                'engine_data_valid':valid,'engine_dropouts':self.dropouts,'matched_counters':matches,'usage':dict(usage),
                'gpu_pct':max(usage.values(),default=0),'memory_MiB':None,'temperature_C':None,'power_W':None,
                'measurement':'Windows PDH per-process GPU engine utilization; no inferred memory/temperature/power'}
        self.last_read=time.monotonic();self.cached=row
        return dict(row,cached_sample=False)
    def close(self):self.pdh.PdhCloseQuery(self.query)
