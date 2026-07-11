from __future__ import annotations
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from .full_video_analyzer import BASE
from .roblox_brain import build_roblox_brain_plan, load_roblox_brain_plan
OUTPUT_DIR = BASE / "outputs" / "world_plans"
@dataclass
class Zone:
    zone_id: str; kind: str; center: tuple[float,float,float]; size: tuple[float,float,float]; purpose: str; props: list[str]=field(default_factory=list)
@dataclass
class WorldPlan:
    source_name: str; scene_type: str; layout_style: str; zones: list[Zone]; player_path: list[tuple[float,float,float]]; props: list[dict[str,Any]]; hazards: list[dict[str,Any]]; npc_specs: list[dict[str,Any]]; gameplay_specs: list[dict[str,Any]]; camera_specs: list[dict[str,Any]]; lighting: str; confidence: int; warnings: list[str]
    def save(self)->Path:
        OUTPUT_DIR.mkdir(parents=True,exist_ok=True); safe=''.join(c if c.isalnum() or c in '-_' else '_' for c in Path(self.source_name).stem); p=OUTPUT_DIR/f'{safe}.world_plan.json'; p.write_text(json.dumps(asdict(self),indent=2,ensure_ascii=False),encoding='utf-8'); return p
def z(i,k,c,s,p,props=None): return Zone(i,k,tuple(c),tuple(s),p,list(props or []))
def build_world_plan(source_name:str)->WorldPlan:
    brain=load_roblox_brain_plan(source_name) or build_roblox_brain_plan(source_name); scene=brain.scene.value; zones=[]; path=[]; props=[]; hazards=[]; npcs=[]
    if scene=='hospital':
        zones=[z('reception','room',(0,4,0),(36,8,26),'opening',['desk','chairs']),z('hallway','corridor',(0,4,30),(16,8,34),'movement',['doors','lights']),z('treatment','room',(0,4,56),(30,8,22),'reveal',['beds','monitor'])]; path=[(0,2,-8),(0,2,8),(0,2,28),(0,2,48),(0,2,58)]; props=[{'type':'hospital_bed','position':[-7,2,56]},{'type':'hospital_bed','position':[7,2,56]},{'type':'reception_desk','position':[0,2,4]}]
    elif scene=='horror_corridor':
        zones=[z('entry','corridor',(0,4,0),(16,8,30),'setup'),z('middle','corridor',(0,4,32),(16,8,34),'tension'),z('reveal','room',(0,4,62),(24,8,22),'monster reveal')]; path=[(0,2,-10),(0,2,12),(0,2,32),(0,2,52),(0,2,64)]; npcs=[{'type':'monster','position':[0,2,62],'behavior':'chase','speed':14}]
    elif scene=='simple_obby':
        zones=[z('course','obby',(40,6,0),(90,20,24),'main gameplay')]; path=[(i*10,2+(i%3)*2,0) for i in range(10)]; hazards=[{'type':'kill_block','position':[25,1,0],'size':[8,1,8]},{'type':'kill_block','position':[65,1,0],'size':[8,1,8]}]
    elif scene=='city':
        zones=[z('street','road',(0,1,0),(90,2,20),'movement'),z('plaza','open_area',(0,1,38),(50,2,38),'showcase')]; path=[(0,2,-35),(0,2,-10),(0,2,10),(0,2,30),(0,2,42)]; props=[{'type':'building','position':[-25,8,0]},{'type':'building','position':[25,8,0]}]
    else:
        zones=[z('showcase','platform',(0,1,0),(60,2,60),'avatar showcase')]; path=[(0,2,-18),(0,2,-4),(0,2,10),(8,2,18)]; props=[{'type':'accent_platform','position':[0,1,0]},{'type':'scale_marker','position':[8,1,10]}]
    actions=[x.value for x in brain.state_actions+brain.event_actions]; gameplay=[{'action':a,'properties':{}} for a in actions]
    if 'grow' in actions: gameplay.append({'action':'grow','properties':{'target_scale':brain.character_state.get('scale',2)}})
    if 'chase' in actions and not npcs: npcs.append({'type':'npc','position':[0,2,25],'behavior':'chase','speed':12})
    camera=[{'type':brain.camera.value,'start':0,'end':brain.duration},{'type':brain.camera_pattern.get('dominant_pattern','none'),'interval':brain.camera_pattern.get('average_interval'),'occurrences':brain.camera_pattern.get('occurrences',0)}]
    plan=WorldPlan(source_name,scene,'linear_short_form',zones,path,props,hazards,npcs,gameplay,camera,brain.lighting,brain.overall_confidence,[]); plan.save(); return plan
