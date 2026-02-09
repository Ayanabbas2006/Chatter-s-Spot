from fastapi import FastAPI,HTTPException,Request,Form,Cookie
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from database import get_db
from fastapi.responses import FileResponse
from argon2 import PasswordHasher
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
ph=PasswordHasher()

app=FastAPI()

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"),name="icon")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
def text_to_ascii(s):
    return ','.join(str(ord(c)) for c in s)
def ascii_to_text(s):
    return ''.join(chr(int(code)) for code in s.split(','))

@app.middleware("http")
async def auth(request: Request, call_next):
    public_routes=["/","/login","/register","/register_user/","/login_user/"]
    if request.url.path not in public_routes:
        user= request.cookies.get("session_name")
        if not user:
            return RedirectResponse("/login",302)
    return await call_next(request)

@app.get("/login",response_class=HTMLResponse)
@app.get("/",response_class=HTMLResponse)
def login_page(request:Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register")
def register(request: Request):
    return templates.TemplateResponse("register.html",{"request":request})

@app.post("/register_user/")
def reg(request:Request,name: str = Form('name'), username: str= Form("username"), password: str= Form("password")):
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute("select * from users where name=%s",(name,))
            name_data=cur.fetchone()
            if name_data:
                return templates.TemplateResponse('register.html',{'request':request,'msg':"Name already taken!"})
            cur.execute("select * from users where name=%s",(username,))
            username_data=cur.fetchone()
            if username_data:
                return templates.TemplateResponse('register.html',{'request':request,'msg':"Username already taken!"})
            hashed_password=ph.hash(password)
            cur.execute("insert into users (username,password,name) values (%s,%s,%s)",(username,hashed_password,name))
            db.commit()
    return templates.TemplateResponse("login.html",{"request":request,"msg" : "Registered Successfully! Try login!"})

@app.post("/login_user/")
def log(request: Request,username : str= Form("username"), password:str = Form("password")):
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute("select * from users where username=(%s)",(username,))
            data=cur.fetchone()
    if data:
        try:
            ph.verify(data[2],password)
            res= RedirectResponse(f"/chat/{username}",status_code=302)
            res.set_cookie("session_name",username)
            return res
        except Exception:
            return templates.TemplateResponse("login.html",{"request":request,"msg" : "incorrect password"})
    else:
        return templates.TemplateResponse("login.html",{"request":request,"msg" : f"User {username} not found! Try register!"})

@app.get("/home")
def home( request: Request, session_name: str = Cookie(None)):
    if not session_name:
        return RedirectResponse("/login",status_code=302)
    return templates.TemplateResponse("home.html",{"request":request, "user": session_name})

@app.get("/chat/{username}")
def chat_page(request:Request,username: str,session_name: str = Cookie(None)):
    if not session_name:
        return RedirectResponse("/login",status_code=302)
    with get_db() as db:
        with db.cursor() as cur:
            cur.execute("select * from users where username = %s",(username,))
            current_user= cur.fetchone()
            cur.execute("select * from users where username != %s",(username,))
            other_user= cur.fetchall()
    return templates.TemplateResponse("home.html",{
        'request': request,
        "user": current_user[0],
        "users": other_user,
        "user_": "Select User"
    })

@app.post("/send_message/")
def send_msg( sender: str = Form('sender'), receiver: str= Form('receiver'), content: str = Form('content')):
    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE name=%s", (sender,))
            sender_row = cursor.fetchone()
            cursor.execute("SELECT * FROM users WHERE name=%s", (receiver,))
            receiver_row = cursor.fetchone()
            if not sender_row or not receiver_row:
                return {"status": "error", "detail": "Sender or receiver not found"}
            sender_id=sender_row[1]
            receiver_id=receiver_row[1]
            cursor.execute("INSERT INTO chats (sender, receiver, message,status) VALUES (%s,%s,%s,%s)",(sender_id, receiver_id, text_to_ascii(content),"sent"))
            db.commit()
    return {"status": "success", "message": content}

@app.get("/get_messages/")
def get_msg(usr1: str, usr2: str):
    with get_db() as db:
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM users WHERE name=%s", (usr1,))
            row1 = cursor.fetchone()
            cursor.execute("SELECT * FROM users WHERE name=%s", (usr2,))
            row2 = cursor.fetchone()
            if not row1 or not row2:
                return {"status": "error", "messages": [row1,row2]}
            uname1=row1[1]
            uname2=row2[1]
            cursor.execute("""
                SELECT sender, message FROM chats
                WHERE (sender=%s AND receiver=%s)
                OR (sender=%s AND receiver=%s)
                ORDER BY transact_at ASC
                """,
                (uname1, uname2, uname2, uname1)
                )
            rows = cursor.fetchall()
            messages = []
            for sender_id, content in rows:
                sender_type = "outgoing" if sender_id == uname1 else "incoming"
                messages.append({"type": sender_type, "content": ascii_to_text(content)})
    return {"status": "success", "messages": messages}