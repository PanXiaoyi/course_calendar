from flask import Flask, send_from_directory, request, jsonify
from icalendar import Calendar, Event
import os, re, datetime, json, requests

app = Flask(__name__)

@app.route('/')
def index():
    return send_from_directory(app.root_path, "index.html")

@app.route("/download/<path:filename>")
def downloader(filename):
    dirpath = os.path.join(app.root_path, 'static/ics') 
    return send_from_directory(dirpath, filename, as_attachment=True)

@app.route("/login")
def login():
    try:
        username = request.args.get('Ecom_User_ID')
        password = request.args.get('Ecom_Password')
        createIcs(username, password)
        return """<p>你的课表已创建</p>
        <p>点击<a href="http://106.12.93.121:5888/download/%s.ics">链接</a>下载</p>
        <p>如需使用帮助请查看<a href="https://github.com/PanXiaoyi/course_calendar">帮助</a></p>
        """ % username
    except:
        return """<p>查询课表失败</p>
        <p>请确认输入了正确的用户名或密码</p>
        <p>如有问题请发送邮件至1753499@tongji.edu.cn</p>
        <p>点击<a href="http://106.12.93.121:5888">此处</a>返回重试</p>
        """

def getCourse(username, password):
    session = requests.Session()
    base_url = "https://ids.tongji.edu.cn:8443"
    init_url = "https://courses.tongji.edu.cn/sign-in"

    result = session.get(init_url)

    #查找js并打开
    js = re.findall(r"<script src=/js/app(.*)js></script>", str(result.content))[0]
    result = session.get("https://courses.tongji.edu.cn/js/app" + js + "js")

    #查找ids.tongji.edu.cn
    mid_url = re.findall(r"VUE_APP_OAUTH_LOGIN:\"https://ids.tongji.edu.cn:8443(.*?)\"", str(result.content))[0]
    result = session.get(base_url + mid_url + init_url)

    #查找跳转地址
    login_url = re.findall(r"action=\"(.*)\"><", str(result.content))[0]
    result = session.post(base_url + login_url)
    
    #提交表单
    form = {
        'Ecom_Password': password,
        'Ecom_User_ID': username,
        'option': 'credential',
        'submit': '登录'
    }
    result = session.post(base_url + login_url, form)

    #登陆后跳转
    target_url = re.findall(r"window.location.href=\\'(.*)\\';", str(result.content))[0]
    result = session.get(target_url, allow_redirects=False)     #禁用重定向捕获code
    
    target_url = result.headers.get('Location')
    code = re.findall(r"code=(.*?)&", target_url)[0]
    result = session.get(target_url)            #重定向跳转

    #获取token
    form = {
        'usertoken':"",
        'code': code
    }
    result  = session.post(r"https://courses.tongji.edu.cn/api/v1/user/sso", form)
    data = json.loads(result.text).get("data")          #获取登录信息 重要字段token,user_id,name

    #获取当前周的课表
    form = {
        "token": data.get("token"),
        "start": '2020-03-02',
        "end": '2020-06-28'
    }
    result = session.post(r"https://courses.tongji.edu.cn/api/v1/user/calendar/my", form)
    course_json = json.loads(result.text).get("data")
    print(course_json)
    return course_json

def createIcs(user, password):
    course_list = getCourse(user, password)
    cal = Calendar()
    cal.add('prodid', '-//Sirius//Tongji Calendar 70.9054//CN')
    cal.add('version', '2.0')
    cal.add('calscale', 'GREGORIAN')
    cal.add('method', 'PUBLISH')
    cal.add('x-wr-calname', '课程表')
    for index, course in enumerate(course_list):
        title = re.split("[\||\r\n]", course.get("title"))
        title.pop(2)
        title[0] = title[0][:-1]
        title[1] = title[1][1:]
        title[2] = title[2][3 : -1]
        title[3] = title[3][4:]
        event = Event()
        event.add('dtstart', datetime.datetime.strptime(course.get('start'), '%Y-%m-%d %H:%M:%S'))
        event.add('dtend', datetime.datetime.strptime(course.get('end'), '%Y-%m-%d %H:%M:%S'))
        event.add('dtstamp', datetime.datetime(2020,3,10,13,30,0))
        event.add('uid', index)
        event.add('location', '教师:' + title[1])
        event.add('description', '会议号:' + title[2] + '|密码:' + title[3])
        event.add('status', 'CONFIRMED')
        event.add('summary', title[0])
        cal.add_component(event)
    f = open(os.path.join('./static/ics', user + '.ics'), 'wb')
    f.write(cal.to_ical())
    f.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5888)
