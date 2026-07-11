from __future__ import annotations
import json,time,uuid
from dataclasses import asdict,dataclass,field
from typing import Any
from .full_video_analyzer import BASE
from .world_planner import build_world_plan
from .roblox_template_compiler_v2 import compile_world,open_place,TEMPLATE_PATH
RUNS=BASE/'outputs'/'creator_ai_v2_runs'
@dataclass
class Stage: name:str; status:str; message:str; output:dict[str,Any]=field(default_factory=dict)
@dataclass
class Run:
    run_id:str; source_name:str; status:str; stages:list[Stage]; started_at:float; finished_at:float|None=None; error:str=''
    def save(self): RUNS.mkdir(parents=True,exist_ok=True); p=RUNS/f'{self.run_id}.json'; p.write_text(json.dumps(asdict(self),indent=2),encoding='utf-8'); return p
def generate_complete_recreation(source_name:str,open_studio:bool=True)->Run:
    run=Run(f'{int(time.time())}_{uuid.uuid4().hex[:8]}',source_name,'RUNNING',[],time.time()); run.save()
    try:
        if not TEMPLATE_PATH.exists(): raise FileNotFoundError('Install a blank Baseplate .rbxlx template once.')
        plan=build_world_plan(source_name); run.stages.append(Stage('world_planner','DONE','World layout, props, NPCs and gameplay planned.',{'scene':plan.scene_type,'zones':len(plan.zones),'npcs':len(plan.npc_specs)})); run.save()
        compiled=compile_world(source_name,plan); run.stages.append(Stage('project_compiler','DONE','Playable Roblox project compiled and validated.',asdict(compiled))); run.save()
        if not compiled.valid: raise RuntimeError('; '.join(compiled.errors))
        if open_studio: open_place(compiled.place_path); run.stages.append(Stage('studio_sync','DONE','Generated place opened in Roblox Studio.',{'place_path':compiled.place_path})); run.save()
        run.status='COMPLETED'; run.finished_at=time.time(); run.save(); return run
    except Exception as e:
        run.status='FAILED'; run.error=str(e); run.finished_at=time.time(); run.stages.append(Stage('error','FAILED',str(e))); run.save(); raise
def list_runs(limit=100):
    rows=[]
    if RUNS.exists():
        for p in RUNS.glob('*.json'):
            try: rows.append(json.loads(p.read_text(encoding='utf-8')))
            except Exception: pass
    return sorted(rows,key=lambda x:x.get('started_at',0),reverse=True)[:limit]
