"""Read local Steam libraries and Wallpaper Engine configuration; never write them."""
import json
from pathlib import Path
import re


def read_vdf(path):
    text = path.read_text(encoding='utf-8-sig',errors='replace')
    tokens = re.finditer(r'"((?:\\.|[^"\\])*)"|([{}])|(?://[^\n]*)',text)
    flat=[]
    for token in tokens:
        value,brace=token.groups()
        if brace:flat.append(brace)
        elif value is not None:flat.append(re.sub(r'\\([\\"])',r'\1',value))
    pos=0
    def parse():
        nonlocal pos
        result={}
        while pos<len(flat):
            key=flat[pos];pos+=1
            if key=='}':return result
            if pos>=len(flat):break
            value=flat[pos];pos+=1
            result[key]=parse() if value=='{' else value
        return result
    return parse()


def steam_libraries(extra=(),home=None):
    home=Path(home or Path.home())
    seeds=[home/'.local/share/Steam', home/'.steam/steam',home/'.steam/root',
           home/'.var/app/com.valvesoftware.Steam/.local/share/Steam']
    seeds += [Path(p).expanduser() for p in extra if p]
    result=set()
    for seed in seeds:
        seed=seed.resolve()
        if seed.name=='steamapps':seed=seed.parent
        if (seed/'steamapps').is_dir():result.add(seed)
        config=seed/'steamapps/libraryfolders.vdf'
        if not config.is_file():continue
        try:values=read_vdf(config).get('libraryfolders',{})
        except (OSError,ValueError):continue
        for key,value in values.items():
            if not key.isdigit():continue
            path=value.get('path') if isinstance(value,dict) else value
            if path and (Path(path)/'steamapps').is_dir():result.add(Path(path).resolve())
    return sorted(result)


def scan(extra=(),home=None):
    libraries=steam_libraries(extra,home)
    roots=[];configs=[];assets=[]
    for library in libraries:
        apps=library/'steamapps'
        roots.append(apps/'workshop/content/431960')
        install=apps/'common/wallpaper_engine'
        manifest=apps/'appmanifest_431960.acf'
        if manifest.is_file():
            try:
                name=read_vdf(manifest).get('AppState',{}).get('installdir')
                if name and (apps/'common'/name).resolve().is_relative_to((apps/'common').resolve()):install=apps/'common'/name
            except (OSError,ValueError):pass
        roots.extend([install/'projects/myprojects',install/'projects/defaultprojects'])
        if (install/'config.json').is_file():configs.append(install/'config.json')
        if (install/'assets').is_dir():assets.append(install/'assets')
    for p in extra:
        if not p:continue
        p=Path(p).expanduser().resolve()
        if p.is_dir():roots.append(p)
    projects={};warnings=[]
    for root in set(roots):
        if not root.is_dir():continue
        candidates=[root/'project.json'] if (root/'project.json').is_file() else root.glob('*/project.json')
        for path in candidates:
            try:
                data=json.loads(path.read_text(encoding='utf-8-sig'))
                projects[str(path.parent.resolve())]={'path':str(path.parent.resolve()),
                    'title':str(data.get('title',path.parent.name)),
                    'type':str(data.get('type','unknown')),
                    'id':str(data.get('workshopid',path.parent.name))}
            except (OSError,ValueError,AttributeError) as e:warnings.append(f'{path.parent.name}: {e}')
    ordered=sorted(projects.values(),key=lambda p:(p['title'].casefold(),p['path']))
    active=[]
    byid={}
    for item in ordered:byid.setdefault(item['id'],[]).append(item['path'])
    def match(value):
        if isinstance(value,dict):
            # Ignore playlists: their file lists do not identify the active item.
            for k,v in value.items():
                if 'playlist' not in k.lower():match(v)
        elif isinstance(value,list):
            for v in value:match(v)
        elif isinstance(value,str):
            normalized=value.replace('\\','/')
            for key in re.findall(r'(?:^|/)431960/(\d+)(?:/|$)',normalized):active.extend(byid.get(key,[]))
            if normalized.isdigit():active.extend(byid.get(normalized,[]))
            path=Path(normalized).expanduser()
            if path.is_absolute():
                parent=path if path.is_dir() else path.parent
                if str(parent.resolve()) in projects:active.append(str(parent.resolve()))
    def selected(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k.lower()=='selectedwallpapers':match(v)
                elif k.lower() not in {'profiles','presets','playlists'}:selected(v)
    for config in configs:
        try:selected(json.loads(config.read_text(encoding='utf-8-sig')))
        except (OSError,ValueError):warnings.append('Wallpaper Engine config is not readable yet; it may be updating.')
    return {'projects':ordered,'active':list(dict.fromkeys(active)),
            'assets':[str(p) for p in assets], 'libraries':[str(p) for p in libraries], 'warnings':warnings}
