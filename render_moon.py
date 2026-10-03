#!/usr/bin/env python3
"""Offline Linux renderer specifically for Moon Workshop 3453730450.
Uses original meshes/textures, with adapted shaders and explicitly ported motion.
Does not execute embedded scripts or reproduce every Wallpaper Engine effect.
"""
import argparse
import io
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import math
import tempfile
import time

import lz4.block
import moderngl
import numpy as np
from PIL import Image

class FormatError(ValueError):
    pass

class Reader:
    def __init__(self, data): self.data=data; self.pos=0
    def take(self,n):
        if n < 0 or self.pos+n > len(self.data): raise FormatError('Truncated asset')
        out=self.data[self.pos:self.pos+n];self.pos+=n;return out
    def u32(self): return struct.unpack('<I',self.take(4))[0]
    def cstring(self):
        end=self.data.find(b'\0',self.pos)
        if end<0:raise FormatError('Unterminated string')
        return self.take(end-self.pos+1)[:-1].decode('utf8')

def unpack(path):
    """Read package entries in memory; never execute scripts or extract paths."""
    r=Reader(Path(path).read_bytes());version=r.take(r.u32())
    if version!=b'PKGV0022':raise FormatError(f'Expected PKGV0022, got {version!r}')
    count=r.u32()
    if count>10000:raise FormatError('Too many entries')
    entries=[]
    for _ in range(count):
        name=r.take(r.u32()).decode('utf8');offset=r.u32();size=r.u32()
        entries.append((name,offset,size))
    base=r.pos
    assets={}
    for name,off,size in entries:
        if base+off+size>len(r.data):raise FormatError('Package offset out of range')
        if name in assets:raise FormatError('Duplicate package path')
        assets[name]=r.data[base+off:base+off+size]
    return assets

def tex_image(data):
    r=Reader(data)
    if r.take(9)!=b'TEXV0005\0' or r.take(9)!=b'TEXI0001\0':raise FormatError('Unsupported texture header')
    fmt=r.u32(); flags=r.u32();r.take(20)
    if r.take(9)!=b'TEXB0004\0':raise FormatError('Only TEXB0004 supported')
    count=r.u32();imagefmt=r.u32();r.u32();mips=r.u32()
    w,h,compressed,rawlen,size=[r.u32() for _ in range(5)]
    if w>16384 or h>16384 or not w or not h:raise FormatError('Invalid texture dimensions')
    payload=r.take(size)
    if compressed:payload=lz4.block.decompress(payload,uncompressed_size=rawlen)
    if imagefmt!=0xffffffff:
        image=Image.open(io.BytesIO(payload));image.load();return image.convert('RGBA')
    if fmt==8:
        rg=np.frombuffer(payload,np.uint8).reshape(h,w,2)
        rgb=np.zeros((h,w,4),np.uint8);rgb[:,:,:2]=rg;rgb[:,:,2]=255;rgb[:,:,3]=255
        return Image.fromarray(rgb)
    if fmt==9:return Image.frombytes('L',(w,h),payload).convert('RGBA')
    if fmt in (4,6,7):
        code,label={4:(3,'DXT5'),6:(2,'DXT3'),7:(1,'DXT1')}[fmt]
        return Image.frombytes('RGBA',(w,h),payload,'bcn',(code,label))
    if fmt==0:return Image.frombytes('RGBA',(w,h),payload)
    raise FormatError(f'Unsupported raw texture format {fmt}')

def model_meshes(data):
    r=Reader(data)
    if r.take(9)!=b'MDLV0023\0':raise FormatError('Expected MDLV0023')
    r.u32();r.u32();count=r.u32()
    if count>100:raise FormatError('Invalid mesh count')
    meshes=[]
    for _ in range(count):
        material=r.cstring();r.u32();r.take(24)
        flags=r.u32();size=r.u32()
        if flags!=15 or size%48:raise FormatError('Unsupported vertex layout')
        verts=np.frombuffer(r.take(size),'<f4').reshape(-1,12).copy()
        size=r.u32()
        if size%2:raise FormatError('Invalid index buffer')
        inds=np.frombuffer(r.take(size),'<u2').copy()
        if len(inds)%3 or (len(inds) and inds.max()>=len(verts)):raise FormatError('Invalid triangle indices')
        r.take(6)
        meshes.append((material,verts,inds))
    return meshes

def rotations(x,y,z):
    cx,sx=math.cos(x),math.sin(x);cy,sy=math.cos(y),math.sin(y);cz,sz=math.cos(z),math.sin(z)
    rx=np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]],np.float32)
    ry=np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]],np.float32)
    rz=np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]],np.float32)
    return rz@ry@rx

def transform(scale=(1,1,1), angles=(0,0,0), position=(0,0,0)):
    out=np.eye(4,dtype=np.float32);out[:3,:3]=rotations(*angles)@np.diag(scale);out[:3,3]=position;return out

def perspective(fov,aspect,near=.01,far=100):
    f=1/math.tan(math.radians(fov)/2)
    return np.array([[f/aspect,0,0,0],[0,f,0,0],[0,0,(far+near)/(near-far),2*far*near/(near-far)],[0,0,-1,0]],np.float32)

def look_at(eye,target):
    eye=np.array(eye,np.float32);target=np.array(target,np.float32)
    f=target-eye;f/=np.linalg.norm(f);right=np.cross(f,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,f)
    m=np.eye(4,dtype=np.float32);m[:3,:3]=np.array([right,up,-f]);m[:3,3]=-m[:3,:3]@eye;return m

VERT='''#version 330
in vec3 position; in vec3 normal; in vec4 tangent; in vec2 uv;
uniform mat4 model; uniform mat4 vp;
out vec3 world; out vec3 n; out vec3 t; out vec3 b; out vec2 coord;
void main(){ vec4 w=model*vec4(position,1); world=w.xyz;
 mat3 nm=transpose(inverse(mat3(model))); n=normalize(nm*normal);
 t=normalize(mat3(model)*tangent.xyz); b=normalize(cross(n,t)*tangent.w);
 coord=uv; gl_Position=vp*w; }
'''
FRAG='''#version 330
in vec3 world; in vec3 n; in vec3 t; in vec3 b; in vec2 coord;
uniform sampler2D albedo; uniform sampler2D normalmap;
uniform bool use_normal; uniform vec3 tint; uniform float brightness;
out vec4 color;
void main(){ vec3 N=normalize(n);
 if(use_normal){ vec2 xy=texture(normalmap,coord).rg*2-1;
 vec3 local=vec3(xy,sqrt(max(0.0,1-dot(xy,xy))));N=normalize(mat3(normalize(t),normalize(b),N)*local); }
 vec3 light=normalize(vec3(9,9,5)-world);
 float diffuse=max(dot(N,light),0.0);
 vec3 base=texture(albedo,coord).rgb*tint;
 float rim=pow(1.0-max(dot(N,normalize(vec3(0,0,9)-world)),0.0),3.0)*.07;
 vec3 lit=base*(.20+diffuse*.95)*brightness+base*rim;
 color=vec4(clamp(lit,0,1),1); }
'''
BG_VERT='''#version 330
in vec2 position; out vec2 uv;
void main(){ uv=position*.5+.5;gl_Position=vec4(position,0,1); }
'''
BG_FRAG='''#version 330
in vec2 uv; uniform sampler2D stars; uniform float seconds; out vec4 color;
void main(){ vec2 coord=vec2(uv.x,1-uv.y)+vec2(seconds*.002,seconds*.001);
 vec3 base=texture(stars,coord).rgb;
 float gradient=.025+.075*pow(max(0.0,uv.x*.6+uv.y*.4),2.0);
 color=vec4(base*.65+vec3(gradient),1); }
'''

class MoonRenderer:
    def __init__(self,assets,width,height,camera=6.0,msaa=4,supersample=1):
        self.assets=assets; self.width=width;self.height=height;self.camera=camera
        self.ctx=moderngl.create_standalone_context(backend='egl')
        print('OpenGL renderer:',self.ctx.info['GL_RENDERER'],flush=True)
        self.render_width=width*supersample;self.render_height=height*supersample
        size=(self.render_width,self.render_height)
        limit=self.ctx.info['GL_MAX_RENDERBUFFER_SIZE']
        if max(size)>limit:raise ValueError(f'Render dimensions {size} exceed GPU limit {limit}; reduce resolution or supersampling')
        maximum=self.ctx.max_samples
        self.samples=max((n for n in (0,2,4,8) if n<=msaa and n<=maximum),default=0)
        if self.samples!=msaa:print(f'MSAA {msaa} unavailable; using {self.samples} samples',flush=True)
        self.framebuffer=self.ctx.simple_framebuffer(size,components=3,samples=self.samples)
        self.resolved=self.ctx.simple_framebuffer(size,components=3) if self.samples else self.framebuffer
        self.framebuffer.use();self.ctx.viewport=(0,0,*size)
        print(f'Output: {width}x{height}; render: {size[0]}x{size[1]}; MSAA: {self.samples}x',flush=True)
        self.program=self.ctx.program(vertex_shader=VERT,fragment_shader=FRAG)
        self.program['albedo']=0;self.program['normalmap']=1
        self.white=self.ctx.texture((1,1),4,bytes([255,255,255,255]))
        self.flat=self.ctx.texture((1,1),4,bytes([128,128,255,255]))
        self.textures={};self.models={}
        for name in ['models/model/model.mdl','models/TY/TY.mdl','models/LP/LP.mdl']:
            meshes=[]
            for material,verts,inds in model_meshes(assets[name]):
                mat=json.loads(assets[material])['passes'][0]
                textures=mat.get('textures',[])
                alb=self.texture(textures[0]) if textures and textures[0] else self.white
                normal=self.texture(textures[1]) if len(textures)>1 and textures[1] else self.flat
                tint=mat.get('constantshadervalues',{}).get('Color','1 1 1')
                if name.endswith('LP.mdl'):tint='0.596 0.596 0.596'
                vbo=self.ctx.buffer(verts.tobytes());ibo=self.ctx.buffer(inds.tobytes())
                vao=self.ctx.vertex_array(self.program,[(vbo,'3f 3f 4f 2f','position','normal','tangent','uv')],ibo,index_element_size=2)
                meshes.append((vao,alb,normal,normal!=self.flat,tuple(map(float,tint.split()))))
            self.models[name]=meshes
        bg=self.ctx.program(vertex_shader=BG_VERT,fragment_shader=BG_FRAG)
        self.bg_program=bg;bg['stars']=0
        self.bg_vao=self.ctx.vertex_array(bg,[(self.ctx.buffer(np.array([-1,-1,1,-1,-1,1,1,1],np.float32).tobytes()),'2f','position')])
        self.bg_texture=self.texture('moon_BBB')
        # Reference preview composition: moon lower than the live clock.
        vp=perspective(50,width/height)@look_at((0,.65,camera),(0,.65,0))
        self.program['vp'].write(vp.T.astype('f4').tobytes())
    def texture(self,name):
        if name in self.textures:return self.textures[name]
        key='materials/'+name+'.tex'
        if key not in self.assets:raise FormatError('Missing texture '+key)
        image=tex_image(self.assets[key]); image=image.convert('RGBA')
        texture=self.ctx.texture(image.size,4,image.tobytes())
        texture.repeat_x=True;texture.repeat_y=True;texture.build_mipmaps()
        texture.filter=(moderngl.LINEAR_MIPMAP_LINEAR,moderngl.LINEAR)
        self.textures[name]=texture;return texture
    def draw(self,name,matrix,brightness=1):
        self.program['model'].write(matrix.T.astype('f4').tobytes());self.program['brightness']=brightness
        for vao,alb,normal,use_normal,tint in self.models[name]:
            alb.use(0);normal.use(1);self.program['use_normal']=use_normal;self.program['tint']=tint
            vao.render()
    def frame(self,seconds,orbits=True):
        self.framebuffer.use();self.framebuffer.clear(.01,.01,.01,depth=1)
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.bg_program['seconds']=seconds;self.bg_texture.use(0);self.bg_vao.render(moderngl.TRIANGLE_STRIP)
        self.ctx.enable(moderngl.DEPTH_TEST)
        deg=math.pi/180
        # The original SceneScript uses degrees for rotation updates.
        moon_angles=((10+10*math.cos(seconds*.05))*deg, seconds*(.2*2000/30)*deg,
                     (-15+10*math.sin(seconds*.05))*deg)
        self.draw('models/model/model.mdl',transform((1.5,)*3,moon_angles))
        if orbits:
            for radius,speed,tilts,offset,scale,axis in [
                (5.5,-.48,(85,0,-10),(-.7,0,0),(.5,.5,.5),1),
                (8.2,-.25,(90,0,-20),(0,0,0),(.7,.7,.6),2),
                (5,-.55,(90,180,-20),(0,0,0),(.2,.2,.2),0)]:
                tilt=rotations(*(v*deg for v in tilts))
                pos=tilt@np.array([radius*math.cos(speed*seconds),radius*math.sin(speed*seconds),0])+offset
                angles=[0,0,0];angles[axis]=seconds*(2000/30)*deg
                self.draw('models/LP/LP.mdl',transform(scale,angles,pos))
            pos=rotations(85*deg,0,-15*deg)@np.array([4.1*math.cos(.618*seconds),4.1*math.sin(.618*seconds),0])
            direction=-pos; yaw=math.atan2(direction[2],direction[0]);pitch=-math.atan2(direction[1],math.hypot(direction[0],direction[2]))
            self.draw('models/TY/TY.mdl',transform((.00025,)*3,(-math.pi/2-yaw,-pitch,75*deg),pos),1.2)
        if self.samples:self.ctx.copy_framebuffer(self.resolved,self.framebuffer)
        return self.resolved.read(components=3,alignment=1)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scene_pkg');parser.add_argument('output',help='Output MP4 (or PNG with --preview)')
    parser.add_argument('--width',type=int,default=1920);parser.add_argument('--height',type=int,default=1080)
    parser.add_argument('--seconds',type=float,default=30);parser.add_argument('--fps',type=int,default=30)
    parser.add_argument('--msaa',type=int,choices=[0,2,4,8],default=4,help='Edge antialiasing samples; 0 disables it (default: 4)')
    parser.add_argument('--supersample',type=int,choices=[1,2],default=1,help='Render at 1x or 2x width/height, then downsample (default: 1)')
    parser.add_argument('--camera',type=float,default=6,help='Camera distance; smaller makes the moon larger')
    parser.add_argument('--start',type=float,default=0,help='Start time for motion; camera intro is omitted')
    parser.add_argument('--no-orbits',action='store_true');parser.add_argument('--preview',action='store_true')
    parser.add_argument('--overwrite',action='store_true');parser.add_argument('--crf',type=int,default=18)
    args=parser.parse_args()
    if args.width<2 or args.height<2 or args.width%2 or args.height%2:parser.error('Dimensions must be positive even numbers')
    if not all(math.isfinite(v) for v in (args.seconds,args.camera,args.start)) or not 1<=args.fps<=120 or args.seconds<=0 or args.camera<=2:parser.error('Invalid FPS, duration, or camera distance')
    if not 0<=args.crf<=51:parser.error('CRF must be 0–51')
    output=Path(args.output).expanduser().resolve()
    if output.exists() and not args.overwrite:parser.error('Output exists; use --overwrite')
    if output==Path(args.scene_pkg).expanduser().resolve():parser.error('Input and output must differ')
    if output.suffix.lower() != ('.png' if args.preview else '.mp4'):parser.error('Output must be .png for preview or .mp4 for video')
    output.parent.mkdir(parents=True,exist_ok=True)
    source=Path(args.scene_pkg).expanduser()
    if source.is_dir():source=source/'scene.pkg'
    renderer=MoonRenderer(unpack(source),args.width,args.height,args.camera,args.msaa,args.supersample)
    print('Original mesh and textures loaded. Using adapted lighting/effects.',flush=True)
    if args.preview:
        data=renderer.frame(args.start,not args.no_orbits)
        im=Image.frombytes('RGB',(renderer.render_width,renderer.render_height),data).transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        if args.supersample>1:im=im.resize((args.width,args.height),Image.Resampling.LANCZOS)
        im.save(output);print('Saved',output);return
    if not shutil.which('ffmpeg'):parser.error('Install ffmpeg')
    fd,staging=tempfile.mkstemp(prefix='.moon-',suffix='.mp4',dir=output.parent);os.close(fd)
    process=None
    try:
        command=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgb24',
                 '-video_size',f'{renderer.render_width}x{renderer.render_height}','-framerate',str(args.fps),'-i','pipe:0',
                 '-vf',f'vflip,scale={args.width}:{args.height}:flags=lanczos,setsar=1','-an','-c:v','libx264','-preset','veryfast','-crf',str(args.crf),'-pix_fmt','yuv420p',
                 '-movflags','+faststart',staging]
        process=subprocess.Popen(command,stdin=subprocess.PIPE)
        count=max(1,round(args.seconds*args.fps));start=time.monotonic()
        for i in range(count):
            data=renderer.frame(args.start+i/args.fps,not args.no_orbits)
            process.stdin.write(data)
            if i%args.fps==0:print(f'{i}/{count} frames ({time.monotonic()-start:.1f}s elapsed)',flush=True)
        process.stdin.close()
        if process.wait():raise RuntimeError('FFmpeg encoding failed')
        if args.overwrite:os.replace(staging,output)
        else:os.link(staging,output);os.unlink(staging)
        print('Saved',output,flush=True)
    finally:
        if process and process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        Path(staging).unlink(missing_ok=True)

if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:raise SystemExit('Cancelled; unfinished output removed.')
    except Exception as e:raise SystemExit(f'Render failed: {e}')
