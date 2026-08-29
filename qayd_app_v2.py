import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3, hashlib, csv, os, shutil, webbrowser
from datetime import datetime

APP_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(APP_DIR, 'qayd_data.db')
con = sqlite3.connect(DB)
con.execute('PRAGMA foreign_keys=ON')
cur = con.cursor()

cur.executescript('''
CREATE TABLE IF NOT EXISTS settings(
 id INTEGER PRIMARY KEY CHECK(id=1), org TEXT DEFAULT '', dept TEXT DEFAULT '', section TEXT DEFAULT '',
 header TEXT DEFAULT '', signer TEXT DEFAULT '', title TEXT DEFAULT '', show_header INTEGER DEFAULT 1, show_sign INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
 role TEXT DEFAULT 'موظف', active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS restrictions(
 id INTEGER PRIMARY KEY AUTOINCREMENT, number TEXT UNIQUE NOT NULL, subject TEXT NOT NULL, directive TEXT,
 source TEXT, source_date TEXT, priority TEXT DEFAULT 'عادي', status TEXT DEFAULT 'غير منجز', notes TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS referrals(
 id INTEGER PRIMARY KEY AUTOINCREMENT, restriction_id INTEGER NOT NULL, entity TEXT NOT NULL,
 person TEXT, status TEXT DEFAULT 'غير منجز', notes TEXT,
 FOREIGN KEY(restriction_id) REFERENCES restrictions(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS followups(
 id INTEGER PRIMARY KEY AUTOINCREMENT, referral_id INTEGER NOT NULL, action TEXT NOT NULL,
 followup_date TEXT, status TEXT DEFAULT 'غير منجز', completion_date TEXT, notes TEXT,
 FOREIGN KEY(referral_id) REFERENCES referrals(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS entities(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS persons(id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, entity_id INTEGER,
 FOREIGN KEY(entity_id) REFERENCES entities(id) ON DELETE SET NULL);
''')
cur.execute('INSERT OR IGNORE INTO settings(id) VALUES(1)')
def sha(s): return hashlib.sha256(s.encode('utf-8')).hexdigest()
cur.execute("INSERT OR IGNORE INTO users(username,password,role) VALUES('admin',?,'مدير')", (sha('admin123'),))
con.commit()

PERMS={
 'مدير': {'add':1,'edit':1,'delete':1,'reports':1,'settings':1,'users':1,'backup':1},
 'موظف': {'add':1,'edit':1,'delete':0,'reports':1,'settings':0,'users':0,'backup':0}
}
current_user=None

root=tk.Tk(); root.withdraw(); root.title('نظام إدارة القيود والمتابعة')
root.geometry('1250x760'); root.minsize(1000,650)
style=ttk.Style(); style.configure('Treeview',rowheight=30,font=('Arial',10)); style.configure('TButton',padding=7)


def next_number():
    cur.execute('SELECT number FROM restrictions ORDER BY id DESC LIMIT 1'); r=cur.fetchone()
    if not r: return '1'
    try: return str(int(r[0])+1)
    except: return str(cur.execute('SELECT COALESCE(MAX(id),0)+1 FROM restrictions').fetchone()[0])

def selected_id():
    s=main_tree.selection(); return int(s[0]) if s else None

def sync_status(rid):
    cur.execute('SELECT COUNT(*) FROM referrals WHERE restriction_id=?',(rid,)); total=cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM referrals WHERE restriction_id=? AND status='منجز'",(rid,)); done=cur.fetchone()[0]
    if total and done==total: st='منجز'
    elif total: st='يحتاج متابعة'
    else: st='غير منجز'
    cur.execute('UPDATE restrictions SET status=? WHERE id=?',(st,rid)); con.commit()

def refresh():
    for x in main_tree.get_children(): main_tree.delete(x)
    q=search_var.get().strip()
    cur.execute('''SELECT id,number,subject,directive,source,source_date,priority,status FROM restrictions
                   WHERE number LIKE ? OR subject LIKE ? OR directive LIKE ? OR source LIKE ? ORDER BY id DESC''',
                tuple(f'%{q}%' for _ in range(4)))
    for r in cur.fetchall(): main_tree.insert('', 'end', iid=r[0], values=r[1:])
    dashboard()

def dashboard():
    for w in stats.winfo_children(): w.destroy()
    items=[('إجمالي القيود',"SELECT COUNT(*) FROM restrictions",None),('منجزة',"SELECT COUNT(*) FROM restrictions WHERE status='منجز'",None),('غير منجزة',"SELECT COUNT(*) FROM restrictions WHERE status='غير منجز'",None),('تحتاج متابعة',"SELECT COUNT(*) FROM restrictions WHERE status='يحتاج متابعة'",None)]
    for i,(t,q,_) in enumerate(items):
        cur.execute(q); n=cur.fetchone()[0]
        f=ttk.LabelFrame(stats,text=t); f.grid(row=0,column=i,padx=6,sticky='nsew')
        ttk.Label(f,text=str(n),font=('Arial',18,'bold'),anchor='center',width=16).pack(pady=14)

def text_value(e): return e.get('1.0','end-1c').strip() if isinstance(e,tk.Text) else e.get().strip()

def restriction_form(rid=None):
    w=tk.Toplevel(root); w.title('تعديل القيد' if rid else 'إضافة قيد'); w.geometry('720x620'); w.transient(root)
    if rid:
        cur.execute('SELECT number,subject,directive,source,source_date,priority,notes FROM restrictions WHERE id=?',(rid,)); vals=list(cur.fetchone())
    else: vals=[next_number(),'','','',datetime.now().strftime('%Y-%m-%d'),'عادي','']
    labels=['رقم القيد','الموضوع','التوجيه','جهة التوجيه','تاريخ التوجيه','الأولوية','ملاحظات']; es=[]
    for i,l in enumerate(labels):
        ttk.Label(w,text=l).grid(row=i,column=0,padx=15,pady=9,sticky='e')
        if i in (2,6): e=tk.Text(w,width=52,height=5 if i==2 else 4); e.insert('1.0',vals[i] or '')
        elif i==5: e=ttk.Combobox(w,values=['عادي','مهم','عاجل'],state='readonly',width=49); e.set(vals[i] or 'عادي')
        else: e=ttk.Entry(w,width=52); e.insert(0,vals[i] or '')
        e.grid(row=i,column=1,sticky='w'); es.append(e)
    def save():
        d=[text_value(e) for e in es]
        if not d[0] or not d[1]: return messagebox.showwarning('تنبيه','رقم القيد والموضوع مطلوبان.')
        try:
            if rid: cur.execute('UPDATE restrictions SET number=?,subject=?,directive=?,source=?,source_date=?,priority=?,notes=? WHERE id=?',(*d,rid))
            else: cur.execute('INSERT INTO restrictions(number,subject,directive,source,source_date,priority,notes,created_at) VALUES(?,?,?,?,?,?,?,?)',(*d,datetime.now().isoformat()))
            con.commit(); refresh(); w.destroy()
        except sqlite3.IntegrityError: messagebox.showerror('خطأ','رقم القيد موجود مسبقًا.')
    ttk.Button(w,text='حفظ القيد',command=save).grid(row=8,column=1,pady=15,sticky='e')

def referrals_window():
    rid=selected_id()
    if not rid: return messagebox.showinfo('تنبيه','اختر قيدًا أولًا.')
    w=tk.Toplevel(root); w.title('الإحالات والمتابعات'); w.geometry('1050x650')
    cur.execute('SELECT number,subject FROM restrictions WHERE id=?',(rid,)); info=cur.fetchone()
    ttk.Label(w,text=f'القيد رقم {info[0]} — {info[1]}',font=('Arial',15,'bold')).pack(pady=10)
    tv=ttk.Treeview(w,columns=('id','entity','person','status','notes'),show='headings')
    for c,t in zip(('id','entity','person','status','notes'),('ID','الجهة الموجه لها','الشخص المختص','حالة الإنجاز','ملاحظات')): tv.heading(c,text=t); tv.column(c,anchor='center',width=170)
    tv.pack(fill='both',expand=True,padx=12,pady=8)
    def load():
        for x in tv.get_children(): tv.delete(x)
        cur.execute('SELECT id,entity,person,status,notes FROM referrals WHERE restriction_id=? ORDER BY id',(rid,))
        for r in cur.fetchall(): tv.insert('', 'end', iid=r[0], values=r)
    def add_ref():
        f=tk.Toplevel(w); f.title('إضافة إحالة'); f.geometry('560x400')
        labs=['الجهة الموجه لها','الشخص المختص (اختياري)','حالة الإنجاز','ملاحظات']; es=[]
        for i,l in enumerate(labs):
            ttk.Label(f,text=l).grid(row=i,column=0,padx=12,pady=10,sticky='e')
            if i==0:
                e=ttk.Combobox(f,width=40); cur.execute('SELECT name FROM entities ORDER BY name'); e['values']=[x[0] for x in cur.fetchall()]
            elif i==2: e=ttk.Combobox(f,values=['غير منجز','منجز'],state='readonly',width=38); e.set('غير منجز')
            else: e=ttk.Entry(f,width=40)
            e.grid(row=i,column=1); es.append(e)
        def save():
            entity,person,status,notes=[text_value(e) for e in es]
            if not entity:return messagebox.showwarning('تنبيه','الجهة مطلوبة.')
            cur.execute('INSERT OR IGNORE INTO entities(name) VALUES(?)',(entity,))
            cur.execute('INSERT INTO referrals(restriction_id,entity,person,status,notes) VALUES(?,?,?,?,?)',(rid,entity,person,status,notes)); con.commit(); sync_status(rid); refresh(); load(); f.destroy()
        ttk.Button(f,text='حفظ الإحالة',command=save).grid(row=5,column=1,pady=15)
    def toggle():
        s=tv.selection()
        if not s:return
        ref=int(s[0]); cur.execute('SELECT status FROM referrals WHERE id=?',(ref,)); st=cur.fetchone()[0]; ns='منجز' if st!='منجز' else 'غير منجز'
        cur.execute('UPDATE referrals SET status=? WHERE id=?',(ns,ref)); con.commit(); sync_status(rid); refresh(); load()
    def delete_ref():
        s=tv.selection()
        if not s:return
        if messagebox.askyesno('تأكيد','حذف الإحالة؟'):
            ref=int(s[0]); cur.execute('DELETE FROM followups WHERE referral_id=?',(ref,)); cur.execute('DELETE FROM referrals WHERE id=?',(ref,)); con.commit(); sync_status(rid); refresh(); load()
    def followups():
        s=tv.selection()
        if not s:return messagebox.showinfo('تنبيه','اختر إحالة أولًا.')
        ref=int(s[0]); f=tk.Toplevel(w); f.title('إجراءات المتابعة'); f.geometry('900x560')
        ft=ttk.Treeview(f,columns=('id','action','date','status','done','notes'),show='headings')
        for c,t in zip(('id','action','date','status','done','notes'),('ID','إجراء المتابعة','تاريخ المتابعة','الحالة','تاريخ الإنجاز','ملاحظات')): ft.heading(c,text=t); ft.column(c,anchor='center',width=135)
        ft.pack(fill='both',expand=True,padx=10,pady=10)
        def loadf():
            for x in ft.get_children():ft.delete(x)
            cur.execute('SELECT id,action,followup_date,status,completion_date,notes FROM followups WHERE referral_id=? ORDER BY id DESC',(ref,))
            for r in cur.fetchall():ft.insert('', 'end', iid=r[0], values=r)
        def addf():
            a=tk.Toplevel(f); a.title('إضافة إجراء متابعة'); a.geometry('580x430'); es=[]
            labs=['إجراء المتابعة','تاريخ المتابعة','الحالة','تاريخ الإنجاز','ملاحظات']
            for i,l in enumerate(labs):
                ttk.Label(a,text=l).grid(row=i,column=0,padx=10,pady=9,sticky='e')
                if i==2:e=ttk.Combobox(a,values=['غير منجز','منجز'],state='readonly',width=42);e.set('غير منجز')
                else:e=ttk.Entry(a,width=44)
                if i==1:e.insert(0,datetime.now().strftime('%Y-%m-%d'))
                e.grid(row=i,column=1);es.append(e)
            def savef():
                d=[text_value(e) for e in es]
                if not d[0]:return messagebox.showwarning('تنبيه','إجراء المتابعة مطلوب.')
                cur.execute('INSERT INTO followups(referral_id,action,followup_date,status,completion_date,notes) VALUES(?,?,?,?,?,?)',(ref,*d));con.commit();loadf();a.destroy()
            ttk.Button(a,text='حفظ',command=savef).grid(row=6,column=1,pady=15)
        ttk.Button(f,text='إضافة متابعة',command=addf).pack(pady=7);loadf()
    bar=ttk.Frame(w);bar.pack(fill='x',pady=8)
    for t,c in [('إضافة إحالة',add_ref),('تغيير الحالة',toggle),('إجراءات المتابعة',followups),('حذف الإحالة',delete_ref)]:ttk.Button(bar,text=t,command=c).pack(side='right',padx=5)
    load()

def delete_restriction():
    rid=selected_id()
    if rid and messagebox.askyesno('تأكيد','حذف القيد وجميع الإحالات والمتابعات؟'):
        cur.execute('DELETE FROM followups WHERE referral_id IN (SELECT id FROM referrals WHERE restriction_id=?)',(rid,));cur.execute('DELETE FROM referrals WHERE restriction_id=?',(rid,));cur.execute('DELETE FROM restrictions WHERE id=?',(rid,));con.commit();refresh()

def settings_window():
    cur.execute('SELECT org,dept,section,header,signer,title,show_header,show_sign FROM settings WHERE id=1');v=list(cur.fetchone())
    w=tk.Toplevel(root);w.title('الترويسة والتوقيع');w.geometry('650x540');es=[]
    labs=['اسم الجهة','الإدارة','القسم','نص الترويسة','اسم المسؤول','الصفة / المنصب']
    for i,l in enumerate(labs):
        ttk.Label(w,text=l).grid(row=i,column=0,padx=12,pady=10,sticky='e');e=ttk.Entry(w,width=48);e.insert(0,v[i] or '');e.grid(row=i,column=1);es.append(e)
    h=tk.IntVar(value=v[6]);s=tk.IntVar(value=v[7]);ttk.Checkbutton(w,text='إظهار الترويسة في التقرير',variable=h).grid(row=7,column=1,sticky='e');ttk.Checkbutton(w,text='إظهار التوقيع الثابت',variable=s).grid(row=8,column=1,sticky='e')
    def save():cur.execute('UPDATE settings SET org=?,dept=?,section=?,header=?,signer=?,title=?,show_header=?,show_sign=? WHERE id=1',(*[e.get().strip() for e in es],h.get(),s.get()));con.commit();w.destroy()
    ttk.Button(w,text='حفظ',command=save).grid(row=10,column=1,pady=20)

def users_window():
    if not PERMS[current_user['role']]['users']:return
    w=tk.Toplevel(root);w.title('المستخدمون والصلاحيات');w.geometry('760x500')
    tv=ttk.Treeview(w,columns=('id','username','role','active'),show='headings')
    for c,t in zip(('id','username','role','active'),('ID','اسم المستخدم','الصلاحية','الحالة')):tv.heading(c,text=t)
    tv.pack(fill='both',expand=True,padx=10,pady=10)
    def load():
        for x in tv.get_children():tv.delete(x)
        cur.execute('SELECT id,username,role,active FROM users ORDER BY id')
        for r in cur.fetchall():tv.insert('', 'end',iid=r[0],values=(r[0],r[1],r[2],'نشط' if r[3] else 'موقوف'))
    def add():
        a=tk.Toplevel(w);a.title('إضافة مستخدم');a.geometry('480x330');es=[]
        for i,l in enumerate(['اسم المستخدم','كلمة المرور','الصلاحية']):
            ttk.Label(a,text=l).grid(row=i,column=0,padx=12,pady=10)
            e=ttk.Combobox(a,values=['مدير','موظف'],state='readonly',width=30) if i==2 else ttk.Entry(a,width=32,show='*' if i==1 else '')
            e.grid(row=i,column=1);es.append(e)
        es[2].set('موظف')
        def save():
            try:cur.execute('INSERT INTO users(username,password,role) VALUES(?,?,?)',(es[0].get().strip(),sha(es[1].get()),es[2].get()));con.commit();load();a.destroy()
            except sqlite3.IntegrityError:messagebox.showerror('خطأ','اسم المستخدم موجود.')
        ttk.Button(a,text='حفظ',command=save).grid(row=5,column=1,pady=15)
    def reset():
        s=tv.selection()
        if not s:return
        uid=int(s[0]);a=tk.Toplevel(w);a.title('تغيير كلمة المرور');a.geometry('400x220');e=ttk.Entry(a,width=30,show='*');e.pack(pady=30)
        def save():cur.execute('UPDATE users SET password=? WHERE id=?',(sha(e.get()),uid));con.commit();a.destroy();messagebox.showinfo('تم','تم تغيير كلمة المرور.')
        ttk.Button(a,text='حفظ',command=save).pack()
    ttk.Button(w,text='إضافة مستخدم',command=add).pack(side='right',padx=6);ttk.Button(w,text='تغيير كلمة المرور',command=reset).pack(side='right',padx=6);load()

def export_csv():
    path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('Excel CSV','*.csv')],title='تصدير القيود')
    if not path:return
    with open(path,'w',newline='',encoding='utf-8-sig') as f:
        wr=csv.writer(f);wr.writerow(['رقم القيد','الموضوع','التوجيه','جهة التوجيه','تاريخ التوجيه','الأولوية','الحالة','جهة الإحالة','الشخص المختص','حالة الإحالة','إجراء المتابعة','تاريخ المتابعة','حالة المتابعة','تاريخ الإنجاز'])
        cur.execute('SELECT id,number,subject,directive,source,source_date,priority,status FROM restrictions ORDER BY id')
        for r in cur.fetchall():
            cur.execute('SELECT id,entity,person,status FROM referrals WHERE restriction_id=?',(r[0],));refs=cur.fetchall()
            if not refs:wr.writerow(list(r[1:])+['']*6);continue
            for ref in refs:
                cur.execute('SELECT action,followup_date,status,completion_date FROM followups WHERE referral_id=? ORDER BY id',(ref[0],));fs=cur.fetchall() or [('', '', '', '')]
                for fu in fs:wr.writerow(list(r[1:])+list(ref[1:])+list(fu))
    messagebox.showinfo('تم','تم تصدير البيانات ويمكن فتح الملف مباشرة في Excel.')

def backup():
    path=filedialog.asksaveasfilename(defaultextension='.db',filetypes=[('Database','*.db')],title='حفظ نسخة احتياطية')
    if path:con.commit();shutil.copy2(DB,path);messagebox.showinfo('تم','تم إنشاء النسخة الاحتياطية.')

def report():
    cur.execute('SELECT org,dept,section,header,signer,title,show_header,show_sign FROM settings WHERE id=1');s=cur.fetchone()
    lines=[]
    if s[6]:
        for x in s[:4]:
            if x:lines.append(x)
        lines.append('')
    lines.append('تقرير نظام إدارة القيود والمتابعة');lines.append('='*90)
    cur.execute('SELECT id,number,subject,directive,source,source_date,priority,status,notes FROM restrictions ORDER BY id')
    for r in cur.fetchall():
        lines += [f'رقم القيد: {r[1]}',f'الموضوع: {r[2]}',f'التوجيه: {r[3]}',f'جهة التوجيه: {r[4]}',f'تاريخ التوجيه: {r[5]}',f'الأولوية: {r[6]} | الحالة: {r[7]}']
        if r[8]:lines.append(f'ملاحظات: {r[8]}')
        cur.execute('SELECT id,entity,person,status,notes FROM referrals WHERE restriction_id=? ORDER BY id',(r[0],))
        for ref in cur.fetchall():
            lines.append(f'  إحالة إلى: {ref[1]} | الشخص: {ref[2] or "غير محدد"} | الحالة: {ref[3]}')
            cur.execute('SELECT action,followup_date,status,completion_date,notes FROM followups WHERE referral_id=? ORDER BY id',(ref[0],))
            for fu in cur.fetchall():lines.append(f'    متابعة: {fu[0]} | التاريخ: {fu[1]} | الحالة: {fu[2]} | الإنجاز: {fu[3] or ""} | {fu[4] or ""}')
        lines.append('-'*90)
    if s[7]:lines += ['',f'المسؤول: {s[4]}',f'الصفة: {s[5]}','التوقيع: __________________________']
    path=filedialog.asksaveasfilename(defaultextension='.html',filetypes=[('تقرير قابل للطباعة','*.html'),('Text','*.txt')],title='حفظ التقرير')
    if not path:return
    if path.endswith('.html'):
        import html
        body='<br>'.join(html.escape(x) for x in lines)
        open(path,'w',encoding='utf-8').write("<html dir='rtl'><meta charset='utf-8'><style>body{font-family:Arial;line-height:2;margin:40px}h1{text-align:center}</style><body>"+body+'</body></html>')
        webbrowser.open('file://'+os.path.abspath(path))
    else:open(path,'w',encoding='utf-8-sig').write('\n'.join(lines))

def login():
    global current_user
    w=tk.Toplevel(root);w.title('تسجيل الدخول');w.geometry('440x300');w.resizable(False,False);w.grab_set()
    ttk.Label(w,text='نظام إدارة القيود والمتابعة',font=('Arial',18,'bold')).pack(pady=22)
    u=ttk.Entry(w,width=34);p=ttk.Entry(w,width=34,show='*');u.pack(pady=7);p.pack(pady=7)
    ttk.Label(w,text='الحساب الأول: admin / admin123',foreground='gray').pack(pady=7)
    def go():
        global current_user
        cur.execute('SELECT id,username,role FROM users WHERE username=? AND password=? AND active=1',(u.get().strip(),sha(p.get())))
        r=cur.fetchone()
        if not r:return messagebox.showerror('خطأ','اسم المستخدم أو كلمة المرور غير صحيحة.')
        current_user={'id':r[0],'username':r[1],'role':r[2]};w.destroy();root.deiconify();apply_permissions();refresh()
    ttk.Button(w,text='دخول',command=go).pack(pady=10);u.focus()
    w.bind('<Return>',lambda e:go())
    w.protocol('WM_DELETE_WINDOW',root.destroy)

def apply_permissions():
    p=PERMS[current_user['role']]
    btn_delete.config(state='normal' if p['delete'] else 'disabled');btn_settings.config(state='normal' if p['settings'] else 'disabled');btn_users.config(state='normal' if p['users'] else 'disabled');btn_backup.config(state='normal' if p['backup'] else 'disabled')

# Main UI
header=ttk.Frame(root);header.pack(fill='x',padx=20,pady=12)
ttk.Label(header,text='نظام إدارة القيود والمتابعة',font=('Arial',24,'bold')).pack(side='right')
ttk.Label(header,text='V2 — النسخة المطورة',font=('Arial',11)).pack(side='left')
stats=ttk.Frame(root);stats.pack(fill='x',padx=20,pady=5)
tool=ttk.Frame(root);tool.pack(fill='x',padx=20,pady=10)
search_var=tk.StringVar();ttk.Label(tool,text='بحث:').pack(side='right');ttk.Entry(tool,textvariable=search_var,width=30).pack(side='right',padx=5);search_var.trace_add('write',lambda *a:refresh())
for t,c in [('إضافة قيد',lambda:restriction_form()),('تعديل',lambda:restriction_form(selected_id()) if selected_id() else messagebox.showinfo('تنبيه','اختر قيدًا أولًا.')),('الإحالات والمتابعات',referrals_window),('التقرير والطباعة',report),('تصدير Excel',export_csv)]:ttk.Button(tool,text=t,command=c).pack(side='right',padx=4)
btn_delete=ttk.Button(tool,text='حذف',command=delete_restriction);btn_delete.pack(side='right',padx=4)
btn_settings=ttk.Button(tool,text='الترويسة والتوقيع',command=settings_window);btn_settings.pack(side='right',padx=4)
btn_users=ttk.Button(tool,text='المستخدمون والصلاحيات',command=users_window);btn_users.pack(side='right',padx=4)
btn_backup=ttk.Button(tool,text='نسخة احتياطية',command=backup);btn_backup.pack(side='right',padx=4)
cols=('number','subject','directive','source','date','priority','status');main_tree=ttk.Treeview(root,columns=cols,show='headings')
for c,t in zip(cols,['رقم القيد','الموضوع','التوجيه','جهة التوجيه','تاريخ التوجيه','الأولوية','الحالة']):main_tree.heading(c,text=t);main_tree.column(c,anchor='center',width=150)
main_tree.pack(fill='both',expand=True,padx=20,pady=10)
main_tree.bind('<Double-1>',lambda e:referrals_window())
ttk.Label(root,text='النسخة الجديدة مستقلة عن النسخة السابقة. البيانات محفوظة محليًا على جهازك.',foreground='gray').pack(pady=5)
login();root.mainloop()
