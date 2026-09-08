#!/usr/bin/env python3
import os, sys, time, subprocess, tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from PIL import Image, ImageTk, ImageDraw, ImageFont

ROOT = Path('/mnt/data/ubuntu-desktop-workspace')
HOME = ROOT / 'home'
DISPLAY = os.environ.get('DISPLAY', ':88')
W, H = 1440, 900
TOP = 32
DOCK_W = 74
BG = '#2c001e'
PANEL = '#1f1721'
DOCK = '#21131f'
ORANGE = '#e95420'
TEXT = '#f7f3f7'
MUTED = '#cbbfca'

os.environ['HOME'] = str(HOME)
HOME.mkdir(parents=True, exist_ok=True)

def find_font(size, bold=False):
    choices = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf' if bold else '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf',
    ]
    for p in choices:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def make_wallpaper(path):
    if path.exists():
        return
    im = Image.new('RGB', (W,H), '#2c001e')
    px = im.load()
    for y in range(H):
        for x in range(W):
            # Ubuntu-like aubergine gradient with a subtle orange bloom.
            t = x / max(1, W-1)
            u = y / max(1, H-1)
            r = int(44 + 35*t + 22*(1-u))
            g = int(0 + 7*t)
            b = int(30 + 42*t + 18*u)
            # radial orange glow in upper-right quadrant
            dx = (x - W*0.78)/(W*0.55)
            dy = (y - H*0.28)/(H*0.55)
            glow = max(0.0, 1.0 - (dx*dx + dy*dy))
            r = min(255, int(r + 105*glow))
            g = min(255, int(g + 38*glow))
            b = min(255, int(b + 6*glow))
            px[x,y] = (r,g,b)
    d = ImageDraw.Draw(im)
    f1 = find_font(38, True)
    f2 = find_font(18, False)
    d.text((110, H-125), 'Ubuntu 24.04 Workspace', font=f1, fill=(255,255,255))
    d.text((112, H-77), 'Local offline desktop session', font=f2, fill=(230,218,228))
    im.save(path)

WALLPAPER = ROOT/'assets'/'wallpaper.png'
WALLPAPER.parent.mkdir(parents=True, exist_ok=True)
make_wallpaper(WALLPAPER)

root = tk.Tk()
root.title('Ubuntu Workspace Desktop')
root.geometry(f'{W}x{H}+0+0')
root.overrideredirect(True)
root.configure(bg=BG)
root.lower()

wall_img = ImageTk.PhotoImage(Image.open(WALLPAPER))
bg = tk.Label(root, image=wall_img, bd=0)
bg.place(x=0,y=0,width=W,height=H)

# desktop icons
icons_frame = tk.Frame(root, bg=BG, bd=0, highlightthickness=0)
icons_frame.place(x=DOCK_W+38, y=TOP+38, width=150, height=240)
# Make the icon frame blend by sampling close dark tone.
icons_frame.configure(bg='#4d153c')

def launch(cmd, **kwargs):
    env = os.environ.copy()
    env['DISPLAY'] = DISPLAY
    env['HOME'] = str(HOME)
    try:
        subprocess.Popen(cmd, env=env, start_new_session=True, **kwargs)
    except Exception as e:
        messagebox.showerror('Launch failed', str(e))

def terminal():
    launch(['xterm','-title','Ubuntu Terminal','-geometry','100x28+205+120',
            '-fa','DejaVu Sans Mono','-fs','11','-bg','#300a24','-fg','#eeeeec',
            '-e','bash','-lc',"printf '\\033[1;38;5;208mUbuntu 24.04 Workspace\\033[0m\\n'; printf 'Offline local desktop session • DISPLAY=%s\\n\\n' \"$DISPLAY\"; cd /mnt/data; exec bash"])

def browser():
    local = ROOT/'home.html'
    launch(['chromium','--no-sandbox','--disable-dev-shm-usage','--disable-gpu',
            f'--user-data-dir={ROOT / "profile"}', '--new-window', local.as_uri()])

def graphics():
    cmd = "source /mnt/data/graphics-workspace/graphics-env.sh; export DISPLAY='%s'; echo 'Starting Vulkan cube on Ubuntu workspace display...'; vkcube" % DISPLAY
    launch(['xterm','-title','Vulkan Graphics','-geometry','80x16+300+180','-bg','#300a24','-fg','#eeeeec','-e','bash','-lc',cmd])

def reaper():
    launch([str(ROOT/'bin'/'launch-reaper.sh')])

def system_info():
    win=tk.Toplevel(root); win.title('Settings — About'); win.geometry('620x430+400+190'); win.configure(bg='#f7f7f7')
    tk.Label(win,text='Ubuntu 24.04 Workspace',font=('DejaVu Sans',22,'bold'),bg='#f7f7f7',fg='#2c001e').pack(pady=(30,8))
    tk.Label(win,text='Local offline desktop session',font=('DejaVu Sans',12),bg='#f7f7f7',fg='#666').pack()
    box=tk.Frame(win,bg='white',highlightbackground='#ddd',highlightthickness=1); box.pack(fill='x',padx=34,pady=28)
    rows=[('Operating-system media','Ubuntu 24.04.4 amd64 netboot staged'),('Window manager','Openbox'),('Display',DISPLAY+' — 1440×900×24'),('Graphics','Vulkan llvmpipe / Mesa workspace'),('Audio','Project audio workspace configured'),('REAPER','7.79 native Linux x86_64'),('Network','Offline in current container')]
    for k,v in rows:
        r=tk.Frame(box,bg='white'); r.pack(fill='x',padx=18,pady=8)
        tk.Label(r,text=k,width=22,anchor='w',bg='white',font=('DejaVu Sans',10,'bold')).pack(side='left')
        tk.Label(r,text=v,anchor='w',bg='white',fg='#444').pack(side='left',fill='x',expand=True)

def file_browser(path=Path('/mnt/data')):
    win=tk.Toplevel(root); win.title('Files'); win.geometry('820x560+285+135'); win.configure(bg='#f5f5f5')
    cur = tk.StringVar(value=str(path))
    top=tk.Frame(win,bg='#3a2f3b'); top.pack(fill='x')
    path_label=tk.Label(top,textvariable=cur,bg='#3a2f3b',fg='white',font=('DejaVu Sans',10,'bold'),anchor='w',padx=16,pady=12); path_label.pack(fill='x')
    body=tk.Frame(win,bg='white'); body.pack(fill='both',expand=True)
    listbox=tk.Listbox(body,font=('DejaVu Sans Mono',11),bd=0,highlightthickness=0,selectbackground='#e95420',selectforeground='white'); listbox.pack(side='left',fill='both',expand=True,padx=(14,0),pady=14)
    sb=tk.Scrollbar(body,command=listbox.yview); sb.pack(side='right',fill='y'); listbox.config(yscrollcommand=sb.set)
    entries=[]
    def load(p):
        nonlocal entries
        p=Path(p)
        if not p.exists() or not p.is_dir(): return
        cur.set(str(p)); listbox.delete(0,'end'); entries=[]
        if p != Path('/'):
            entries.append(('..',p.parent,True)); listbox.insert('end','📁  ..')
        for child in sorted(p.iterdir(), key=lambda q:(not q.is_dir(), q.name.lower())):
            try:
                isdir=child.is_dir()
            except Exception:
                isdir=False
            entries.append((child.name,child,isdir))
            prefix='📁  ' if isdir else '    '
            listbox.insert('end',prefix+child.name)
    def open_selected(evt=None):
        sel=listbox.curselection()
        if not sel: return
        _,p,isdir=entries[sel[0]]
        if isdir: load(p)
        else:
            if p.suffix.lower() in ('.html','.htm','.png','.jpg','.jpeg','.webp','.pdf','.txt','.md'):
                launch(['chromium','--no-sandbox','--disable-gpu','--new-window',p.as_uri()])
            else:
                launch(['xterm','-title',p.name,'-e','bash','-lc',f"cd {str(p.parent)!r}; ls -lh {p.name!r}; echo; file {p.name!r}; exec bash"])
    listbox.bind('<Double-Button-1>',open_selected)
    load(path)

def shutdown():
    if messagebox.askyesno('End session','End the Ubuntu workspace desktop session?'):
        root.destroy()

# desktop shortcuts
for text, cmd in [('Home', lambda: file_browser(HOME)), ('Workspace', lambda: file_browser(Path('/mnt/data'))), ('REAPER', reaper), ('Terminal', terminal)]:
    b=tk.Button(icons_frame,text='▣\n'+text,command=cmd,width=10,height=3,bg='#4d153c',fg='white',activebackground='#683050',activeforeground='white',relief='flat',font=('DejaVu Sans',10,'bold'))
    b.pack(pady=4)

# top panel
panel=tk.Toplevel(root); panel.overrideredirect(True); panel.geometry(f'{W}x{TOP}+0+0'); panel.configure(bg=PANEL); panel.attributes('-topmost',True)
activities=tk.Button(panel,text='Activities',command=lambda: None,bg=PANEL,fg=TEXT,activebackground='#3a303a',activeforeground='white',relief='flat',font=('DejaVu Sans',10,'bold')); activities.pack(side='left',padx=(10,0),fill='y')
app=tk.Label(panel,text='Ubuntu Workspace',bg=PANEL,fg=MUTED,font=('DejaVu Sans',10)); app.pack(side='left',padx=18)
clock=tk.Label(panel,text='',bg=PANEL,fg=TEXT,font=('DejaVu Sans',10,'bold')); clock.pack(side='right',padx=18)
status=tk.Label(panel,text='🔊   ◉',bg=PANEL,fg=TEXT,font=('DejaVu Sans',10)); status.pack(side='right',padx=4)

def tick():
    clock.config(text=time.strftime('%a %b %d   %H:%M'))
    root.after(1000,tick)
tick()

# left dock
Dock=tk.Toplevel(root); Dock.overrideredirect(True); Dock.geometry(f'{DOCK_W}x{H-TOP}+0+{TOP}'); Dock.configure(bg=DOCK); Dock.attributes('-topmost',True)

def dock_button(label, glyph, command):
    b=tk.Button(Dock,text=glyph+'\n'+label,command=command,bg=DOCK,fg=TEXT,activebackground='#4b3243',activeforeground='white',relief='flat',bd=0,font=('DejaVu Sans',9,'bold'),height=3,width=8)
    b.pack(pady=5,padx=5)
    return b

dock_button('Files','▰',lambda:file_browser(Path('/mnt/data')))
dock_button('REAPER','R',reaper)
dock_button('Terminal','>_',terminal)
dock_button('Web','◎',browser)
dock_button('Vulkan','◇',graphics)
dock_button('Settings','⚙',system_info)
tk.Frame(Dock,bg=DOCK).pack(fill='both',expand=True)
dock_button('Power','⏻',shutdown)

# local home page for browser
home_html = ROOT/'home.html'
home_html.write_text('''<!doctype html><meta charset="utf-8"><title>Ubuntu Workspace</title><style>body{margin:0;background:#2c001e;color:#fff;font-family:Ubuntu,Arial,sans-serif}main{max-width:900px;margin:12vh auto;padding:50px}h1{font-size:50px;margin:0 0 16px}.o{color:#e95420}.card{background:#fff1;padding:28px;border-radius:16px;margin-top:32px;line-height:1.7}code{background:#0005;padding:4px 8px;border-radius:5px}</style><main><h1><span class=o>Ubuntu</span> Workspace</h1><p>Local offline desktop session</p><div class=card><b>Desktop setup is running.</b><br>Open REAPER 7.79, Terminal, Files, Settings, or the Vulkan graphics test from the dock.<br><br>Workspace: <code>/mnt/data</code></div></main>''')

# Ask Openbox to keep the desktop behind normal windows and dock/panel above.
def apply_hints():
    try:
        subprocess.run(['wmctrl','-r','Ubuntu Workspace Desktop','-b','add,below,sticky'],env=os.environ,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    except Exception:
        pass
root.after(900,apply_hints)
root.mainloop()
