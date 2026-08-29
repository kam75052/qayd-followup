import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3, csv, os
from datetime import datetime

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qayd_data.db")

conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS settings(
    id INTEGER PRIMARY KEY CHECK(id=1),
    org_name TEXT DEFAULT '',
    dept_name TEXT DEFAULT '',
    section_name TEXT DEFAULT '',
    header_text TEXT DEFAULT '',
    manager_name TEXT DEFAULT '',
    manager_title TEXT DEFAULT '',
    show_header INTEGER DEFAULT 1,
    show_signature INTEGER DEFAULT 1
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS restrictions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    number TEXT UNIQUE,
    subject TEXT,
    directive TEXT,
    issuing_entity TEXT,
    directive_date TEXT,
    priority TEXT,
    notes TEXT,
    status TEXT DEFAULT 'غير منجز',
    created_at TEXT
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS referrals(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    restriction_id INTEGER,
    entity TEXT,
    person TEXT,
    status TEXT DEFAULT 'غير منجز',
    notes TEXT,
    FOREIGN KEY(restriction_id) REFERENCES restrictions(id) ON DELETE CASCADE
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS followups(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    referral_id INTEGER,
    action TEXT,
    followup_date TEXT,
    status TEXT DEFAULT 'غير منجز',
    completion_date TEXT,
    notes TEXT,
    FOREIGN KEY(referral_id) REFERENCES referrals(id) ON DELETE CASCADE
)""")
cur.execute("INSERT OR IGNORE INTO settings(id) VALUES(1)")
conn.commit()

def next_number():
    cur.execute("SELECT number FROM restrictions ORDER BY id DESC LIMIT 1")
    row=cur.fetchone()
    if not row: return "1"
    try: return str(int(row[0])+1)
    except: return str(cur.execute("SELECT COALESCE(MAX(id),0)+1 FROM restrictions").fetchone()[0])

def refresh():
    for x in tree.get_children(): tree.delete(x)
    cur.execute("SELECT id,number,subject,issuing_entity,directive_date,priority,status FROM restrictions ORDER BY id DESC")
    for r in cur.fetchall(): tree.insert("", "end", iid=r[0], values=r[1:])

def form_window(title, rid=None):
    w=tk.Toplevel(root); w.title(title); w.geometry("700x620"); w.transient(root); w.grab_set()
    labels=["رقم القيد","الموضوع","التوجيه","جهة التوجيه","تاريخ التوجيه","الأولوية","الملاحظات"]
    vals=[""]*7
    if rid:
        cur.execute("SELECT number,subject,directive,issuing_entity,directive_date,priority,notes FROM restrictions WHERE id=?",(rid,))
        vals=list(cur.fetchone())
    else: vals[0]=next_number(); vals[4]=datetime.now().strftime("%Y-%m-%d"); vals[5]="عادي"
    entries=[]
    for i,lbl in enumerate(labels):
        ttk.Label(w,text=lbl).grid(row=i,column=0,padx=12,pady=8,sticky="e")
        if i in (2,6):
            e=tk.Text(w,height=4 if i==2 else 5,width=55)
            e.insert("1.0",vals[i] or "")
        elif i==5:
            e=ttk.Combobox(w,values=["عادي","مهم","عاجل"],state="readonly",width=50)
            e.set(vals[i] or "عادي")
        else:
            e=ttk.Entry(w,width=55); e.insert(0,vals[i] or "")
        e.grid(row=i,column=1,padx=12,pady=8)
        entries.append(e)
    def save():
        data=[]
        for i,e in enumerate(entries):
            data.append(e.get("1.0","end-1c") if isinstance(e,tk.Text) else e.get())
        if not data[0] or not data[1]:
            messagebox.showwarning("تنبيه","رقم القيد والموضوع مطلوبان."); return
        if rid:
            cur.execute("""UPDATE restrictions SET number=?,subject=?,directive=?,issuing_entity=?,directive_date=?,priority=?,notes=? WHERE id=?""",(*data,rid))
        else:
            try: cur.execute("""INSERT INTO restrictions(number,subject,directive,issuing_entity,directive_date,priority,notes,created_at) VALUES(?,?,?,?,?,?,?,?)""",(*data,datetime.now().isoformat()))
            except sqlite3.IntegrityError:
                messagebox.showerror("خطأ","رقم القيد موجود مسبقًا."); return
        conn.commit(); refresh(); w.destroy()
    ttk.Button(w,text="حفظ",command=save).grid(row=8,column=1,pady=18,sticky="e")

def selected_id():
    s=tree.selection()
    return int(s[0]) if s else None

def referrals_window():
    rid=selected_id()
    if not rid: messagebox.showinfo("تنبيه","اختر قيدًا أولاً."); return
    w=tk.Toplevel(root); w.title("الإحالات والمتابعات"); w.geometry("900x620")
    ttk.Label(w,text="الإحالات المرتبطة بالقيد",font=("Arial",14,"bold")).pack(pady=10)
    cols=("id","entity","person","status","notes")
    tv=ttk.Treeview(w,columns=cols,show="headings")
    for c,t in zip(cols,["ID","الجهة","الشخص المختص","الحالة","ملاحظات"]): tv.heading(c,text=t)
    tv.pack(fill="both",expand=True,padx=10)
    def load():
        for x in tv.get_children(): tv.delete(x)
        cur.execute("SELECT id,entity,person,status,notes FROM referrals WHERE restriction_id=? ORDER BY id",(rid,))
        for r in cur.fetchall(): tv.insert("", "end", iid=r[0], values=r)
    def add_ref():
        f=tk.Toplevel(w); f.title("إضافة إحالة"); f.geometry("500x350")
        fields=["الجهة","الشخص المختص (اختياري)","الملاحظات"]
        es=[]
        for i,l in enumerate(fields):
            ttk.Label(f,text=l).grid(row=i,column=0,padx=10,pady=10,sticky="e")
            e=ttk.Entry(f,width=40); e.grid(row=i,column=1); es.append(e)
        def sv():
            if not es[0].get().strip(): messagebox.showwarning("تنبيه","اسم الجهة مطلوب."); return
            cur.execute("INSERT INTO referrals(restriction_id,entity,person,notes) VALUES(?,?,?,?)",(rid,es[0].get(),es[1].get(),es[2].get()))
            conn.commit(); load(); f.destroy()
        ttk.Button(f,text="حفظ",command=sv).grid(row=4,column=1,pady=15)
    def follow():
        s=tv.selection()
        if not s: messagebox.showinfo("تنبيه","اختر إحالة أولاً."); return
        ref=int(s[0]); fw=tk.Toplevel(w); fw.title("إجراءات المتابعة"); fw.geometry("760x480")
        ft=ttk.Treeview(fw,columns=("id","action","date","status","done"),show="headings")
        for c,t in zip(("id","action","date","status","done"),("ID","إجراء المتابعة","التاريخ","الحالة","تاريخ الإنجاز")): ft.heading(c,text=t)
        ft.pack(fill="both",expand=True,padx=10,pady=10)
        def loadf():
            for x in ft.get_children(): ft.delete(x)
            cur.execute("SELECT id,action,followup_date,status,completion_date FROM followups WHERE referral_id=? ORDER BY id DESC",(ref,))
            for r in cur.fetchall(): ft.insert("", "end", iid=r[0], values=r)
        def addf():
            af=tk.Toplevel(fw); af.title("إضافة متابعة"); af.geometry("520x360")
            labs=["إجراء المتابعة","التاريخ","الحالة","تاريخ الإنجاز","ملاحظات"]; es=[]
            for i,l in enumerate(labs):
                ttk.Label(af,text=l).grid(row=i,column=0,padx=10,pady=8,sticky="e")
                if i==2:
                    e=ttk.Combobox(af,values=["غير منجز","منجز"],state="readonly"); e.set("غير منجز")
                else: e=ttk.Entry(af,width=38)
                e.grid(row=i,column=1); es.append(e)
            es[1].insert(0,datetime.now().strftime("%Y-%m-%d"))
            def sv():
                if not es[0].get().strip(): messagebox.showwarning("تنبيه","إجراء المتابعة مطلوب."); return
                cur.execute("INSERT INTO followups(referral_id,action,followup_date,status,completion_date,notes) VALUES(?,?,?,?,?,?)",
                            (ref,es[0].get(),es[1].get(),es[2].get(),es[3].get(),es[4].get()))
                conn.commit(); loadf(); af.destroy()
            ttk.Button(af,text="حفظ",command=sv).grid(row=6,column=1,pady=15)
        ttk.Button(fw,text="إضافة متابعة",command=addf).pack(pady=5); loadf()
    ttk.Button(w,text="إضافة إحالة",command=add_ref).pack(side="left",padx=10,pady=10)
    ttk.Button(w,text="المتابعات",command=follow).pack(side="left",padx=10,pady=10)
    load()

def delete():
    rid=selected_id()
    if rid and messagebox.askyesno("تأكيد","هل تريد حذف القيد وجميع إحالاته ومتتابعاته؟"):
        cur.execute("DELETE FROM followups WHERE referral_id IN (SELECT id FROM referrals WHERE restriction_id=?)",(rid,))
        cur.execute("DELETE FROM referrals WHERE restriction_id=?",(rid,))
        cur.execute("DELETE FROM restrictions WHERE id=?",(rid,)); conn.commit(); refresh()

def settings_window():
    cur.execute("SELECT org_name,dept_name,section_name,header_text,manager_name,manager_title,show_header,show_signature FROM settings WHERE id=1")
    vals=list(cur.fetchone()); w=tk.Toplevel(root); w.title("إعدادات الترويسة والتوقيع"); w.geometry("600x520")
    labs=["اسم الجهة","اسم الإدارة","اسم القسم","نص إضافي للترويسة","اسم المسؤول","الصفة / المنصب"]; es=[]
    for i,l in enumerate(labs):
        ttk.Label(w,text=l).grid(row=i,column=0,padx=12,pady=10,sticky="e")
        e=ttk.Entry(w,width=45); e.insert(0,vals[i] or ""); e.grid(row=i,column=1); es.append(e)
    h=tk.IntVar(value=vals[6]); s=tk.IntVar(value=vals[7])
    ttk.Checkbutton(w,text="إظهار الترويسة في التقارير",variable=h).grid(row=7,column=1,sticky="e")
    ttk.Checkbutton(w,text="إظهار التوقيع في التقارير",variable=s).grid(row=8,column=1,sticky="e")
    def save():
        cur.execute("""UPDATE settings SET org_name=?,dept_name=?,section_name=?,header_text=?,manager_name=?,manager_title=?,show_header=?,show_signature=? WHERE id=1""",
                    (*[e.get() for e in es],h.get(),s.get())); conn.commit(); w.destroy()
    ttk.Button(w,text="حفظ",command=save).grid(row=10,column=1,pady=20)

def report():
    cur.execute("SELECT org_name,dept_name,section_name,header_text,manager_name,manager_title,show_header,show_signature FROM settings WHERE id=1")
    st=cur.fetchone()
    lines=[]
    if st[6]:
        for x in st[:4]:
            if x: lines.append(x)
        lines.append("="*70)
    lines.append("تقرير القيود والإحالات والمتابعة")
    lines.append("="*70)
    cur.execute("SELECT id,number,subject,directive,issuing_entity,directive_date,priority,status,notes FROM restrictions ORDER BY id")
    for r in cur.fetchall():
        lines.append(f"\nالقيد رقم: {r[1]}")
        lines.append(f"الموضوع: {r[2]}\nالتوجيه: {r[3]}\nجهة التوجيه: {r[4]}\nالتاريخ: {r[5]}\nالأولوية: {r[6]}\nالحالة: {r[7]}")
        cur.execute("SELECT id,entity,person,status,notes FROM referrals WHERE restriction_id=?",(r[0],))
        for rr in cur.fetchall():
            lines.append(f"  إحالة: {rr[1]} | الشخص: {rr[2] or 'غير محدد'} | الحالة: {rr[3]}")
            cur.execute("SELECT action,followup_date,status,completion_date FROM followups WHERE referral_id=?",(rr[0],))
            for ff in cur.fetchall(): lines.append(f"    متابعة: {ff[0]} | {ff[1]} | {ff[2]} | الإنجاز: {ff[3] or '-'}")
    if st[7]:
        lines += ["\n"+"-"*70,f"المسؤول: {st[4]}",f"الصفة: {st[5]}","التوقيع: __________________"]
    path=filedialog.asksaveasfilename(title="حفظ التقرير",defaultextension=".txt",filetypes=[("Text","*.txt")])
    if path:
        with open(path,"w",encoding="utf-8-sig") as f: f.write("\n".join(lines))
        messagebox.showinfo("تم","تم حفظ التقرير.")

root=tk.Tk(); root.title("نظام إدارة القيود والمتابعة"); root.geometry("1050x650")
style=ttk.Style(); style.configure("Treeview",rowheight=30,font=("Arial",10)); style.configure("TButton",padding=7)
ttk.Label(root,text="نظام إدارة القيود والمتابعة",font=("Arial",20,"bold")).pack(pady=15)
bar=ttk.Frame(root); bar.pack(fill="x",padx=15,pady=5)
for txt,cmd in [("إضافة قيد",lambda:form_window("إضافة قيد")),
                ("تعديل القيد",lambda: form_window("تعديل القيد",selected_id()) if selected_id() else messagebox.showinfo("تنبيه","اختر قيدًا أولاً.")),
                ("الإحالات والمتابعات",referrals_window),("حذف",delete),("التقارير",report),("الإعدادات",settings_window)]:
    ttk.Button(bar,text=txt,command=cmd).pack(side="right",padx=4)
cols=("number","subject","issuing","date","priority","status")
tree=ttk.Treeview(root,columns=cols,show="headings")
for c,t in zip(cols,["رقم القيد","الموضوع","جهة التوجيه","التاريخ","الأولوية","الحالة"]): tree.heading(c,text=t)
tree.pack(fill="both",expand=True,padx=15,pady=10)
ttk.Label(root,text="انقر مرتين على القيد لفتح الإحالات والمتابعات").pack(pady=5)
tree.bind("<Double-1>",lambda e:referrals_window())
refresh()
root.mainloop()
