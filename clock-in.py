import datetime
import io
import json
import re
import sys
import time
from copy import copy
from dataclasses import dataclass
from typing import Callable, Union

import PIL.Image
import pytesseract
from requests import Response, Session

LOGIN_URL = 'https://zjuam.zju.edu.cn/cas/login?service=https%3A%2F%2Fhealthreport.zju.edu.cn%2Fa_zju%2Fapi%2Fsso%2Findex%3Fredirect%3Dhttps%253A%252F%252Fhealthreport.zju.edu.cn%252Fncov%252Fwap%252Fdefault%252Findex'
PUBLIC_KEY_URL = 'https://zjuam.zju.edu.cn/cas/v2/getPubKey'
BASE_URL = "https://healthreport.zju.edu.cn/ncov/wap/default/index"
SAVE_URL = "https://healthreport.zju.edu.cn/ncov/wap/default/save"
VERIFY_CODE_URL = 'https://healthreport.zju.edu.cn/ncov/wap/default/code'
VERIFY_CODE_FILE_NAME = 'code.png'
TESSERACT_CMD = 'tesseract'
MAX_TRIAL = 10

@dataclass
class Rsa:
    modulus: str
    exponent: str

# result
class Retry:
    pass

class Success:
    pass

class HaveClockIn:
    pass

@dataclass
class Error:
    message: str


Result = Union[Success, Retry, HaveClockIn, Error]

def sanitize_json(text: str) -> str:
    text = text.strip('{}, \t\n')
    items = text.split(',')
    key_vals = [[x.strip() for x in item.split(':')] for item in items]
    key_vals = [
        (f'"{key}"' if not key.startswith('"') else key, value)
        for key, value in key_vals
    ]
    items = [
        f'{key}:{value}'
        for key, value in key_vals
    ]
    text = ','.join(items)
    return '{' + text + '}'

def generate_headers() -> dict:
    return {'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.159 Safari/537.36'}

def get_execution(session: Session, login_url: str) -> str:
    response: Response = session.get(login_url)
    execution: str = re.search('name="execution" value="(.*?)"', response.text).group(1)
    return execution

def get_rsa_info(session: Session, public_key_url: str) -> Rsa:
    return Rsa(**session.get(public_key_url).json())

def rsa_encrypt(message: str, rsa_info: Rsa) -> str:
    password_bytes = bytes(message, 'ascii')
    password_int = int.from_bytes(password_bytes, 'big')
    e_int = int(rsa_info.exponent, 16)
    M_int = int(rsa_info.modulus, 16)
    result_int = pow(password_int, e_int, M_int)
    return hex(result_int)[2:].rjust(128, '0')

def login(username: str, password: str) -> Callable[[str, str], Session]:
    def call(login_url: str, public_key_url: str) -> Session:
        session = Session()
        execution = get_execution(session, login_url)
        rsa_info = get_rsa_info(session, public_key_url)
        password_encrypted = rsa_encrypt(password, rsa_info)
        data_to_post = {
            'username': username,
            'password': password_encrypted,
            'execution': execution,
            '_eventId': 'submit'
        }
        response = session.post(login_url, data_to_post)
        if '统一身份认证' in response.content.decode():
            raise Exception('登录失败')
        return session
    return call

def get_date() -> str:
    today = datetime.date.today()
    return "%4d%02d%02d" % (today.year, today.month, today.day)

def get_verify_code(session: Session) -> PIL.Image.Image:
    response = session.get(VERIFY_CODE_URL, headers=generate_headers())
    verify_code = response.content
    return PIL.Image.open(io.BytesIO(verify_code))

def recognize_verify_code(image: PIL.Image.Image) -> str:
    return pytesseract.image_to_string(image).strip()

def generate_info(session: Session, base_url: str) -> dict:
    response = session.get(base_url, headers=generate_headers())
    html: str = response.content.decode()
    #
    def_info = json.loads(re.findall(r'var def = ({[^\n]+});', html)[0])
    new_info = generate_new_info_from(def_info)
    return new_info

def generate_new_info_from(old_info: dict) -> dict:
    new_info = {
        "sfymqjczrj": "0", # 入境
        "zjdfgj": "",
        "sfyrjjh": "0",
        "cfgj": "",
        "tjgj": "",
        "nrjrq": "0",
        "rjka": "",
        "jnmddsheng": "",
        "jnmddshi": "",
        "jnmddqu": "",
        "jnmddxiangxi": "",
        "rjjtfs": "",
        "rjjtfs1": "",
        "rjjtgjbc": "",
        "jnjtfs": "",
        "jnjtfs1": "",
        "jnjtgjbc": "",
        "sfqrxxss": "1", # 是否确认信息属实
        "sfqtyyqjwdg": "",
        "sffrqjwdg": "",
        "sfhsjc": "",
        "zgfx14rfh": "0",
        "zgfx14rfhdd": "",
        "sfyxjzxgym": "",
        "sfbyjzrq": "0",
        "jzxgymqk": "0",
        "campus": "玉泉校区",
        "ismoved": "0",
        "tw": "0",
        "sfcxtz": "0",
        "sfjcbh": "0",
        "sfcxzysx": "0",
        "qksm": "",
        "sfyyjc": "0",
        "jcjgqr": "0",
        "remark": "",
        "address": "浙江省杭州市西湖区灵隐街道庆丰新村",
        "geo_api_info": "{\"type\":\"complete\",\"position\":{\"Q\":30.269411892362,\"R\":120.12539306640701,\"lng\":120.125393,\"lat\":30.269412},\"location_type\":\"html5\",\"message\":\"Get+ipLocation+failed.Get+geolocation+success.Convert+Success.Get+address+success.\",\"accuracy\":199,\"isConverted\":true,\"status\":1,\"addressComponent\":{\"citycode\":\"0571\",\"adcode\":\"330106\",\"businessAreas\":[{\"name\":\"西溪\",\"id\":\"330106\",\"location\":{\"Q\":30.271791,\"R\":120.09102999999999,\"lng\":120.09103,\"lat\":30.271791}},{\"name\":\"西湖\",\"id\":\"330106\",\"location\":{\"Q\":30.253167,\"R\":120.137878,\"lng\":120.137878,\"lat\":30.253167}},{\"name\":\"黄龙\",\"id\":\"330106\",\"location\":{\"Q\":30.266482,\"R\":120.13581299999998,\"lng\":120.135813,\"lat\":30.266482}}],\"neighborhoodType\":\"商务住宅;住宅区;住宅小区\",\"neighborhood\":\"庆丰新村\",\"building\":\"\",\"buildingType\":\"\",\"street\":\"西溪路\",\"streetNumber\":\"378号\",\"country\":\"中国\",\"province\":\"浙江省\",\"city\":\"杭州市\",\"district\":\"西湖区\",\"towncode\":\"330106003000\",\"township\":\"灵隐街道\"},\"formattedAddress\":\"浙江省杭州市西湖区灵隐街道庆丰新村\",\"roads\":[],\"crosses\":[],\"pois\":[],\"info\":\"SUCCESS\"}",
        "area": "浙江省+杭州市+西湖区",
        "province": "浙江省",
        "city": "杭州市",
        "sfzx": "1",
        "sfjcwhry": "0",
        "sfjchbry": "0",
        "sfcyglq": "0",
        "gllx": "",
        "glksrq": "",
        "jcbhlx": "",
        "jcbhrq": "",
        "bztcyy": "",
        "sftjhb": "",
        "sftjwh": "0",
        "sfjcqz": "",
        "jcqzrq": "",
        "jrsfqzys": "",
        "jrsfqzfy": "",
        "sfyqjzgc": "0",
        "sfsqhzjkk": "0", # 是否申领杭州健康码
        "sqhzjkkys": "1", # 杭州健康吗颜色，1:绿色 2:红色 3:黄色
        "gwszgzcs": "",
        "szgj": "",
        "internship": "1",
        "fxyy": "",
        "jcjg": "",
        "date": get_date(),
        "uid": "85614",
        "created": round(time.time()),
        "id": "55443557",
        "gwszdd": "",
        "szsqsfybl": "0",
        "sfygtjzzfj": "",
        "gtjzzfjsj": "",
        "szgjcs": "",
        "verifyCode": ""
    }
    return new_info

def post_data(session: Session, save_url: str, info: dict) -> Result:
    response_text = session.post(save_url, info, headers=generate_headers()).text
    response = json.loads(response_text)
    if response['e'] == 0:
        return Success()
    else:
        error_message = response["m"].strip()
        if error_message == '今天已经填报了':
            return HaveClockIn()
        elif error_message == '验证码错误':
            return Retry()
        else:
            return Error(error_message)

def clock_in(username: str, password: str):
    print('开始打卡')
    for _ in range(MAX_TRIAL):
        session = login(username, password)(LOGIN_URL, PUBLIC_KEY_URL)
        new_info = generate_info(session, BASE_URL)
        result = post_data(session, SAVE_URL, new_info)
        if type(result) == Success or type(result) == HaveClockIn:
            print('打卡成功')
            return
        elif type(result) == Retry:
            print('重试打卡')
            time.sleep(5)
            continue
        elif type(result) == Error:
            print(f'打卡失败：{result.message}')
            raise Exception("打卡失败")
        else:
            raise NotImplementedError()


if __name__ == '__main__':
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    username = sys.argv[1]
    password = sys.argv[2]
    clock_in(username, password)
